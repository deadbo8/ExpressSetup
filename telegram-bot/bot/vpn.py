"""ExpressVPN CLI wrapper — executes commands inside the Docker container."""

import asyncio
import json
import logging
from .config import EXPRESSVPN_CONTAINER

logger = logging.getLogger(__name__)


async def _exec(args: list[str], timeout: float = 30) -> tuple[int, str, str]:
    """Execute a command inside the ExpressVPN container."""
    # Ensure absolute path is used to avoid PATH resolution issues via docker exec
    if args and args[0] in ("expressvpn", "expressvpnctl"):
        args[0] = "/opt/expressvpn/bin/expressvpnctl"

    cmd = ["docker", "exec", EXPRESSVPN_CONTAINER] + args
    logger.debug("Running: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return 1, "", "Command timed out"
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


# ── Status ───────────────────────────────────────────────────────────────────

async def get_status() -> str:
    """Return a human-readable VPN status with emoji."""
    try:
        rc, out, err = await _exec(["expressvpn", "status"])
        if rc != 0:
            logger.error("status failed (rc=%d): %s", rc, err)
            return f"❌ *Error getting status*\n`{err or out}`"

        lower = out.lower()
        if "connected" in lower and "not connected" not in lower:
            return f"🟢 *Connected*\n\n```\n{out}\n```"
        else:
            return f"🔴 *Disconnected*\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("get_status error")
        return f"❌ *Error:* `{exc}`"


# ── Connect / Disconnect ─────────────────────────────────────────────────────

async def connect(location: str = "smart") -> str:
    """Connect to the given location alias (default: smart)."""
    try:
        rc, out, err = await _exec(["expressvpn", "connect", location])
        if rc != 0:
            logger.error("connect(%s) failed (rc=%d): %s", location, rc, err)
            return f"❌ *Connection failed*\n`{err or out}`"
        return f"✅ *Connected to* `{location}`\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("connect error")
        return f"❌ *Error:* `{exc}`"


async def disconnect() -> str:
    """Disconnect from the current VPN server."""
    try:
        rc, out, err = await _exec(["expressvpn", "disconnect"])
        if rc != 0:
            logger.error("disconnect failed (rc=%d): %s", rc, err)
            return f"❌ *Disconnect failed*\n`{err or out}`"
        return f"🔌 *Disconnected*\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("disconnect error")
        return f"❌ *Error:* `{exc}`"


# ── Reconnect ────────────────────────────────────────────────────────────────

async def reconnect() -> str:
    """Disconnect then reconnect (same server / smart)."""
    try:
        # Grab the current location before disconnecting
        rc_s, status_out, _ = await _exec(["expressvpn", "status"])
        location = "smart"
        if rc_s == 0:
            for line in status_out.splitlines():
                lower = line.lower()
                if "connected to" in lower:
                    # e.g. "Connected to USA - New York"
                    parts = line.split("Connected to", 1)
                    if len(parts) == 2:
                        location = parts[1].strip()
                    break

        await _exec(["expressvpn", "disconnect"])
        rc, out, err = await _exec(["expressvpn", "connect", location])
        if rc != 0:
            return f"❌ *Reconnect failed*\n`{err or out}`"
        return f"🔄 *Reconnected to* `{location}`\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("reconnect error")
        return f"❌ *Error:* `{exc}`"


# ── Server list ──────────────────────────────────────────────────────────────

async def get_locations() -> str:
    """Return the raw server list."""
    try:
        rc, out, err = await _exec(["expressvpn", "list", "all"])
        if rc != 0:
            logger.error("list failed (rc=%d): %s", rc, err)
            return f"❌ *Error listing servers*\n`{err or out}`"
        return f"🗺 *Available Servers*\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("get_locations error")
        return f"❌ *Error:* `{exc}`"


async def get_server_list_filtered(query: str) -> str:
    """Search the full server list for locations matching a query."""
    try:
        rc, out, err = await _exec(["expressvpn", "list", "all"])
        if rc != 0:
            logger.error("list filtered failed (rc=%d): %s", rc, err)
            return f"❌ *Error listing servers*\n`{err or out}`"

        lines = out.splitlines()
        header = lines[0] if lines else ""
        matches = [l for l in lines[1:] if query.lower() in l.lower()]

        if not matches:
            return f"🔍 *No servers found matching* `{query}`"

        result = "\n".join(matches[:20])  # Limit to 20 results
        count = len(matches)
        return (
            f"🔍 *Servers matching* `{query}` ({count} found)\n\n"
            f"```\n{header}\n{result}\n```"
        )
    except Exception as exc:
        logger.exception("get_server_list_filtered error")
        return f"❌ *Error:* `{exc}`"


# ── Public IP ────────────────────────────────────────────────────────────────

async def get_public_ip() -> str:
    """Fetch the container's public IP via ifconfig.me."""
    try:
        rc, out, err = await _exec(["curl", "-s", "--max-time", "5", "ifconfig.me"])
        if rc != 0:
            logger.error("curl ip failed (rc=%d): %s", rc, err)
            return f"❌ *Could not retrieve IP*\n`{err or out}`"
        return f"🌐 *Public IP:* `{out}`"
    except Exception as exc:
        logger.exception("get_public_ip error")
        return f"❌ *Error:* `{exc}`"


# ── Protocol ─────────────────────────────────────────────────────────────────

async def get_protocol() -> str:
    """Return the current protocol setting."""
    try:
        rc, out, err = await _exec(["expressvpn", "protocol"])
        if rc != 0:
            logger.error("protocol get failed (rc=%d): %s", rc, err)
            return f"❌ *Error getting protocol*\n`{err or out}`"
        return f"⚡ *Protocol*\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("get_protocol error")
        return f"❌ *Error:* `{exc}`"


async def set_protocol(protocol: str) -> str:
    """Set the VPN protocol (e.g. lightway_udp, lightway_tcp, auto)."""
    try:
        rc, out, err = await _exec(["expressvpn", "protocol", protocol])
        if rc != 0:
            logger.error("protocol set(%s) failed (rc=%d): %s", protocol, rc, err)
            return f"❌ *Failed to set protocol*\n`{err or out}`"
        return f"✅ *Protocol set to* `{protocol}`\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("set_protocol error")
        return f"❌ *Error:* `{exc}`"


# ── Diagnostics ──────────────────────────────────────────────────────────────

async def get_diagnostics() -> str:
    """Return expressvpn diagnostics output."""
    try:
        rc, out, err = await _exec(["expressvpn", "diagnostics"])
        if rc != 0:
            logger.error("diagnostics failed (rc=%d): %s", rc, err)
            return f"❌ *Diagnostics error*\n`{err or out}`"
        return f"🔧 *Diagnostics*\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("get_diagnostics error")
        return f"❌ *Error:* `{exc}`"


# ── Preferences ──────────────────────────────────────────────────────────────

async def get_preferences() -> str:
    """Return all ExpressVPN preferences."""
    try:
        rc, out, err = await _exec(["expressvpn", "preferences"])
        if rc != 0:
            logger.error("preferences failed (rc=%d): %s", rc, err)
            return f"❌ *Error getting preferences*\n`{err or out}`"
        return f"⚙️ *Preferences*\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("get_preferences error")
        return f"❌ *Error:* `{exc}`"


async def set_preference(key: str, value: str) -> str:
    """Set a specific ExpressVPN preference."""
    try:
        rc, out, err = await _exec(["expressvpn", "preferences", "set", key, value])
        if rc != 0:
            logger.error("preference set(%s=%s) failed (rc=%d): %s", key, value, rc, err)
            return f"❌ *Failed to set preference*\n`{err or out}`"
        return f"✅ *Preference updated*\n🔑 `{key}` → `{value}`\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("set_preference error")
        return f"❌ *Error:* `{exc}`"


# ── Refresh Servers ──────────────────────────────────────────────────────────

async def refresh_servers() -> str:
    """Refresh the ExpressVPN server list."""
    try:
        rc, out, err = await _exec(["expressvpn", "refresh"])
        if rc != 0:
            logger.error("refresh failed (rc=%d): %s", rc, err)
            return f"❌ *Refresh failed*\n`{err or out}`"
        return f"🔃 *Server list refreshed*\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("refresh_servers error")
        return f"❌ *Error:* `{exc}`"


# ── Cipher ───────────────────────────────────────────────────────────────────

async def set_cipher(cipher: str) -> str:
    """Set the Lightway cipher (aes, chacha20, auto)."""
    try:
        rc, out, err = await _exec(
            ["expressvpn", "preferences", "set", "lightway_cipher", cipher]
        )
        if rc != 0:
            logger.error("cipher set(%s) failed (rc=%d): %s", cipher, rc, err)
            return f"❌ *Failed to set cipher*\n`{err or out}`"
        return f"🔐 *Cipher set to* `{cipher}`\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("set_cipher error")
        return f"❌ *Error:* `{exc}`"


# ── Auto-Connect ─────────────────────────────────────────────────────────────

async def get_autoconnect() -> str:
    """Get the current auto-connect setting from preferences."""
    try:
        rc, out, err = await _exec(["expressvpn", "preferences"])
        if rc != 0:
            return f"❌ *Error reading preferences*\n`{err or out}`"

        for line in out.splitlines():
            if "auto_connect" in line.lower():
                return f"🔄 *Auto-Connect:* `{line.strip()}`"

        return "🔄 *Auto-Connect:* `not found in preferences`"
    except Exception as exc:
        logger.exception("get_autoconnect error")
        return f"❌ *Error:* `{exc}`"


async def set_autoconnect(enabled: bool) -> str:
    """Enable or disable auto-connect."""
    value = "true" if enabled else "false"
    try:
        rc, out, err = await _exec(["expressvpn", "autoconnect", value])
        if rc != 0:
            logger.error("autoconnect set(%s) failed (rc=%d): %s", value, rc, err)
            return f"❌ *Failed to set auto-connect*\n`{err or out}`"
        emoji = "✅" if enabled else "⭕"
        state = "enabled" if enabled else "disabled"
        return f"{emoji} *Auto-Connect {state}*\n\n```\n{out}\n```"
    except Exception as exc:
        logger.exception("set_autoconnect error")
        return f"❌ *Error:* `{exc}`"


# ── Logout ───────────────────────────────────────────────────────────────────

async def logout() -> str:
    """Logout from ExpressVPN. ⚠️ WARNING: This deactivates the device!"""
    try:
        rc, out, err = await _exec(["expressvpn", "logout"])
        if rc != 0:
            logger.error("logout failed (rc=%d): %s", rc, err)
            return f"❌ *Logout failed*\n`{err or out}`"
        return (
            "⚠️ *Logged out from ExpressVPN*\n\n"
            "🚨 The device has been deactivated.\n"
            "You will need to re-activate with an activation code.\n\n"
            f"```\n{out}\n```"
        )
    except Exception as exc:
        logger.exception("logout error")
        return f"❌ *Error:* `{exc}`"


# ── Speed Test ───────────────────────────────────────────────────────────────

async def speed_test() -> str:
    """Run a speed test inside the container. May take 30+ seconds."""
    try:
        rc, out, err = await _exec(
            ["speedtest-cli", "--json"],
            timeout=90,  # Speed tests can be slow
        )
        if rc != 0:
            logger.error("speed test failed (rc=%d): %s", rc, err)
            return f"❌ *Speed test failed*\n`{err or out}`"

        try:
            data = json.loads(out)
            download = data.get("download", 0) / 1_000_000  # bps → Mbps
            upload = data.get("upload", 0) / 1_000_000
            ping = data.get("ping", 0)
            server_name = data.get("server", {}).get("name", "Unknown")
            server_country = data.get("server", {}).get("country", "")
            isp = data.get("client", {}).get("isp", "Unknown")

            return (
                "🚀 *Speed Test Results*\n\n"
                f"📥 *Download:* `{download:.1f} Mbps`\n"
                f"📤 *Upload:* `{upload:.1f} Mbps`\n"
                f"🏓 *Ping:* `{ping:.0f} ms`\n\n"
                f"🖥 *Server:* `{server_name}, {server_country}`\n"
                f"🏢 *ISP:* `{isp}`"
            )
        except (json.JSONDecodeError, KeyError):
            return f"🚀 *Speed Test*\n\n```\n{out}\n```"

    except Exception as exc:
        logger.exception("speed_test error")
        return f"❌ *Error:* `{exc}`"


# ── Mode Switch ──────────────────────────────────────────────────────────────

async def switch_mode(mode: str) -> str:
    """Switch between VPN and direct mode using switch-mode.sh."""
    if mode not in ("vpn", "direct"):
        return "❌ *Invalid mode.* Use `vpn` or `direct`."
    try:
        rc, out, err = await _exec(
            ["/usr/local/bin/switch-mode.sh", mode],
            timeout=30,
        )
        if rc != 0:
            logger.error("switch_mode(%s) failed (rc=%d): %s", mode, rc, err)
            return f"❌ *Mode switch failed*\n`{err or out}`"

        if mode == "vpn":
            return (
                "🔒 *Mode: Full VPN*\n\n"
                "All traffic is now routed through ExpressVPN.\n\n"
                f"```\n{out}\n```"
            )
        else:
            return (
                "⚡ *Mode: Direct + AdGuard*\n\n"
                "Traffic bypasses VPN, only AdGuard DNS filtering active.\n\n"
                f"```\n{out}\n```"
            )
    except Exception as exc:
        logger.exception("switch_mode error")
        return f"❌ *Error:* `{exc}`"


async def get_current_mode() -> str:
    """Read the current mode from the container."""
    try:
        rc, out, err = await _exec(["cat", "/tmp/current_mode"])
        if rc != 0:
            logger.error("get_current_mode failed (rc=%d): %s", rc, err)
            return "unknown"
        mode = out.strip().lower()
        return mode if mode in ("vpn", "direct") else "unknown"
    except Exception as exc:
        logger.exception("get_current_mode error")
        return "unknown"
