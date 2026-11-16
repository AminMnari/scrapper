"""
config.py — Centralized configuration for the scraper.
Load settings from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ══════════════════════════════════════════════════════════════
#  API & LLM Configuration
# ══════════════════════════════════════════════════════════════

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    import warnings
    warnings.warn(
        "GROQ_API_KEY environment variable is not set. "
        "Set it in .env or export it: export GROQ_API_KEY='gsk_...'\n"
        "The scraper will fail if you try to use LLM features."
    )

GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-70b-versatile")

# ══════════════════════════════════════════════════════════════
#  Request Configuration
# ══════════════════════════════════════════════════════════════

REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "15"))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT
}

# ══════════════════════════════════════════════════════════════
#  Selenium Configuration
# ══════════════════════════════════════════════════════════════

BROWSER_HEADLESS = os.environ.get("BROWSER_HEADLESS", "false").lower() == "true"
BROWSER_WINDOW_WIDTH = int(os.environ.get("BROWSER_WINDOW_WIDTH", "1920"))
BROWSER_WINDOW_HEIGHT = int(os.environ.get("BROWSER_WINDOW_HEIGHT", "1080"))
BROWSER_USE_PROFILE = os.environ.get("BROWSER_USE_PROFILE", "true").lower() == "true"
BROWSER_USER_DATA_DIR = os.environ.get("BROWSER_USER_DATA_DIR", "./chrome_profile")
BROWSER_PROFILE_DIRECTORY = os.environ.get("BROWSER_PROFILE_DIRECTORY", "Default")
CHALLENGE_WAIT_SECONDS = int(os.environ.get("CHALLENGE_WAIT_SECONDS", "300"))
BROWSER_USE_UNDETECTED = os.environ.get("BROWSER_USE_UNDETECTED", "true").lower() == "true"

# ══════════════════════════════════════════════════════════════
#  Scraper Configuration
# ══════════════════════════════════════════════════════════════

MAX_PAGES_DEFAULT = int(os.environ.get("MAX_PAGES_DEFAULT", "10"))
MAX_SCROLLS = int(os.environ.get("MAX_SCROLLS", "6"))
SCROLL_PAUSE = float(os.environ.get("SCROLL_PAUSE", "2.0"))
MAX_HTML_CHARS = int(os.environ.get("MAX_HTML_CHARS", "12000"))
MAX_LLM_RETRIES = int(os.environ.get("MAX_LLM_RETRIES", "3"))

# ══════════════════════════════════════════════════════════════
#  Output Configuration
# ══════════════════════════════════════════════════════════════

OUTPUT_FILENAME = os.environ.get("OUTPUT_FILENAME", "products.json")

# ══════════════════════════════════════════════════════════════
#  CSS Selectors for Scraping
# ══════════════════════════════════════════════════════════════

CSS_CONTAINERS = [
    ".product-item",
    ".item.product",
    ".product-miniature",
    ".product-card",
    ".product",
    "[data-product-id]",
    "li.product",
    ".js-product",
    "article.product-item",
    ".product_list li",
    ".products li",
]

CSS_NAMES = [
    "a.product-item-link",
    ".product-item-name",
    ".product-title",
    "h2.product-title",
    ".product-name",
    "a.title",
    ".product-miniature .product-title a",
    "h3.product-title a",
    ".item-title",
]

CSS_PRICES = [
    ".price",
    ".special-price .price",
    ".price-wrapper .price",
    ".product-price-and-shipping .price",
    ".current-price .price",
    ".product-price",
    ".current-price",
    "span.price",
    ".price-box .price",
]

GRID_HINTS = [
    "#products",
    ".products",
    "#product-list",
    ".product-list",
    ".products-grid",
    "#center_column",
    "main",
    "#main",
    "[id*='product']",
    ".category-products",
]

POPUP_SELECTORS = [
    "button#onetrust-accept-btn-handler",
    ".cookie-accept",
    ".accept-cookies",
    "#accept-cookies",
    "button[aria-label='Accept']",
    "button[aria-label='Accepter']",
    ".modal-close",
    ".popup-close",
    "#close-cookie-popup",
    ".cc-accept",
    "[data-dismiss='modal']",
    "button.btn-accept",
    ".cookie-consent-accept",
]

NEXT_PAGE_SELECTORS = [
    "a[rel='next']",
    "a.next",
    ".pagination .next a",
    "li.next a",
    "a[aria-label='Next page']",
    ".pagination-next a",
    "#pagination_next a",
]
