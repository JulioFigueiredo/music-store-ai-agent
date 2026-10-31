"""Settings loaded from environment variables, with sensible defaults.

Every tunable value lives here so the rest of the code has no magic numbers.
"""

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# --- Paths -----------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Exact file names (no globbing: "*orders.csv" would also match order_items).
CSV_PREFIX = "desafio_tecnico_ai_eng - "
CATEGORIES_CSV = DATA_DIR / f"{CSV_PREFIX}categories.csv"
PRODUCTS_CSV = DATA_DIR / f"{CSV_PREFIX}products.csv"
CUSTOMERS_CSV = DATA_DIR / f"{CSV_PREFIX}customers.csv"
ORDERS_CSV = DATA_DIR / f"{CSV_PREFIX}orders.csv"
ORDER_ITEMS_CSV = DATA_DIR / f"{CSV_PREFIX}order_items.csv"
PROMOTIONS_CSV = DATA_DIR / f"{CSV_PREFIX}promotions.csv"
POLICIES_PDF = DATA_DIR / "políticas_da_loja.pdf"

DATA_FILES = (
    CATEGORIES_CSV,
    PRODUCTS_CSV,
    CUSTOMERS_CSV,
    ORDERS_CSV,
    ORDER_ITEMS_CSV,
    PROMOTIONS_CSV,
    POLICIES_PDF,
)

# --- LLM -------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
# Low temperature: answers should be consistent and factual, not creative.
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
# Max model -> tools -> model round trips in a single turn before giving up.
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "5"))

# --- Reference date and time -----------------------------------------------

# The store is in Campo Grande/MS (UTC-4, no daylight saving time).
STORE_TIMEZONE = ZoneInfo("America/Campo_Grande")
# The dataset is frozen in March 2026, so a fixed "now" keeps order timelines
# and return deadlines realistic. Unset it to use the real current time.
STORE_NOW = os.getenv("STORE_NOW", "")


def get_store_now() -> datetime:
    """Return the store's current date and time (timezone-aware).

    Uses STORE_NOW when set (ISO format, e.g. "2026-03-25T10:30"), otherwise
    the real current time in Campo Grande. Tools and the system prompt both
    call this, so they always agree on what "now" is.
    """
    if not STORE_NOW:
        return datetime.now(STORE_TIMEZONE)
    simulated = datetime.fromisoformat(STORE_NOW)
    if simulated.tzinfo is None:
        simulated = simulated.replace(tzinfo=STORE_TIMEZONE)
    return simulated


def check_data_files() -> None:
    """Fail fast with a clear message if any provided data file is missing."""
    missing = [path.name for path in DATA_FILES if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing data files in {DATA_DIR}: {missing}")


def require_api_key() -> str:
    """Return the Gemini API key, or fail fast with setup instructions.

    Not called at import time, so tests can run offline without a key.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add a "
            "free key from https://aistudio.google.com/apikey"
        )
    return GEMINI_API_KEY
