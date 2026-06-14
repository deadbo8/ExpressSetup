"""Inline keyboard builders for the ExpressVPN Telegram bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ── Helpers ──────────────────────────────────────────────────────────────────

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


def _rows_of_two(buttons: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    """Chunk a flat button list into rows of 2."""
    return [buttons[i : i + 2] for i in range(0, len(buttons), 2)]


def _rows_of_four(buttons: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    """Chunk a flat button list into rows of 4."""
    return [buttons[i : i + 4] for i in range(0, len(buttons), 4)]


# ── Main Menu ────────────────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    """Main control panel."""
    keyboard = [
        [_btn("📊 Status", "action:status"), _btn("🌐 My IP", "action:ip")],
        [_btn("🔗 Connect", "action:connect"), _btn("🔌 Disconnect", "action:disconnect")],
        [_btn("🔄 Reconnect", "action:reconnect"), _btn("⚡ Protocol", "action:protocol")],
        [_btn("🗺 Servers", "action:servers"), _btn("🔧 Diagnostics", "action:diagnostics")],
        [_btn("🛡️ AdGuard", "action:adguard"), _btn("🔀 VPN Mode", "action:mode")],
        [_btn("⚙️ Preferences", "action:preferences"), _btn("🚀 Speed Test", "action:speed")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── Region Selection ─────────────────────────────────────────────────────────

def regions_menu() -> InlineKeyboardMarkup:
    """Region selection menu."""
    keyboard = [
        [_btn("🌎 Americas", "region:americas")],
        [_btn("🌍 Europe", "region:europe")],
        [_btn("🌏 Asia Pacific", "region:asia_pacific")],
        [_btn("🔙 Back to Menu", "back:menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── Americas Servers ─────────────────────────────────────────────────────────

def americas_servers() -> InlineKeyboardMarkup:
    """Popular Americas server locations."""
    buttons = [
        _btn("🇺🇸 USA - New York", "connect:usa-new-york"),
        _btn("🇺🇸 USA - Los Angeles", "connect:usa-los-angeles-1"),
        _btn("🇺🇸 USA - Chicago", "connect:usa-chicago"),
        _btn("🇺🇸 USA - Miami", "connect:usa-miami"),
        _btn("🇺🇸 USA - Dallas", "connect:usa-dallas"),
        _btn("🇺🇸 USA - San Francisco", "connect:usa-san-francisco"),
        _btn("🇺🇸 USA - Washington DC", "connect:usa-washington-dc"),
        _btn("🇺🇸 USA - Atlanta", "connect:usa-atlanta"),
        _btn("🇨🇦 Canada - Toronto", "connect:canada-toronto"),
        _btn("🇨🇦 Canada - Montreal", "connect:canada-montreal"),
        _btn("🇧🇷 Brazil", "connect:brazil"),
        _btn("🇲🇽 Mexico", "connect:mexico"),

        _btn("🇦🇷 Argentina", "connect:argentina"),
        _btn("🇨🇱 Chile", "connect:chile"),
        _btn("🇨🇴 Colombia", "connect:colombia"),
        _btn("🇵🇪 Peru", "connect:peru"),
        _btn("🇪🇨 Ecuador", "connect:ecuador"),
        _btn("🇻🇪 Venezuela", "connect:venezuela"),
        _btn("🇺🇾 Uruguay", "connect:uruguay"),
        _btn("🇵🇦 Panama", "connect:panama"),
        _btn("🇨🇷 Costa Rica", "connect:costa-rica"),
    ]

    rows = _rows_of_two(buttons)
    rows.append([_btn("🔙 Back to Regions", "back:regions")])
    return InlineKeyboardMarkup(rows)


# ── Europe Servers ───────────────────────────────────────────────────────────

def europe_servers() -> InlineKeyboardMarkup:
    """Popular Europe server locations."""
    buttons = [
        _btn("🇬🇧 UK - London", "connect:uk-london"),
        _btn("🇬🇧 UK - Docklands", "connect:uk-docklands"),
        _btn("🇩🇪 Germany - Frankfurt", "connect:germany-frankfurt-1"),
        _btn("🇫🇷 France - Paris", "connect:france-paris-1"),
        _btn("🇳🇱 Netherlands", "connect:netherlands-amsterdam"),
        _btn("🇨🇭 Switzerland", "connect:switzerland"),
        _btn("🇪🇸 Spain", "connect:spain-madrid"),
        _btn("🇮🇹 Italy - Milan", "connect:italy-milan"),
        _btn("🇸🇪 Sweden", "connect:sweden"),
        _btn("🇳🇴 Norway", "connect:norway"),

        _btn("🇷🇸 Serbia", "connect:serbia"),
        _btn("🇺🇦 Ukraine", "connect:ukraine"),
        _btn("🇷🇴 Romania", "connect:romania"),
        _btn("🇵🇱 Poland", "connect:poland"),
        _btn("🇨🇿 Czechia", "connect:czech-republic"),
        _btn("🇭🇺 Hungary", "connect:hungary"),
        _btn("🇬🇷 Greece", "connect:greece"),
        _btn("🇵🇹 Portugal", "connect:portugal"),
        _btn("🇮🇪 Ireland", "connect:ireland"),
        _btn("🇫🇮 Finland", "connect:finland"),
        _btn("🇩🇰 Denmark", "connect:denmark"),
        _btn("🇦🇹 Austria", "connect:austria"),
        _btn("🇧🇪 Belgium", "connect:belgium"),
        _btn("🇹🇷 Turkey", "connect:turkey"),
    ]

    rows = _rows_of_two(buttons)
    rows.append([_btn("🔙 Back to Regions", "back:regions")])
    return InlineKeyboardMarkup(rows)


# ── Asia-Pacific Servers ─────────────────────────────────────────────────────

def asia_pacific_servers() -> InlineKeyboardMarkup:
    """Popular Asia-Pacific + Middle East + Africa server locations."""
    buttons = [
        _btn("🇯🇵 Japan - Tokyo", "connect:japan-tokyo"),
        _btn("🇸🇬 Singapore", "connect:singapore-jurong"),
        _btn("🇦🇺 Australia - Sydney", "connect:australia-sydney"),
        _btn("🇮🇳 India (via SG)", "connect:india-(via-singapore)"),
        _btn("🇮🇳 India (via UK)", "connect:india-(via-uk)"),
        _btn("🇭🇰 Hong Kong", "connect:hong-kong-2"),
        _btn("🇰🇷 South Korea", "connect:south-korea-2"),
        _btn("🇹🇭 Thailand", "connect:thailand"),

        _btn("🇳🇿 New Zealand", "connect:new-zealand"),
        _btn("🇹🇼 Taiwan", "connect:taiwan-3"),
        _btn("🇵🇭 Philippines", "connect:philippines"),
        _btn("🇮🇩 Indonesia", "connect:indonesia"),
        _btn("🇲🇾 Malaysia", "connect:malaysia"),
        _btn("🇻🇳 Vietnam", "connect:vietnam"),
        _btn("🇵🇰 Pakistan", "connect:pakistan"),
        _btn("🇰🇿 Kazakhstan", "connect:kazakhstan"),
        _btn("🇺🇿 Uzbekistan", "connect:uzbekistan"),
        _btn("🇬🇪 Georgia", "connect:georgia"),
        _btn("🇦🇲 Armenia", "connect:armenia"),
        _btn("🇦🇿 Azerbaijan", "connect:azerbaijan"),
        _btn("🇶🇦 Qatar", "connect:qatar"),
        _btn("🇨🇾 Cyprus", "connect:cyprus"),
        _btn("🇲🇹 Malta", "connect:malta"),

        _btn("🇿🇦 South Africa", "connect:south-africa"),
        _btn("🇰🇪 Kenya", "connect:kenya"),
        _btn("🇳🇬 Nigeria", "connect:nigeria"),
        _btn("🇬🇭 Ghana", "connect:ghana"),
        _btn("🇲🇦 Morocco", "connect:morocco"),
        _btn("🇩🇿 Algeria", "connect:algeria"),
        _btn("🇪🇬 Egypt", "connect:egypt"),
        _btn("🇦🇪 UAE", "connect:united-arab-emirates"),
        _btn("🇸🇦 Saudi Arabia", "connect:saudi-arabia"),
        _btn("🇮🇱 Israel", "connect:israel"),
    ]
    rows = _rows_of_two(buttons)
    rows.append([_btn("🔙 Back to Regions", "back:regions")])
    return InlineKeyboardMarkup(rows)


# ── Protocol Menu ────────────────────────────────────────────────────────────

def protocol_menu() -> InlineKeyboardMarkup:
    """Protocol selection menu."""
    keyboard = [
        [_btn("⚡ Lightway UDP (Fastest)", "protocol:lightway_udp")],
        [_btn("🔒 Lightway TCP", "protocol:lightway_tcp")],
        [_btn("🔄 Auto", "protocol:auto")],
        [_btn("🔙 Back to Menu", "back:menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── Disconnect Confirmation ──────────────────────────────────────────────────

def confirm_disconnect() -> InlineKeyboardMarkup:
    """Disconnect confirmation prompt."""
    keyboard = [
        [
            _btn("✅ Yes, Disconnect", "confirm_disconnect:yes"),
            _btn("❌ Cancel", "confirm_disconnect:no"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── AdGuard Menu ─────────────────────────────────────────────────────────────

def adguard_menu() -> InlineKeyboardMarkup:
    """AdGuard Home control panel."""
    keyboard = [
        [_btn("🛡️ Toggle Protection", "adguard:toggle")],
        [_btn("📊 Stats", "adguard:stats"), _btn("📋 Query Log", "adguard:querylog")],
        [_btn("🔒 Safe Browsing", "adguard:safebrowsing"), _btn("👨‍👧 Parental Control", "adguard:parental")],
        [_btn("🚫 Block Services", "adguard:services")],
        [_btn("🔙 Back to Menu", "back:menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── Blocked Services Menu ───────────────────────────────────────────────────

def blocked_services_menu() -> InlineKeyboardMarkup:
    """Service blocking toggles."""
    buttons = [
        _btn("📱 TikTok", "service:tiktok"),
        _btn("📘 Facebook", "service:facebook"),
        _btn("📸 Instagram", "service:instagram"),
        _btn("🎵 Spotify", "service:spotify"),
        _btn("🐦 Twitter/X", "service:twitter"),
        _btn("📺 YouTube", "service:youtube"),
        _btn("👻 Snapchat", "service:snapchat"),
        _btn("💬 WhatsApp", "service:whatsapp"),
        _btn("🎮 Twitch", "service:twitch"),
        _btn("📌 Pinterest", "service:pinterest"),
        _btn("💼 LinkedIn", "service:linkedin"),
        _btn("🎬 Netflix", "service:netflix"),
    ]
    rows = _rows_of_four(buttons)
    rows.append([_btn("🔙 Back to AdGuard", "back:adguard")])
    return InlineKeyboardMarkup(rows)


# ── Mode Menu ────────────────────────────────────────────────────────────────

def mode_menu() -> InlineKeyboardMarkup:
    """VPN mode selection."""
    keyboard = [
        [_btn("🔒 Full VPN (ExpressVPN)", "mode:vpn")],
        [_btn("⚡ Direct + AdGuard Only", "mode:direct")],
        [_btn("🔙 Back to Menu", "back:menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── Preferences Menu ────────────────────────────────────────────────────────

def preferences_menu() -> InlineKeyboardMarkup:
    """ExpressVPN preferences panel."""
    keyboard = [
        [_btn("⚡ Protocol", "pref:protocol"), _btn("🔐 Cipher", "pref:cipher")],
        [_btn("🔄 Auto-Connect", "pref:autoconnect"), _btn("🔃 Refresh Servers", "pref:refresh")],
        [_btn("📋 View All Preferences", "pref:view")],
        [_btn("🔙 Back to Menu", "back:menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── Cipher Menu ──────────────────────────────────────────────────────────────

def cipher_menu() -> InlineKeyboardMarkup:
    """Lightway cipher selection."""
    keyboard = [
        [_btn("🔐 AES-256", "cipher:aes")],
        [_btn("🚀 ChaCha20", "cipher:chacha20")],
        [_btn("🔄 Auto", "cipher:auto")],
        [_btn("🔙 Back to Preferences", "back:preferences")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── Logout Confirmation ─────────────────────────────────────────────────────

def confirm_logout() -> InlineKeyboardMarkup:
    """Dangerous action confirmation for logout."""
    keyboard = [
        [_btn("⚠️ Yes, LOGOUT (deactivates device)", "logout:yes")],
        [_btn("❌ Cancel", "logout:no")],
    ]
    return InlineKeyboardMarkup(keyboard)
