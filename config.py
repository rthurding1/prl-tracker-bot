"""Configuration loaded from environment variables (.env supported)."""
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional in production where env vars are set directly
    pass


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    # allow underscores like 25_000_000
    return int(raw.replace("_", "").strip())


# --- Telegram ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Optional: chat id auto-subscribed on startup (your own DM). Comma-separated allowed.
_default_chats = os.getenv("TELEGRAM_CHAT_ID", "").strip()
DEFAULT_CHAT_IDS = [c.strip() for c in _default_chats.split(",") if c.strip()]

# --- Token / market ---
COINGECKO_ID = os.getenv("COINGECKO_ID", "perle").strip()
# Optional free CoinGecko demo key (raises rate limits on shared cloud IPs).
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "").strip()
# Max supply used to derive FDV as a fallback when CoinGecko is unavailable.
MAX_SUPPLY = float(os.getenv("MAX_SUPPLY", "1000000000").replace("_", ""))
# Perp symbols per exchange (OI is combined across all three).
BINANCE_SYMBOL = os.getenv("BINANCE_SYMBOL", "PRLUSDT").strip()
BYBIT_SYMBOL = os.getenv("BYBIT_SYMBOL", "PRLUSDT").strip()
BITGET_SYMBOL = os.getenv("BITGET_SYMBOL", "PRLUSDT").strip()
BITGET_PRODUCT_TYPE = os.getenv("BITGET_PRODUCT_TYPE", "usdt-futures").strip()

# --- Alerting behaviour ---
FDV_INCREMENT = _int("FDV_INCREMENT", 25_000_000)  # alert each time FDV crosses this
COOLDOWN_SECONDS = _int("COOLDOWN_SECONDS", 3600)   # min gap between FDV alerts (1h)
POLL_INTERVAL_SECONDS = _int("POLL_INTERVAL_SECONDS", 60)

# --- State persistence ---
STATE_FILE = os.getenv("STATE_FILE", "state.json").strip()


def validate() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set. Create a bot with @BotFather and put the "
            "token in your .env (see .env.example)."
        )
