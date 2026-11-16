"""
Universal E-Commerce Scraper
=============================
Handles: bot detection, cookie popups, infinite scroll,
         pagination, LLM-based selector detection (Groq),
         and CSS heuristic fallback.

Usage:
    python universal_scraper.py <URL> [max_pages]

Requirements:
    pip install groq selenium webdriver-manager beautifulsoup4 selenium-stealth

Environment:
    export GROQ_API_KEY="gsk_..."
"""

import sys
import time
import json
import re
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from bs4 import BeautifulSoup
from groq import Groq


# ═══════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════

GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "your_groq_api_key_here")
GROQ_MODEL     = "llama3-70b-8192"   # free tier; alt: mixtral-8x7b-32768

MAX_HTML_CHARS  = 12000   # token-safe HTML slice for the LLM
MAX_LLM_RETRIES = 3       # number of prompt variants to try
MAX_SCROLLS     = 6       # max scroll attempts for infinite-scroll pages
SCROLL_PAUSE    = 2.0     # seconds between scrolls

# CSS candidates used as last resort if LLM fails completely
CSS_CONTAINERS = [
    ".product-item", ".item.product", ".product-miniature",
    ".product-card", ".product", "[data-product-id]",
    "li.product", ".js-product", "article.product-item",
    ".product_list li", ".products li"
]
CSS_NAMES = [
    "a.product-item-link", ".product-item-name", ".product-title",
    "h2.product-title", ".product-name", "a.title",
    ".product-miniature .product-title a", "h3.product-title a",
    ".product_list .product-name a", ".item-title"
]
CSS_PRICES = [
    ".price", ".special-price .price", ".price-wrapper .price",
    ".product-price-and-shipping .price", ".current-price .price",
    ".product-price", ".current-price", "[class*='price']",
    "span.price", ".price-box .price"
]

# Selectors that hint at the product grid section of the page
GRID_HINTS = [
    "#products", ".products", "#product-list", ".product-list",
    ".products-grid", "#center_column", "main", "#main",
    "[id*='product']", ".category-products"
]

# Cookie / modal popup dismiss selectors
POPUP_SELECTORS = [
    "button#onetrust-accept-btn-handler",
    ".cookie-accept", ".accept-cookies", "#accept-cookies",
    "button[aria-label='Accept']", "button[aria-label='Accepter']",
    ".modal-close", ".popup-close", "#close-cookie-popup",
    ".cc-accept", "[data-dismiss='modal']",
    "button.btn-accept", ".cookie-consent-accept"
]


# ═══════════════════════════════════════════════════════════
#  DRIVER  (stealth mode to avoid bot detection)
# ═══════════════════════════════════════════════════════════

def setup_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    # Stealth patches — hides headless/Selenium fingerprints from sites
    stealth(
        driver,
        languages=["fr-TN", "fr", "en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    return driver


# ═══════════════════════════════════════════════════════════
#  POPUP DISMISSAL
# ═══════════════════════════════════════════════════════════

def dismiss_popups(driver) -> None:
    """Try to close cookie banners or modal popups blocking the page."""
    for sel in POPUP_SELECTORS:
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            btn.click()
            time.sleep(0.5)
            print(f"   ✅ Dismissed popup: {sel!r}")
            return
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
#  SMART SCROLL  (handles both lazy load and infinite scroll)
# ═══════════════════════════════════════════════════════════

def scroll_to_load_all(driver, max_scrolls: int = MAX_SCROLLS,
                        pause: float = SCROLL_PAUSE) -> None:
    """
    Scroll gradually to trigger lazy-loaded content.
    Stops early if page height stops growing (fully loaded).
    """
    last_height = driver.execute_script("return document.body.scrollHeight")

    for i in range(max_scrolls):
        # Two-step scroll: mid-page first, then bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(pause / 2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(pause)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print(f"   ℹ️  Page fully loaded after {i + 1} scroll(s)")
            return
        last_height = new_height

    print(f"   ⚠️  Reached scroll limit ({max_scrolls}) — some products may be missing")


# ═══════════════════════════════════════════════════════════
#  SMART HTML COMPRESSION
# ═══════════════════════════════════════════════════════════

def compress_html(driver, max_chars: int = MAX_HTML_CHARS) -> str:
    """
    1. Remove noise tags (scripts, nav, footer, etc.)
    2. Isolate the product grid section using GRID_HINTS
    3. Strip all non-essential HTML attributes
    4. Truncate to max_chars to stay within LLM token limits
    """
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Step 1 — remove everything that is not product structure
    for tag in soup(["script", "style", "svg", "img", "meta",
                      "link", "noscript", "iframe",
                      "header", "footer", "nav", "aside"]):
        tag.decompose()

    # Step 2 — try to isolate the product grid
    html_slice = None
    for hint in GRID_HINTS:
        section = soup.select_one(hint)
        if section:
            raw = str(section)
            if len(raw) > 800:   # must contain real content
                print(f"   📌 HTML sliced at section: {hint!r}")
                html_slice = raw
                break

    if not html_slice:
        html_slice = str(soup.body) if soup.body else str(soup)

    # Step 3 — strip attributes, keep only class / id / data-*
    section_soup = BeautifulSoup(html_slice, "html.parser")
    for tag in section_soup.find_all(True):
        tag.attrs = {
            k: v for k, v in tag.attrs.items()
            if k in ("class", "id") or k.startswith("data-")
        }

    return str(section_soup)[:max_chars]


# ═══════════════════════════════════════════════════════════
#  GROQ LLM SELECTOR DETECTION  (3-prompt retry strategy)
# ═══════════════════════════════════════════════════════════

PROMPT_VARIANTS = [

    # Attempt 1 — direct and concise
    """\
You are an expert web scraper. Analyze this e-commerce HTML and return \
CSS selectors for its product listings.

Respond with ONLY a raw JSON object — no markdown, no explanation:
{{"container": "<repeating element wrapping each product>", \
"name": "<product title inside container>", \
"price": "<price inside container>"}}

HTML:
{html}""",

    # Attempt 2 — rule-based, more explicit
    """\
Analyze the HTML below from an online shop.

Rules:
- "container" → the repeating wrapper around each product card (should match 4+ elements)
- "name"      → CSS selector for the product title INSIDE the container
- "price"     → CSS selector for the price INSIDE the container

Respond with ONLY this JSON, no code fences, no extra text:
{{"container": "...", "name": "...", "price": "..."}}

HTML:
{html}""",

    # Attempt 3 — chain-of-thought, JSON on last line
    """\
You are helping build a web scraper for an e-commerce website.
Study the HTML, reason briefly about the product grid structure, \
then on the VERY LAST LINE output a JSON object.

The last line must be ONLY valid JSON — example:
{{"container": ".product-item", "name": "a.title", "price": ".price"}}

HTML:
{html}""",
]


def _parse_llm_json(raw: str) -> dict:
    """Tolerantly extract JSON — handles code fences, preamble, chain-of-thought."""
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    # Try each line bottom-up (chain-of-thought puts JSON last)
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass

    return json.loads(raw)  # last resort: parse the whole response


def llm_detect_selectors(driver) -> dict | None:
    """
    Ask Groq to identify CSS selectors for this page.
    Tries MAX_LLM_RETRIES different prompt variants.
    Also validates that the container selector actually finds elements.
    Returns dict {container, name, price} or None on total failure.
    """
    client     = Groq(api_key=GROQ_API_KEY)
    compressed = compress_html(driver)

    for attempt, prompt_template in enumerate(PROMPT_VARIANTS[:MAX_LLM_RETRIES], start=1):
        print(f"\n   🤖 LLM attempt {attempt}/{MAX_LLM_RETRIES}...")
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise web scraping assistant. "
                            "When asked for CSS selectors, always reply "
                            "with valid JSON only — no markdown, no explanation."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt_template.format(html=compressed)
                    }
                ],
                temperature=0.1,   # low = more deterministic
                max_tokens=300,
            )

            raw = response.choices[0].message.content.strip()
            print(f"   Raw response: {raw[:250]}")

            selectors = _parse_llm_json(raw)

            # Check all three keys exist and are non-empty strings
            if {"container", "name", "price"}.issubset(selectors) \
                    and all(selectors[k] for k in ("container", "name", "price")):

                # Sanity-check: does the container actually match elements on the page?
                found = driver.find_elements(By.CSS_SELECTOR, selectors["container"])
                if len(found) >= 2:
                    print(f"   ✅ LLM selectors validated ({len(found)} containers): {selectors}")
                    return selectors
                else:
                    print(f"   ⚠️  Container {selectors['container']!r} "
                          f"found only {len(found)} element(s) — retrying")
            else:
                print(f"   ⚠️  Incomplete JSON on attempt {attempt}: {selectors}")

        except json.JSONDecodeError as e:
            print(f"   ⚠️  JSON parse error on attempt {attempt}: {e}")
        except Exception as e:
            print(f"   ⚠️  LLM call failed on attempt {attempt}: {e}")

    print("   ❌ All LLM attempts exhausted")
    return None


# ═══════════════════════════════════════════════════════════
#  CSS HEURISTIC FALLBACK
# ═══════════════════════════════════════════════════════════

def _best_css_selector(driver, candidates: list, min_matches: int = 4) -> str | None:
    best_sel, best_count = None, 0
    for sel in candidates:
        try:
            count = len(driver.find_elements(By.CSS_SELECTOR, sel))
            if count > best_count:
                best_sel, best_count = sel, count
        except Exception:
            pass
    if best_count >= min_matches:
        print(f"   ✅ CSS selected: {best_sel!r} ({best_count} matches)")
        return best_sel
    return None


def css_fallback(driver) -> dict | None:
    print("\n   ⚙️  Falling back to CSS heuristics...")
    container = _best_css_selector(driver, CSS_CONTAINERS)
    name      = _best_css_selector(driver, CSS_NAMES)
    price     = _best_css_selector(driver, CSS_PRICES)

    if container and name and price:
        return {"container": container, "name": name, "price": price}

    print("   ❌ CSS fallback also failed")
    return None


# ═══════════════════════════════════════════════════════════
#  PRICE CLEANER
# ═══════════════════════════════════════════════════════════

def clean_price(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("TND", "").replace("DT", "")
            .replace("$", "").replace("€", "").replace("£", "")
            .replace("\xa0", "").replace("Â", "")
            .replace(",", ".").strip()
    )


# ═══════════════════════════════════════════════════════════
#  PRODUCT SCRAPER
# ═══════════════════════════════════════════════════════════

def scrape_products(driver, selectors: dict) -> list:
    containers = driver.find_elements(By.CSS_SELECTOR, selectors["container"])
    print(f"\n   📦 Containers found: {len(containers)}")

    data = []
    for c in containers:
        try:
            name = price = ""

            try:
                name = c.find_element(By.CSS_SELECTOR, selectors["name"]).text.strip()
            except Exception:
                pass

            try:
                # Grab the LAST price match — usually the discounted/current price
                prices = c.find_elements(By.CSS_SELECTOR, selectors["price"])
                if prices:
                    price = clean_price(prices[-1].text)
            except Exception:
                pass

            if name:
                data.append({
                    "name":  name,
                    "price": price if price else "N/A"
                })

        except Exception as e:
            print(f"   ⚠️  Container parse error: {e}")

    return data


# ═══════════════════════════════════════════════════════════
#  PAGINATION
# ═══════════════════════════════════════════════════════════

NEXT_PAGE_SELECTORS = [
    "a[rel='next']", "a.next", ".pagination .next a",
    "li.next a", "a[aria-label='Next page']",
    ".pagination-next a", "a.page-link[aria-label='Next']",
    "#pagination_next a", ".next-page a"
]


def get_next_page_url(driver) -> str | None:
    for sel in NEXT_PAGE_SELECTORS:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            href = el.get_attribute("href")
            if href and href != "#":
                return href
        except Exception:
            pass
    return None


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    url       = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    driver    = setup_driver()
    all_data  = []
    selectors = None   # detected once on page 1, then reused

    try:
        current_url = url

        for page_num in range(1, max_pages + 1):
            print(f"\n{'═' * 55}")
            print(f"📄  Page {page_num}  →  {current_url}")
            print(f"{'═' * 55}")

            driver.get(current_url)

            # Wait for DOM
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # 1. Dismiss cookie/modal popups
            dismiss_popups(driver)

            # 2. Scroll to trigger lazy/infinite content
            scroll_to_load_all(driver)

            # 3. Detect selectors (LLM first, CSS fallback second)
            #    Only done on the first page, then reused for all subsequent pages
            if selectors is None:
                print("\n🔍 Detecting selectors...")
                selectors = llm_detect_selectors(driver)

                if selectors is None:
                    selectors = css_fallback(driver)

                if selectors is None:
                    print("\n❌ Selector detection failed completely. Exiting.")
                    break

                print(f"\n🎯 Final selectors: {selectors}")

            # 4. Scrape products
            page_data = scrape_products(driver, selectors)
            print(f"   ✅ {len(page_data)} products on page {page_num}")
            all_data.extend(page_data)

            # 5. Go to next page (if requested)
            if page_num < max_pages:
                next_url = get_next_page_url(driver)
                if not next_url:
                    print("\n   ℹ️  No next page detected — stopping early")
                    break
                current_url = next_url
            else:
                print(f"\n   ℹ️  Reached max_pages limit ({max_pages})")

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user — saving progress...")
    finally:
        driver.quit()

    # ── Save ──────────────────────────────────────────────────
    print(f"\n{'═' * 55}")
    print(f"✅ Total products extracted: {len(all_data)}")

    out_file = "products.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved to: {out_file}")

    # Quick preview
    if all_data:
        print("\n📋 First 5 results:")
        for item in all_data[:5]:
            print(f"   • {item['name'][:55]:<55}  {item['price']}")


if __name__ == "__main__":
    main()