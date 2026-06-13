FROM ubuntu:22.04

ARG EXPRESSVPN_VERSION=3.76.0.4-1

LABEL maintainer="expressvpn-gateway"
LABEL description="ExpressVPN CLI container for ARM64 (Oracle Cloud Ampere A1)"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install required dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    expect \
    iptables \
    iproute2 \
    curl \
    ca-certificates \
    jq \
    speedtest-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-downloaded ExpressVPN .run installer from the build context
# Place the installer as expressvpn/expressvpn_arm64.run before building
COPY expressvpn_arm64.run /tmp/expressvpn.run

# Install ExpressVPN — the .run file is a makeself archive
# We run it silently; ignore service-start failures (no systemd in Docker)
RUN chmod +x /tmp/expressvpn.run \
    && /tmp/expressvpn.run -- --noscripts 2>/dev/null \
    || /tmp/expressvpn.run 2>/dev/null || true \
    && apt-get update && apt-get install -f -y && rm -rf /var/lib/apt/lists/* \
    && rm -f /tmp/expressvpn.run

# Debug: confirm installation and show all installed binaries
RUN echo "=== ExpressVPN installed files ===" \
    && find / -name 'expressvpn*' -type f 2>/dev/null \
    && dpkg -l | grep -i express || true \
    && echo "=== END ==="

# Copy entrypoint and mode-switch scripts
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY switch-mode.sh /usr/local/bin/switch-mode.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/switch-mode.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Health check: verify VPN connected (vpn mode) OR direct mode is active
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD (expressvpn status | grep -q "Connected") || \
        ([ -f /tmp/current_mode ] && grep -q "direct" /tmp/current_mode) || exit 1
