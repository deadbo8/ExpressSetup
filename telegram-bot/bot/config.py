"""Configuration loaded from environment variables."""

import os

# --- Telegram Bot Token (required) ---
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError(
        "TELEGRAM_BOT_TOKEN environment variable is required but not set."
    )

# --- Allowed Telegram User IDs (required) ---
_raw_ids = os.environ.get("ALLOWED_USER_IDS", "")
if not _raw_ids:
    raise ValueError(
        "ALLOWED_USER_IDS environment variable is required but not set. "
        "Provide a comma-separated list of Telegram user IDs."
    )
ALLOWED_USER_IDS: set[int] = {int(uid.strip()) for uid in _raw_ids.split(",") if uid.strip()}

# --- ExpressVPN Docker container name ---
EXPRESSVPN_CONTAINER: str = os.environ.get("EXPRESSVPN_CONTAINER", "expressvpn")

# --- AdGuard Home ---
ADGUARD_URL: str = os.environ.get("ADGUARD_URL", "http://expressvpn:3000")
ADGUARD_USER: str = os.environ.get("ADGUARD_USER", "admin")
ADGUARD_PASS: str = os.environ.get("ADGUARD_PASS", "admin")

# --- Dashboard ---
DASHBOARD_PIN: str = os.environ.get("DASHBOARD_PIN", "123456")
API_PORT: int = int(os.environ.get("API_PORT", "8080"))

# --- JWT ---
JWT_SECRET: str = os.environ.get("JWT_SECRET", TELEGRAM_BOT_TOKEN)

# --- Logging level ---
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
