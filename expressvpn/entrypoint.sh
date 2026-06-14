#!/bin/bash
# Note: we intentionally do NOT use set -e so we can handle errors gracefully

# =============================================================================
# ExpressVPN Container Entrypoint (v2)
# Handles daemon startup, activation, connection, kill-switch iptables,
# Telegram notifications, mode switching, and health monitoring
# =============================================================================

# -- Color codes ---------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# -- Logging helpers -----------------------------------------------------------
log_info()    { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${GREEN}[INFO]${NC}    $*"; }
log_warn()    { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${YELLOW}[WARN]${NC}    $*"; }
log_error()   { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${RED}[ERROR]${NC}   $*"; }
log_success() { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${CYAN}[SUCCESS]${NC} $*"; }
log_step()    { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${BLUE}[STEP]${NC}    $*"; }

# -- Telegram notifications ---------------------------------------------------
send_telegram() {
    local message="$1"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_CHAT_ID}" \
            -d text="${message}" \
            -d parse_mode="Markdown" > /dev/null 2>&1 || true
    fi
}

# -- Global state --------------------------------------------------------------
DAEMON_PID=""
TARGET_SERVER="${SERVER:-smart}"
PROTOCOL="${PREFERRED_PROTOCOL:-lightway_udp}"
INITIAL_MODE="${VPN_MODE:-vpn}"

# -- Policy routing: fix eth0 response routing --------------------------------
# ExpressVPN injects 0.0.0.0/1 and 128.0.0.0/1 routes via tun0, which means
# ALL outbound traffic (including responses to inbound connections) goes through
# the VPN. This breaks AdGuard/WireGuard UI access from outside.
# Solution: route table 200 sends traffic from eth0's IP back via eth0.
_fix_eth0_routing() {
    ETH0_IP=$(ip addr show eth0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
    ETH0_GW=$(ip route | grep default | grep eth0 | awk '{print $3}' | head -1)
    ETH0_NET=$(ip route | grep eth0 | grep -v default | grep -v via | head -1 | awk '{print $1}')

    if [ -z "$ETH0_IP" ] || [ -z "$ETH0_GW" ]; then
        log_warn "Could not determine eth0 IP or gateway — skipping policy routing fix"
        return
    fi

    log_info "Policy routing: eth0 IP=$ETH0_IP GW=$ETH0_GW net=$ETH0_NET"
    ip route flush table 200 2>/dev/null || true
    [ -n "$ETH0_NET" ] && ip route add "$ETH0_NET" dev eth0 table 200 2>/dev/null || true
    ip route add default via "$ETH0_GW" dev eth0 table 200 2>/dev/null || true
    ip rule del from "$ETH0_IP" table 200 priority 100 2>/dev/null || true
    ip rule add from "$ETH0_IP" table 200 priority 100
    log_success "Policy routing configured — service responses will use eth0"
}

# -- iptables: VPN mode (fail-closed kill switch) -----------------------------
apply_vpn_mode() {
    log_info "Applying VPN mode iptables rules (kill switch active)..."

    iptables -F FORWARD
    iptables -t nat -F POSTROUTING
    iptables -P FORWARD DROP  # Default: block everything (kill switch)

    # Allow WireGuard → VPN tunnel
    iptables -A FORWARD -i wg0 -o tun0 -j ACCEPT
    iptables -A FORWARD -i tun0 -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT

    # NAT through VPN
    iptables -t nat -A POSTROUTING -o tun0 -j MASQUERADE

    # The gateway itself needs unrestricted INPUT/OUTPUT to allow the daemon to reconnect
    # to the ExpressVPN API when the tunnel drops, and to allow hosted services to respond.
    iptables -I INPUT 1 -j ACCEPT 2>/dev/null || true
    iptables -I OUTPUT 1 -j ACCEPT 2>/dev/null || true

    # Neuter ExpressVPN's internal block sub-chain to bypass Network Lock 
    # without triggering the daemon's anti-tamper deadlock loop.
    iptables -I evpn.100.blockAll 1 -j ACCEPT 2>/dev/null || true

    # Fix routing asymmetry: ExpressVPN adds 0.0.0.0/1 and 128.0.0.0/1 routes via tun0
    # which causes response packets for inbound connections to be mis-routed through tun0.
    # Policy routing table 200 ensures responses to eth0-destined traffic go back via eth0.
    _fix_eth0_routing

    echo 'vpn' > /tmp/current_mode
    log_success "VPN mode active — traffic routes through tun0 (kill switch enforced)."

}

# -- iptables: Direct mode (fail-closed kill switch) ---------------------------
apply_direct_mode() {
    log_info "Applying Direct mode iptables rules (kill switch active)..."

    iptables -F FORWARD
    iptables -t nat -F POSTROUTING
    iptables -P FORWARD DROP  # Default: block everything (kill switch)

    # Allow WireGuard → direct internet (eth0)
    iptables -A FORWARD -i wg0 -o eth0 -j ACCEPT
    iptables -A FORWARD -i eth0 -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT

    # NAT through direct
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

    # The gateway itself needs unrestricted INPUT/OUTPUT.
    iptables -I INPUT 1 -j ACCEPT 2>/dev/null || true
    iptables -I OUTPUT 1 -j ACCEPT 2>/dev/null || true

    echo 'direct' > /tmp/current_mode
    log_success "Direct mode active — traffic routes through eth0 (no VPN)."
}

# -- Graceful shutdown ---------------------------------------------------------
cleanup() {
    log_warn "Received shutdown signal. Cleaning up..."
    send_telegram "🛑 *ExpressVPN Gateway shutting down*"
    expressvpnctl disconnect 2>/dev/null || true
    if [ -n "$DAEMON_PID" ] && kill -0 "$DAEMON_PID" 2>/dev/null; then
        log_info "Stopping expressvpn-daemon (PID: $DAEMON_PID)..."
        kill "$DAEMON_PID" 2>/dev/null || true
        wait "$DAEMON_PID" 2>/dev/null || true
    fi
    log_info "Shutdown complete. Goodbye."
    exit 0
}

trap cleanup SIGTERM SIGINT

# =============================================================================
# STEP 1: Create TUN device
# =============================================================================
log_step "Creating /dev/net/tun device..."
mkdir -p /dev/net
mknod /dev/net/tun c 10 200 2>/dev/null || true
if [ -c /dev/net/tun ]; then
    log_success "/dev/net/tun is ready."
else
    log_error "/dev/net/tun could not be created. Ensure container has NET_ADMIN capability."
    exit 1
fi

# =============================================================================
# STEP 2: Start expressvpn-daemon
# =============================================================================
log_step "Starting expressvpn-daemon..."

# The daemon binary is at /opt/expressvpn/bin/expressvpn-daemon
EVPN_DAEMON="/opt/expressvpn/bin/expressvpn-daemon"

if [ ! -x "$EVPN_DAEMON" ]; then
    log_error "Daemon not found at $EVPN_DAEMON. Was ExpressVPN installed correctly?"
    exit 1
fi

log_info "Starting daemon: $EVPN_DAEMON run"
"$EVPN_DAEMON" run > /tmp/daemon.log 2>&1 &
DAEMON_PID=$!
log_info "expressvpn-daemon started with PID: $DAEMON_PID"

# Wait for daemon readiness (max 60 seconds)
log_info "Waiting for daemon to become ready (up to 60s)..."
SECONDS_WAITED=0
MAX_WAIT=60
while [ $SECONDS_WAITED -lt $MAX_WAIT ]; do
    if expressvpnctl status &>/dev/null 2>&1; then
        log_success "Daemon is ready after ${SECONDS_WAITED}s."
        break
    fi
    sleep 2
    SECONDS_WAITED=$((SECONDS_WAITED + 2))
done

if [ $SECONDS_WAITED -ge $MAX_WAIT ]; then
    log_error "Daemon failed to become ready within ${MAX_WAIT}s."
    log_error "=== Daemon output (last 20 lines) ==="
    tail -20 /tmp/daemon.log 2>/dev/null || true
    log_error "=== End daemon output ==="
    exit 1
fi

# =============================================================================
# STEP 3: Activate ExpressVPN
# =============================================================================
log_step "Checking login status..."

if expressvpnctl status 2>&1 | grep -qi "Not logged in\|not logged\|login"; then
    if [ -z "${ACTIVATION_CODE:-}" ]; then
        log_error "ACTIVATION_CODE environment variable is not set. Cannot login."
        exit 1
    fi

    log_info "Logging in to ExpressVPN with activation code..."

    # Write activation code to a temp file (required by expressvpnctl login)
    echo "${ACTIVATION_CODE}" > /tmp/evpn_login.txt
    expressvpnctl login /tmp/evpn_login.txt
    LOGIN_RESULT=$?
    rm -f /tmp/evpn_login.txt

    if [ $LOGIN_RESULT -ne 0 ]; then
        log_error "Login failed. Check your ACTIVATION_CODE."
        exit 1
    fi
    log_success "ExpressVPN logged in successfully."
else
    log_info "ExpressVPN is already logged in."
fi

# =============================================================================
# STEP 4: Set preferences
# =============================================================================
log_step "Configuring ExpressVPN preferences..."

# Enable background mode — REQUIRED for headless operation without GUI
expressvpnctl background enable
log_info "Background mode: enabled"

# Disable network lock natively. We manage our own kill switch via iptables.
expressvpn preferences set network_lock off 2>/dev/null || true
expressvpn preferences set force_vpn_dns false 2>/dev/null || true
expressvpn preferences set block_trackers false 2>/dev/null || true
log_info "Network lock: disabled via preferences"

# Set protocol
expressvpnctl set protocol "${PROTOCOL:-auto}"
log_info "Protocol set to: ${PROTOCOL:-auto}"

log_success "All preferences configured."

# =============================================================================
# STEP 5: Connect to VPN server (unless starting in direct mode)
# =============================================================================
if [ "$INITIAL_MODE" = "direct" ]; then
    log_step "Starting in DIRECT mode — skipping VPN connection."
    apply_direct_mode

    PUBLIC_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || echo "unknown")
    send_telegram "🌐 *ExpressVPN Gateway started in Direct mode*
• Public IP: \`${PUBLIC_IP}\`
• VPN: not connected
• Traffic routes directly via eth0"
else
    log_step "Connecting to ExpressVPN server: ${BOLD}${TARGET_SERVER}${NC}..."

    expressvpnctl connect "$TARGET_SERVER"

    # Wait for connection to establish (max 30 seconds)
    log_info "Waiting for connection to establish..."
    SECONDS_WAITED=0
    MAX_WAIT=30
    CONNECTED=false
    while [ $SECONDS_WAITED -lt $MAX_WAIT ]; do
        STATUS=$(expressvpnctl status 2>&1 || true)
        if echo "$STATUS" | grep -qi "Connected"; then
            CONNECTED=true
            break
        fi
        sleep 1
        SECONDS_WAITED=$((SECONDS_WAITED + 1))
    done

    if [ "$CONNECTED" != "true" ]; then
        log_error "Failed to connect within ${MAX_WAIT}s."
        log_error "Last status: $STATUS"
        exit 1
    fi

    log_success "VPN connection established after ${SECONDS_WAITED}s."

    # Apply VPN mode iptables (kill switch)
    apply_vpn_mode

    PUBLIC_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || echo "unknown")
    send_telegram "✅ *ExpressVPN Gateway Online*
• Server: \`${TARGET_SERVER}\`
• Protocol: \`${PROTOCOL}\`
• Public IP: \`${PUBLIC_IP}\`
• Kill switch: active"
fi

# =============================================================================
# STEP 6: Print success banner
# =============================================================================
PUBLIC_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || echo "unknown")
VPN_STATUS=$(expressvpnctl status 2>&1 || echo "unknown")
CURRENT_MODE=$(cat /tmp/current_mode 2>/dev/null || echo "unknown")

echo ""
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅ ExpressVPN Gateway v2 is Running${NC}"
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "  ${CYAN}Public IP:${NC}   $PUBLIC_IP"
echo -e "  ${CYAN}Server:${NC}     $TARGET_SERVER"
echo -e "  ${CYAN}Protocol:${NC}   $PROTOCOL"
echo -e "  ${CYAN}Mode:${NC}       ${BOLD}${CURRENT_MODE}${NC}"
echo -e "  ${CYAN}VPN Status:${NC} $VPN_STATUS"
echo -e "  ${CYAN}Kill Switch:${NC} ${GREEN}ACTIVE${NC} (FORWARD policy DROP)"
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""

# =============================================================================
# STEP 7: Health monitoring loop
# =============================================================================
log_step "Entering health monitoring loop (checking every 60s)..."

VPN_WAS_DOWN=false

while true; do
    sleep 60 &
    wait $!

    # Read current mode — it may have been changed by switch-mode.sh
    CURRENT_MODE=$(cat /tmp/current_mode 2>/dev/null || echo "vpn")

    if [ "$CURRENT_MODE" = "direct" ]; then
        # In direct mode, just verify iptables are sane
        log_info "Health check: ${CYAN}Direct mode${NC} — VPN monitoring skipped."
        continue
    fi

    # VPN mode: check connection health
    CURRENT_STATUS=$(expressvpnctl status 2>&1 || true)

    if echo "$CURRENT_STATUS" | grep -qi "Connected"; then
        if [ "$VPN_WAS_DOWN" = "true" ]; then
            # VPN just recovered
            VPN_WAS_DOWN=false
            NEW_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || echo "unknown")
            log_success "VPN reconnected! New IP: ${NEW_IP}"
            send_telegram "✅ *VPN Reconnected* to \`${TARGET_SERVER}\`
• Public IP: \`${NEW_IP}\`
• Kill switch: re-applied"
        fi
        log_info "Health check: ${GREEN}Connected${NC} — $CURRENT_STATUS"
    else
        VPN_WAS_DOWN=true
        log_warn "Health check: ${RED}NOT connected${NC} — $CURRENT_STATUS"
        log_warn "Kill switch active — all client traffic is blocked until VPN recovers."
        send_telegram "⚠️ *VPN Disconnected!* Kill switch active — reconnecting..."

        log_warn "Attempting reconnection to ${TARGET_SERVER}..."
        expressvpnctl connect "$TARGET_SERVER" 2>&1 || true

        # Wait for reconnection (max 30s)
        RECONN_WAIT=0
        RECONN_OK=false
        while [ $RECONN_WAIT -lt 30 ]; do
            if expressvpnctl status 2>&1 | grep -qi "Connected"; then
                RECONN_OK=true
                break
            fi
            sleep 1
            RECONN_WAIT=$((RECONN_WAIT + 1))
        done

        if [ "$RECONN_OK" = "true" ]; then
            log_success "Reconnected successfully after ${RECONN_WAIT}s."

            # Re-apply VPN iptables rules (tun0 may have changed)
            # We must wait a few seconds because the daemon might overwrite our rules
            # right after it connects.
            sleep 3
            apply_vpn_mode

            NEW_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || echo "unknown")
            log_info "New public IP: $NEW_IP"

            VPN_WAS_DOWN=false
            send_telegram "✅ *VPN Reconnected* to \`${TARGET_SERVER}\`
• Reconnected after: ${RECONN_WAIT}s
• Public IP: \`${NEW_IP}\`
• Kill switch: re-applied"
        else
            log_error "Reconnection failed. Kill switch remains active. Will retry in next cycle."
            send_telegram "❌ *VPN Reconnection Failed!* Kill switch still active — retrying in 60s..."
        fi
    fi
done
