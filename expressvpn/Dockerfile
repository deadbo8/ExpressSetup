FROM ubuntu:22.04

LABEL maintainer="expressvpn-gateway"
LABEL description="ExpressVPN CLI container for ARM64 (Oracle Cloud Ampere A1)"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install required dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    expect \
    iptables \
    iproute2 \
    curl \
    ca-certificates \
    jq \
    speedtest-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-downloaded ExpressVPN .run installer from the build context
COPY expressvpn_arm64.run /tmp/expressvpn.run

# Install ExpressVPN in headless mode (no systemd, no GUI)
# The installer asks "Is this ok? [y/N]" for headless mode — we answer y
RUN chmod +x /tmp/expressvpn.run \
    && echo "y" | /tmp/expressvpn.run -- --headless 2>&1 || \
       printf "y\n" | /tmp/expressvpn.run 2>&1 || true \
    && rm -f /tmp/expressvpn.run

# Add ExpressVPN binaries to PATH
ENV PATH="/opt/expressvpn/bin:${PATH}"

# Confirm installation — we now know the binaries are in /opt/expressvpn/bin/
RUN echo "=== ExpressVPN installed files ===" \
    && ls -la /opt/expressvpn/bin/ \
    && echo "=== END ==="

# Copy entrypoint and mode-switch scripts
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY switch-mode.sh /usr/local/bin/switch-mode.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/switch-mode.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Health check: verify VPN connected (vpn mode) OR direct mode is active
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD (expressvpnctl status | grep -qi "Connected") || \
        ([ -f /tmp/current_mode ] && grep -q "direct" /tmp/current_mode) || exit 1
