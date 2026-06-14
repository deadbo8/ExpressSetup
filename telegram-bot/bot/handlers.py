"""Telegram command & callback handlers for the ExpressVPN bot."""

import logging
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from . import vpn, adguard
from .config import ALLOWED_USER_IDS
from .keyboards import (
    main_menu,
    regions_menu,
    americas_servers,
    europe_servers,
    asia_pacific_servers,
    protocol_menu,
    confirm_disconnect,
    adguard_menu,
    blocked_services_menu,
    mode_menu,
    preferences_menu,
    cipher_menu,
    confirm_logout,
)

logger = logging.getLogger(__name__)


# ── Access Control ───────────────────────────────────────────────────────────

def restricted(func):
    """Decorator that blocks unauthorised Telegram users."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USER_IDS:
            text = "⛔ *Access Denied*\n\nYou are not authorized to use this bot."
            if update.callback_query:
                await update.callback_query.answer(text, show_alert=True)
            else:
                await update.message.reply_text(text, parse_mode="Markdown")
            logger.warning("Unauthorized access attempt by user %s", user_id)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


# ── /start ───────────────────────────────────────────────────────────────────

@restricted
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome banner and main menu."""
    text = (
        "🛡️ *ExpressVPN Gateway Controller*\n"
        "\n"
        "Welcome! I'm your personal VPN & network control bot.\n"
        "Use the panel below to manage your VPN, AdGuard DNS,\n"
        "and network routing mode."
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())


# ── /help ────────────────────────────────────────────────────────────────────

@restricted
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available commands."""
    text = (
        "📖 *Available Commands*\n"
        "\n"
        "/start — Launch the control panel\n"
        "/menu — Show the main menu\n"
        "/status — Current VPN status & IP\n"
        "/adguard — AdGuard Home controls\n"
        "/mode — Switch VPN/Direct mode\n"
        "/speed — Run a speed test\n"
        "/preferences — ExpressVPN preferences\n"
        "/help — This help message\n"
        "\n"
        "You can also use the inline buttons for quick access."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── /status ──────────────────────────────────────────────────────────────────

@restricted
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show VPN status and public IP."""
    status = await vpn.get_status()
    ip_info = await vpn.get_public_ip()
    mode = await vpn.get_current_mode()
    mode_emoji = "🔒 VPN" if mode == "vpn" else "⚡ Direct" if mode == "direct" else "❓ Unknown"
    text = f"{status}\n\n{ip_info}\n🔀 *Mode:* {mode_emoji}"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())


# ── /menu ────────────────────────────────────────────────────────────────────

@restricted
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the main menu keyboard."""
    text = "🛡️ *ExpressVPN Control Panel*\n\nChoose an action:"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())


# ── /adguard ─────────────────────────────────────────────────────────────────

@restricted
async def adguard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show AdGuard Home status and menu."""
    status = await adguard.get_status()
    await update.message.reply_text(status, parse_mode="Markdown", reply_markup=adguard_menu())


# ── /mode ────────────────────────────────────────────────────────────────────

@restricted
async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current routing mode and selection menu."""
    mode = await vpn.get_current_mode()
    mode_emoji = "🔒 Full VPN" if mode == "vpn" else "⚡ Direct + AdGuard" if mode == "direct" else "❓ Unknown"
    text = f"🔀 *Current Mode:* {mode_emoji}\n\nSelect a mode:"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=mode_menu())


# ── /speed ───────────────────────────────────────────────────────────────────

@restricted
async def speed_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run a speed test with loading indicator."""
    msg = await update.message.reply_text(
        "⏳ *Running speed test…*\n\nThis may take 30-60 seconds.",
        parse_mode="Markdown",
    )
    result = await vpn.speed_test()
    await msg.edit_text(result, parse_mode="Markdown", reply_markup=main_menu())


# ── /preferences ─────────────────────────────────────────────────────────────

@restricted
async def preferences_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show ExpressVPN preferences and menu."""
    prefs = await vpn.get_preferences()
    await update.message.reply_text(prefs, parse_mode="Markdown", reply_markup=preferences_menu())


# ── Callback Query Router ───────────────────────────────────────────────────


async def _reply_new(query, text, reply_markup=None):
    """Remove keyboard from old message and send a new one."""
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    return await query.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup, quote=False)

@restricted
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route all inline-keyboard button presses."""
    query = update.callback_query
    await query.answer()  # dismiss the spinner immediately

    data = query.data or ""

    # ── actions ──────────────────────────────────────────────────────────
    if data == "action:status":
        status = await vpn.get_status()
        ip_info = await vpn.get_public_ip()
        mode = await vpn.get_current_mode()
        mode_emoji = "🔒 VPN" if mode == "vpn" else "⚡ Direct" if mode == "direct" else "❓ Unknown"
        text = f"{status}\n\n{ip_info}\n🔀 *Mode:* {mode_emoji}"
        await _reply_new(query, text, parse_mode="Markdown", reply_markup=main_menu())

    elif data == "action:ip":
        ip_info = await vpn.get_public_ip()
        await _reply_new(query, ip_info, parse_mode="Markdown", reply_markup=main_menu())

    elif data == "action:connect":
        await _reply_new(query, 
            "🗺 *Select a Region*", parse_mode="Markdown", reply_markup=regions_menu()
        )

    elif data == "action:disconnect":
        await _reply_new(query, 
            "⚠️ *Are you sure you want to disconnect?*",
            parse_mode="Markdown",
            reply_markup=confirm_disconnect(),
        )

    elif data == "action:reconnect":
        msg = await _reply_new(query, "⏳ *Reconnecting…*", parse_mode="Markdown")
        result = await vpn.reconnect()
        await msg.edit_text( result, parse_mode="Markdown", reply_markup=main_menu())

    elif data == "action:protocol":
        proto = await vpn.get_protocol()
        text = f"{proto}\n\n🔧 *Select a protocol:*"
        await _reply_new(query, text, parse_mode="Markdown", reply_markup=protocol_menu())

    elif data == "action:servers":
        await _reply_new(query, 
            "🗺 *Select a Region*", parse_mode="Markdown", reply_markup=regions_menu()
        )

    elif data == "action:diagnostics":
        msg = await _reply_new(query, "⏳ *Running diagnostics…*", parse_mode="Markdown")
        result = await vpn.get_diagnostics()
        await msg.edit_text( result, parse_mode="Markdown", reply_markup=main_menu())

    # ── regions ──────────────────────────────────────────────────────────
    elif data == "region:americas":
        await _reply_new(query, 
            "🌎 *Americas Servers*", parse_mode="Markdown", reply_markup=americas_servers()
        )

    elif data == "region:europe":
        await _reply_new(query, 
            "🌍 *Europe Servers*", parse_mode="Markdown", reply_markup=europe_servers()
        )

    elif data == "region:asia_pacific":
        await _reply_new(query, 
            "🌏 *Asia Pacific Servers*", parse_mode="Markdown", reply_markup=asia_pacific_servers()
        )

    elif data == "region:back":
        await _reply_new(query, 
            "🛡️ *ExpressVPN Control Panel*\n\nChoose an action:",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )

    # ── connect to specific server ───────────────────────────────────────
    elif data.startswith("connect:"):
        alias = data.split(":", 1)[1]
        msg = await _reply_new(query, 
            f"⏳ *Connecting to* `{alias}`*…*", parse_mode="Markdown"
        )
        result = await vpn.connect(alias)
        await msg.edit_text(result, parse_mode="Markdown", reply_markup=main_menu())

    # ── protocol selection ───────────────────────────────────────────────
    elif data.startswith("protocol:"):
        proto = data.split(":", 1)[1]
        msg = await _reply_new(query, 
            f"⏳ *Setting protocol to* `{proto}`*…*", parse_mode="Markdown"
        )
        result = await vpn.set_protocol(proto)
        await msg.edit_text(result, parse_mode="Markdown", reply_markup=main_menu())

    # ── disconnect confirmation ──────────────────────────────────────────
    elif data == "confirm_disconnect:yes":
        msg = await _reply_new(query, "⏳ *Disconnecting…*", parse_mode="Markdown")
        result = await vpn.disconnect()
        await msg.edit_text( result, parse_mode="Markdown", reply_markup=main_menu())

    elif data == "confirm_disconnect:no":
        await _reply_new(query, 
            "🛡️ *ExpressVPN Control Panel*\n\nChoose an action:",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )

    # ── AdGuard controls ────────────────────────────────────────────────
    elif data == "action:adguard":
        status = await adguard.get_status()
        await _reply_new(query, status, parse_mode="Markdown", reply_markup=adguard_menu())

    elif data == "adguard:toggle":
        status_data = await adguard.get_status_raw()
        current = status_data.get("protection_enabled", True)
        result = await adguard.toggle_protection(not current)
        new_status = await adguard.get_status()
        text = f"{result}\n\n{new_status}"
        await _reply_new(query, text, parse_mode="Markdown", reply_markup=adguard_menu())

    elif data == "adguard:stats":
        stats = await adguard.get_stats()
        await _reply_new(query, stats, parse_mode="Markdown", reply_markup=adguard_menu())

    elif data == "adguard:querylog":
        log = await adguard.get_query_log()
        await _reply_new(query, log, parse_mode="Markdown", reply_markup=adguard_menu())

    elif data == "adguard:safebrowsing":
        # Toggle: check current state first
        status_data = await adguard.get_status_raw()
        # AdGuard doesn't return safe_browsing in status; just toggle on
        # We'll use a simple toggle approach
        result = await adguard.toggle_safe_browsing(True)
        await _reply_new(query, result, parse_mode="Markdown", reply_markup=adguard_menu())

    elif data == "adguard:parental":
        result = await adguard.toggle_parental(True)
        await _reply_new(query, result, parse_mode="Markdown", reply_markup=adguard_menu())

    elif data == "adguard:services":
        blocked = await adguard.get_blocked_services()
        if blocked:
            svc_list = ", ".join(f"`{s}`" for s in blocked)
            text = f"🚫 *Currently blocked:*\n{svc_list}\n\n_Tap a service to toggle it:_"
        else:
            text = "✅ *No services blocked*\n\n_Tap a service to block it:_"
        await _reply_new(query, text, parse_mode="Markdown", reply_markup=blocked_services_menu())

    # ── Service blocking ────────────────────────────────────────────────
    elif data.startswith("service:"):
        service = data.split(":", 1)[1]
        blocked = await adguard.get_blocked_services()
        if service in blocked:
            blocked.remove(service)
            action_text = f"✅ *Unblocked* `{service}`"
        else:
            blocked.append(service)
            action_text = f"🚫 *Blocked* `{service}`"
        await adguard.set_blocked_services(blocked)

        if blocked:
            svc_list = ", ".join(f"`{s}`" for s in blocked)
            text = f"{action_text}\n\n🚫 *Currently blocked:*\n{svc_list}"
        else:
            text = f"{action_text}\n\n✅ *No services blocked*"
        await _reply_new(query, text, parse_mode="Markdown", reply_markup=blocked_services_menu())

    # ── Mode switch ─────────────────────────────────────────────────────
    elif data == "action:mode":
        mode = await vpn.get_current_mode()
        mode_emoji = "🔒 Full VPN" if mode == "vpn" else "⚡ Direct + AdGuard" if mode == "direct" else "❓ Unknown"
        text = f"🔀 *Current Mode:* {mode_emoji}\n\nSelect a mode:"
        await _reply_new(query, text, parse_mode="Markdown", reply_markup=mode_menu())

    elif data.startswith("mode:"):
        mode = data.split(":", 1)[1]
        msg = await _reply_new(query, 
            f"⏳ *Switching to* `{mode}` *mode…*", parse_mode="Markdown"
        )
        result = await vpn.switch_mode(mode)
        await msg.edit_text(result, parse_mode="Markdown", reply_markup=main_menu())

    # ── Preferences ─────────────────────────────────────────────────────
    elif data == "action:preferences":
        prefs = await vpn.get_preferences()
        await _reply_new(query, prefs, parse_mode="Markdown", reply_markup=preferences_menu())

    elif data == "pref:protocol":
        proto = await vpn.get_protocol()
        text = f"{proto}\n\n🔧 *Select a protocol:*"
        await _reply_new(query, text, parse_mode="Markdown", reply_markup=protocol_menu())

    elif data == "pref:cipher":
        text = "🔐 *Select Lightway cipher:*"
        await _reply_new(query, text, parse_mode="Markdown", reply_markup=cipher_menu())

    elif data == "pref:autoconnect":
        # Toggle autoconnect
        current = await vpn.get_autoconnect()
        # Determine current state from the output
        is_enabled = "true" in current.lower()
        result = await vpn.set_autoconnect(not is_enabled)
        await _reply_new(query, result, parse_mode="Markdown", reply_markup=preferences_menu())

    elif data == "pref:refresh":
        msg = await _reply_new(query, "⏳ *Refreshing server list…*", parse_mode="Markdown")
        result = await vpn.refresh_servers()
        await msg.edit_text( result, parse_mode="Markdown", reply_markup=preferences_menu())

    elif data == "pref:view":
        prefs = await vpn.get_preferences()
        await _reply_new(query, prefs, parse_mode="Markdown", reply_markup=preferences_menu())

    # ── Cipher selection ────────────────────────────────────────────────
    elif data.startswith("cipher:"):
        cipher = data.split(":", 1)[1]
        msg = await _reply_new(query, 
            f"⏳ *Setting cipher to* `{cipher}`*…*", parse_mode="Markdown"
        )
        result = await vpn.set_cipher(cipher)
        await msg.edit_text(result, parse_mode="Markdown", reply_markup=preferences_menu())

    # ── Speed test ──────────────────────────────────────────────────────
    elif data == "action:speed":
        msg = await _reply_new(query, 
            "⏳ *Running speed test…*\n\nThis may take 30-60 seconds.",
            parse_mode="Markdown",
        )
        result = await vpn.speed_test()
        await msg.edit_text(result, parse_mode="Markdown", reply_markup=main_menu())

    # ── Logout ──────────────────────────────────────────────────────────
    elif data == "action:logout":
        text = (
            "⚠️ *DANGER: Logout*\n\n"
            "This will *deactivate this device* from your ExpressVPN account.\n"
            "You will need an activation code to re-activate.\n\n"
            "Are you sure?"
        )
        await _reply_new(query, text, parse_mode="Markdown", reply_markup=confirm_logout())

    elif data == "logout:yes":
        msg = await _reply_new(query, "⏳ *Logging out…*", parse_mode="Markdown")
        result = await vpn.logout()
        await msg.edit_text( result, parse_mode="Markdown", reply_markup=main_menu())

    elif data == "logout:no":
        await _reply_new(query, 
            "🛡️ *ExpressVPN Control Panel*\n\nChoose an action:",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )

    # ── back navigation ──────────────────────────────────────────────────
    elif data == "back:menu":
        await _reply_new(query, 
            "🛡️ *ExpressVPN Control Panel*\n\nChoose an action:",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )

    elif data == "back:regions":
        await _reply_new(query, 
            "🗺 *Select a Region*", parse_mode="Markdown", reply_markup=regions_menu()
        )

    elif data == "back:adguard":
        status = await adguard.get_status()
        await _reply_new(query, status, parse_mode="Markdown", reply_markup=adguard_menu())

    elif data == "back:preferences":
        prefs = await vpn.get_preferences()
        await _reply_new(query, prefs, parse_mode="Markdown", reply_markup=preferences_menu())

    else:
        logger.warning("Unhandled callback data: %s", data)
        await _reply_new(query, 
            "❓ Unknown action.", parse_mode="Markdown", reply_markup=main_menu()
        )


# ── Global Error Handler ────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and try to notify the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ *An unexpected error occurred.* Please try again.",
                parse_mode="Markdown",
            )
        except Exception:
            logger.exception("Failed to send error notification to user")
