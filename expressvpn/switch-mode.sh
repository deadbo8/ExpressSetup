#!/bin/bash
# =============================================================================
# ExpressVPN Mode Switch Script
# Switch between VPN and Direct routing modes at runtime
# Usage: switch-mode.sh vpn|direct
# Called via: docker exec expressvpn /usr/local/bin/switch-mode.sh <mode>
# =============================================================================

set -euo pipefail

# -- Color codes ---------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# -- Logging helpers -----------------------------------------------------------
log_info()    { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${GREEN}[INFO]${NC}    $*"; }
log_warn()    { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${YELLOW}[WARN]${NC}    $*"; }
log_error()   { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${RED}[ERROR]${NC}   $*"; }
log_success() { echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] ${CYAN}[SUCCESS]${NC} $*"; }

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

# -- Validate argument ---------------------------------------------------------
MODE="${1:-}"

if [ -z "$MODE" ]; then
    echo -e "${RED}Error: No mode specified.${NC}"
    echo "Usage: switch-mode.sh vpn|direct"
    exit 1
fi

if [ "$MODE" != "vpn" ] && [ "$MODE" != "direct" ]; then
    echo -e "${RED}Error: Invalid mode '${MODE}'. Must be 'vpn' or 'direct'.${NC}"
    echo "Usage: switch-mode.sh vpn|direct"
    exit 1
fi

# -- Read current mode ---------------------------------------------------------
CURRENT_MODE="unknown"
if [ -f /tmp/current_mode ]; then
    CURRENT_MODE=$(cat /tmp/current_mode)
fi

if [ "$MODE" = "$CURRENT_MODE" ]; then
    log_info "Already in '${MODE}' mode. No changes needed."
    echo "MODE=${MODE}"
    echo "STATUS=unchanged"
    exit 0
fi

# -- Apply VPN mode ------------------------------------------------------------
apply_vpn_mode() {
    log_info "Applying VPN mode iptables rules..."

    iptables -F FORWARD
    iptables -t nat -F POSTROUTING
    iptables -P FORWARD DROP  # Kill switch: block everything by default

    # Detect active VPN interface
    VPN_IF=$(ip route | grep -E '0.0.0.0/1|128.0.0.0/1' | awk '{print $5}' | head -n 1)
    if [ -z "$VPN_IF" ]; then
        VPN_IF=$(ip link show | grep -oE '(tun[0-9]+|lightway[0-9]+)' | head -n 1)
    fi
    if [ -z "$VPN_IF" ]; then
        VPN_IF="tun0"
    fi
    log_info "Detected VPN interface: $VPN_IF"

    # Allow WireGuard → VPN tunnel
    iptables -A FORWARD -i wg0 -o "$VPN_IF" -j ACCEPT
    iptables -A FORWARD -i "$VPN_IF" -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT

    # NAT through VPN
    iptables -t nat -A POSTROUTING -o "$VPN_IF" -j MASQUERADE

    echo 'vpn' > /tmp/current_mode
    log_success "VPN mode iptables rules applied."
}

# -- Apply Direct mode ---------------------------------------------------------
apply_direct_mode() {
    log_info "Applying Direct mode iptables rules..."

    iptables -F FORWARD
    iptables -t nat -F POSTROUTING
    iptables -P FORWARD DROP  # Kill switch: block everything by default

    # Allow WireGuard → direct internet (eth0)
    iptables -A FORWARD -i wg0 -o eth0 -j ACCEPT
    iptables -A FORWARD -i eth0 -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT

    # NAT through direct
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

    echo 'direct' > /tmp/current_mode
    log_success "Direct mode iptables rules applied."
}

# -- Execute mode switch -------------------------------------------------------
log_info "Switching from '${CURRENT_MODE}' to '${MODE}' mode..."

if [ "$MODE" = "vpn" ]; then
    # Ensure ExpressVPN is connected before routing through it
    log_info "Ensuring ExpressVPN is connected..."

    CURRENT_STATUS=$(expressvpnctl status 2>&1 || true)
    if echo "$CURRENT_STATUS" | grep -qi "connected" && ! echo "$CURRENT_STATUS" | grep -qi "disconnected" && ! echo "$CURRENT_STATUS" | grep -qi "not connected"; then
        log_info "ExpressVPN is already connected."
    else
        TARGET_SERVER="${SERVER:-smart}"
        log_info "Connecting to ExpressVPN server: ${TARGET_SERVER}..."
        expressvpnctl connect "$TARGET_SERVER" 2>&1 || true

        # Wait for connection (max 30s)
        WAIT=0
        CONNECTED=false
        while [ $WAIT -lt 30 ]; do
            if expressvpnctl status 2>&1 | grep -qi "Connected to"; then
                CONNECTED=true
                break
            fi
            sleep 1
            WAIT=$((WAIT + 1))
        done

        if [ "$CONNECTED" != "true" ]; then
            log_error "Failed to connect to ExpressVPN within 30s."
            echo "MODE=vpn"
            echo "STATUS=error"
            echo "ERROR=vpn_connection_failed"
            exit 1
        fi
        log_success "ExpressVPN connected after ${WAIT}s."
    fi

    apply_vpn_mode
    send_telegram "🔒 *Mode Switched to VPN* — Traffic now routed through VPN tunnel ($VPN_IF)"

elif [ "$MODE" = "direct" ]; then
    # Disconnect ExpressVPN to save resources (optional but recommended)
    log_info "Disconnecting ExpressVPN (not needed in direct mode)..."
    expressvpnctl disconnect 2>/dev/null || true
    sleep 2

    apply_direct_mode
    send_telegram "🌐 *Mode Switched to Direct* — Traffic now routed directly via eth0 (no VPN)"
fi

# -- Print parseable output for the bot ----------------------------------------
PUBLIC_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || echo "unknown")

echo ""
log_success "Mode switch complete!"
echo -e "  ${CYAN}Mode:${NC}       ${BOLD}${MODE}${NC}"
echo -e "  ${CYAN}Public IP:${NC}  ${PUBLIC_IP}"
echo ""

# Parseable key=value output
echo "MODE=${MODE}"
echo "STATUS=success"
echo "PUBLIC_IP=${PUBLIC_IP}"

exit 0
