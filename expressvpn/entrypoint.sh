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

    echo 'direct' > /tmp/current_mode
    log_success "Direct mode active — traffic routes through eth0 (no VPN)."
}

# -- Graceful shutdown ---------------------------------------------------------
cleanup() {
    log_warn "Received shutdown signal. Cleaning up..."
    send_telegram "🛑 *ExpressVPN Gateway shutting down*"
    expressvpn disconnect 2>/dev/null || true
    if [ -n "$DAEMON_PID" ] && kill -0 "$DAEMON_PID" 2>/dev/null; then
        log_info "Stopping expressvpnd (PID: $DAEMON_PID)..."
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
# STEP 2: Start expressvpnd daemon
# =============================================================================
log_step "Starting expressvpnd daemon..."

# Find the daemon binary — it may be in different locations depending on package version
EVPN_DAEMON=""
for candidate in /usr/bin/expressvpnd /usr/sbin/expressvpnd /opt/expressvpn/expressvpnd /usr/lib/expressvpn/expressvpnd; do
    if [ -x "$candidate" ]; then
        EVPN_DAEMON="$candidate"
        break
    fi
done

# Also search via find as a fallback
if [ -z "$EVPN_DAEMON" ]; then
    EVPN_DAEMON=$(find / -name 'expressvpnd' -type f -executable 2>/dev/null | head -1 || true)
fi

if [ -z "$EVPN_DAEMON" ]; then
    log_warn "expressvpnd binary not found separately — ExpressVPN may use a different startup method."
    log_info "Attempting to start via /etc/init.d/expressvpnd..."
    /etc/init.d/expressvpnd start 2>/dev/null || true
    sleep 5
else
    log_info "Found daemon at: $EVPN_DAEMON"
    "$EVPN_DAEMON" &
    DAEMON_PID=$!
    log_info "expressvpnd started with PID: $DAEMON_PID"
fi

# Wait for daemon readiness (max 60 seconds — takes longer on first boot)
log_info "Waiting for daemon to become ready (up to 60s)..."
SECONDS_WAITED=0
MAX_WAIT=60
while [ $SECONDS_WAITED -lt $MAX_WAIT ]; do
    if expressvpn status &>/dev/null 2>&1; then
        log_success "Daemon is ready after ${SECONDS_WAITED}s."
        break
    fi
    sleep 2
    SECONDS_WAITED=$((SECONDS_WAITED + 2))
done

if [ $SECONDS_WAITED -ge $MAX_WAIT ]; then
    log_error "Daemon failed to become ready within ${MAX_WAIT}s."
    log_info "Checking what binaries are available..."
    find / -name 'expressvpn*' -type f 2>/dev/null || true
    log_error "Container will exit. Check Dockerfile: is the .deb installing correctly?"
    exit 1
fi

# =============================================================================
# STEP 3: Activate ExpressVPN
# =============================================================================
log_step "Checking activation status..."

if expressvpn status 2>&1 | grep -qi "Not Activated"; then
    if [ -z "${ACTIVATION_CODE:-}" ]; then
        log_error "ACTIVATION_CODE environment variable is not set. Cannot activate."
        exit 1
    fi

    log_info "Activating ExpressVPN with provided activation code..."

    expect <<EOF
set timeout 30
spawn expressvpn activate
expect {
    "activation code" {
        send "${ACTIVATION_CODE}\r"
    }
    "Enter code" {
        send "${ACTIVATION_CODE}\r"
    }
    "code:" {
        send "${ACTIVATION_CODE}\r"
    }
    timeout {
        puts "ERROR: Timed out waiting for activation code prompt."
        exit 1
    }
}
expect {
    -re "diagnostics|information|share|help improve" {
        send "n\r"
    }
    timeout {
        puts "WARN: No diagnostics prompt received, continuing..."
    }
}
expect {
    -re "Activated|activated|success" {
        puts "Activation successful."
    }
    eof
}
EOF

    if [ $? -ne 0 ]; then
        log_error "Activation failed."
        exit 1
    fi
    log_success "ExpressVPN activated successfully."
else
    log_info "ExpressVPN is already activated."
fi

# =============================================================================
# STEP 4: Set preferences
# =============================================================================
log_step "Configuring ExpressVPN preferences..."

expressvpn preferences set send_diagnostics false
log_info "Diagnostics sharing: disabled"

expressvpn preferences set auto_connect true
log_info "Auto-connect: enabled"

# Disable network_lock — we manage the kill switch via iptables ourselves
# network_lock can interfere with WireGuard forwarding
expressvpn preferences set network_lock off
log_info "Network lock: off (managed via iptables)"

expressvpn protocol "$PROTOCOL"
log_info "Protocol set to: $PROTOCOL"

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

    expressvpn connect "$TARGET_SERVER"

    # Wait for connection to establish (max 30 seconds)
    log_info "Waiting for connection to establish..."
    SECONDS_WAITED=0
    MAX_WAIT=30
    CONNECTED=false
    while [ $SECONDS_WAITED -lt $MAX_WAIT ]; do
        STATUS=$(expressvpn status 2>&1 || true)
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
VPN_STATUS=$(expressvpn status 2>&1 || echo "unknown")
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
    CURRENT_STATUS=$(expressvpn status 2>&1 || true)

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
        expressvpn connect "$TARGET_SERVER" 2>&1 || true

        # Wait for reconnection (max 30s)
        RECONN_WAIT=0
        RECONN_OK=false
        while [ $RECONN_WAIT -lt 30 ]; do
            if expressvpn status 2>&1 | grep -qi "Connected"; then
                RECONN_OK=true
                break
            fi
            sleep 1
            RECONN_WAIT=$((RECONN_WAIT + 1))
        done

        if [ "$RECONN_OK" = "true" ]; then
            log_success "Reconnected successfully after ${RECONN_WAIT}s."

            # Re-apply VPN iptables rules (tun0 may have changed)
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
