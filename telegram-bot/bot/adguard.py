"""AdGuard Home REST API client."""

import httpx
import logging
from .config import ADGUARD_URL, ADGUARD_USER, ADGUARD_PASS

logger = logging.getLogger(__name__)


async def _request(method: str, path: str, json=None) -> dict | str:
    """Make an authenticated request to AdGuard Home API."""
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method, f"{ADGUARD_URL}/control{path}",
            auth=(ADGUARD_USER, ADGUARD_PASS),
            json=json, timeout=10,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return resp.text


# ── Status ───────────────────────────────────────────────────────────────────

async def get_status() -> str:
    """Get AdGuard Home status with emoji formatting."""
    try:
        data = await _request("GET", "/status")
        if isinstance(data, str):
            return f"❌ *Unexpected response*\n`{data}`"

        protection = "🟢 ON" if data.get("protection_enabled") else "🔴 OFF"
        version = data.get("version", "unknown")
        dns_port = data.get("dns_port", "unknown")

        return (
            "🛡️ *AdGuard Home Status*\n\n"
            f"🔰 *Protection:* {protection}\n"
            f"📦 *Version:* `{version}`\n"
            f"🔌 *DNS Port:* `{dns_port}`\n"
        )
    except httpx.HTTPStatusError as exc:
        logger.error("AdGuard status HTTP error: %s", exc)
        return f"❌ *AdGuard API error:* `{exc.response.status_code}`"
    except Exception as exc:
        logger.exception("AdGuard get_status error")
        return f"❌ *Error:* `{exc}`"


async def get_status_raw() -> dict:
    """Get raw AdGuard status dict (for internal use)."""
    try:
        data = await _request("GET", "/status")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# ── Protection Toggle ────────────────────────────────────────────────────────

async def toggle_protection(enabled: bool) -> str:
    """Enable or disable AdGuard Home protection."""
    try:
        await _request("POST", "/dns_config", json={
            "protection_enabled": enabled,
        })
        state = "🟢 enabled" if enabled else "🔴 disabled"
        return f"🛡️ *Protection {state}*"
    except httpx.HTTPStatusError as exc:
        logger.error("AdGuard toggle protection HTTP error: %s", exc)
        return f"❌ *Failed to toggle protection:* `{exc.response.status_code}`"
    except Exception as exc:
        logger.exception("toggle_protection error")
        return f"❌ *Error:* `{exc}`"


# ── Statistics ───────────────────────────────────────────────────────────────

async def get_stats() -> str:
    """Get AdGuard Home statistics."""
    try:
        data = await _request("GET", "/stats")
        if isinstance(data, str):
            return f"❌ *Unexpected response*\n`{data}`"

        total = data.get("num_dns_queries", 0)
        blocked = data.get("num_blocked_filtering", 0)
        malware = data.get("num_replaced_safebrowsing", 0)
        parental = data.get("num_replaced_parental", 0)
        pct = (blocked / total * 100) if total > 0 else 0

        # Top blocked domains
        top_blocked = data.get("top_blocked_domains", [])
        top_list = ""
        for i, entry in enumerate(top_blocked[:5], 1):
            if isinstance(entry, dict):
                for domain, count in entry.items():
                    top_list += f"  {i}. `{domain}` — {count}\n"

        result = (
            "📊 *AdGuard Home Statistics*\n\n"
            f"🔍 *Total queries:* `{total:,}`\n"
            f"🚫 *Blocked:* `{blocked:,}` ({pct:.1f}%)\n"
            f"🦠 *Malware blocked:* `{malware:,}`\n"
            f"👨‍👧 *Parental blocked:* `{parental:,}`\n"
        )

        if top_list:
            result += f"\n🏆 *Top Blocked Domains:*\n{top_list}"

        return result
    except httpx.HTTPStatusError as exc:
        logger.error("AdGuard stats HTTP error: %s", exc)
        return f"❌ *AdGuard API error:* `{exc.response.status_code}`"
    except Exception as exc:
        logger.exception("get_stats error")
        return f"❌ *Error:* `{exc}`"


# ── Query Log ────────────────────────────────────────────────────────────────

async def get_query_log(limit: int = 10) -> str:
    """Get recent DNS queries from the query log."""
    try:
        data = await _request("GET", f"/querylog?limit={limit}")
        if isinstance(data, str):
            return f"❌ *Unexpected response*\n`{data}`"

        entries = data.get("data", [])
        if not entries:
            return "📋 *Query Log:* No recent queries."

        lines = []
        for entry in entries[:limit]:
            question = entry.get("question", {})
            name = question.get("name", "unknown")
            qtype = question.get("type", "?")
            reason = entry.get("reason", "")
            client = entry.get("client", "?")

            # Determine emoji based on reason
            if "Filtered" in reason or "Blocked" in reason:
                emoji = "🚫"
            else:
                emoji = "✅"

            lines.append(f"{emoji} `{name}` ({qtype}) — {client}")

        result = "📋 *Recent DNS Queries*\n\n" + "\n".join(lines)
        return result
    except httpx.HTTPStatusError as exc:
        logger.error("AdGuard querylog HTTP error: %s", exc)
        return f"❌ *AdGuard API error:* `{exc.response.status_code}`"
    except Exception as exc:
        logger.exception("get_query_log error")
        return f"❌ *Error:* `{exc}`"


# ── Safe Browsing ────────────────────────────────────────────────────────────

async def toggle_safe_browsing(enabled: bool) -> str:
    """Enable or disable safe browsing."""
    try:
        action = "enable" if enabled else "disable"
        await _request("POST", f"/safebrowsing/{action}")
        state = "🟢 enabled" if enabled else "🔴 disabled"
        return f"🔒 *Safe Browsing {state}*"
    except httpx.HTTPStatusError as exc:
        logger.error("Safe browsing toggle HTTP error: %s", exc)
        return f"❌ *Failed:* `{exc.response.status_code}`"
    except Exception as exc:
        logger.exception("toggle_safe_browsing error")
        return f"❌ *Error:* `{exc}`"


# ── Parental Control ─────────────────────────────────────────────────────────

async def toggle_parental(enabled: bool) -> str:
    """Enable or disable parental control."""
    try:
        action = "enable" if enabled else "disable"
        await _request("POST", f"/parental/{action}")
        state = "🟢 enabled" if enabled else "🔴 disabled"
        return f"👨‍👧 *Parental Control {state}*"
    except httpx.HTTPStatusError as exc:
        logger.error("Parental toggle HTTP error: %s", exc)
        return f"❌ *Failed:* `{exc.response.status_code}`"
    except Exception as exc:
        logger.exception("toggle_parental error")
        return f"❌ *Error:* `{exc}`"


# ── Blocked Services ─────────────────────────────────────────────────────────

async def get_blocked_services() -> list:
    """Get the list of currently blocked services."""
    try:
        data = await _request("GET", "/blocked_services/list")
        if isinstance(data, list):
            return data
        return []
    except Exception as exc:
        logger.exception("get_blocked_services error")
        return []


async def set_blocked_services(services: list) -> str:
    """Set the list of blocked services."""
    try:
        await _request("POST", "/blocked_services/set", json=services)
        if services:
            svc_list = ", ".join(f"`{s}`" for s in services)
            return f"🚫 *Blocked services updated:*\n{svc_list}"
        else:
            return "✅ *All services unblocked*"
    except httpx.HTTPStatusError as exc:
        logger.error("Set blocked services HTTP error: %s", exc)
        return f"❌ *Failed:* `{exc.response.status_code}`"
    except Exception as exc:
        logger.exception("set_blocked_services error")
        return f"❌ *Error:* `{exc}`"
