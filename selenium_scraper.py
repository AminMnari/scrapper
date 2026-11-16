"""
selenium_scraper.py — Browser-based scraper for PrestaShop, Magento, and unknown platforms.
Uses Groq LLM to detect CSS selectors, with a CSS heuristic fallback.
"""

import time
import json
import re
import logging
import importlib
from typing import Any
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from bs4 import BeautifulSoup
from groq import Groq

try:
    uc: Any = importlib.import_module("undetected_chromedriver")
    HAS_UNDETECTED = True
except Exception:
    uc = None
    HAS_UNDETECTED = False

from config import (
    GROQ_API_KEY, GROQ_MODEL, MAX_HTML_CHARS, MAX_LLM_RETRIES,
    MAX_SCROLLS, SCROLL_PAUSE, CSS_CONTAINERS, CSS_NAMES, CSS_PRICES,
    GRID_HINTS, POPUP_SELECTORS, NEXT_PAGE_SELECTORS,
    BROWSER_HEADLESS, BROWSER_WINDOW_WIDTH, BROWSER_WINDOW_HEIGHT,
    BROWSER_USE_PROFILE, BROWSER_USER_DATA_DIR, BROWSER_PROFILE_DIRECTORY,
    CHALLENGE_WAIT_SECONDS, BROWSER_USE_UNDETECTED,
)
logger = logging.getLogger(__name__)


def _log_browser_config():
    """Log browser configuration at module initialization."""
    config_lines = [
        "╔════ Browser Configuration ════╗",
        f"║ Undetected ChromeDriver:  {'✓ ENABLED' if BROWSER_USE_UNDETECTED and HAS_UNDETECTED else '✗ DISABLED'}",
        f"║ Headless Mode:            {'✓ Yes' if BROWSER_HEADLESS else '✗ No (Visible)'}",
        f"║ Browser Profile:          {'✓ Enabled' if BROWSER_USE_PROFILE and BROWSER_USER_DATA_DIR else '✗ Disabled'}",
        f"║ Profile Directory:        {BROWSER_USER_DATA_DIR or '(none)'}",
        f"║ Cloudflare Timeout:       {CHALLENGE_WAIT_SECONDS}s",
        "╚═══════════════════════════╝",
    ]
    for line in config_lines:
        logger.info(line)


_log_browser_config()


# ── Driver ───────────────────────────────────────────────────

def setup_driver(headless: bool | None = None) -> webdriver.Chrome:
    """Initialize and configure a Selenium Chrome driver with advanced anti-detection."""
    use_headless = BROWSER_HEADLESS if headless is None else bool(headless)
    use_undetected = BROWSER_USE_UNDETECTED and HAS_UNDETECTED

    if use_undetected:
        logger.info("Using undetected-chromedriver for automatic Cloudflare bypass")
        try:
            options = uc.ChromeOptions()
            
            # Profile & data persistence
            if BROWSER_USER_DATA_DIR:
                options.add_argument(f"--user-data-dir={BROWSER_USER_DATA_DIR}")
                options.add_argument(f"--profile-directory={BROWSER_PROFILE_DIRECTORY}")
                logger.debug(f"Using profile: {BROWSER_USER_DATA_DIR}/{BROWSER_PROFILE_DIRECTORY}")
            
            # Headless mode
            if use_headless:
                options.add_argument("--headless=new")
                logger.debug("Running in headless mode")
            
            # Window size
            options.add_argument(f"--window-size={BROWSER_WINDOW_WIDTH},{BROWSER_WINDOW_HEIGHT}")
            
            # Anti-detection arguments
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-preconnect")
            options.add_argument("--disable-sync")
            options.add_argument("--metrics-recording-only")
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-client-side-phishing-detection")
            
            # Prevent hangups
            options.add_argument("--disable-hang-monitor")
            options.add_argument("--disable-prompt-on-repost")
            
            driver = uc.Chrome(options=options, version_main=None)
            logger.info("✓ undetected-chromedriver initialized (will bypass Cloudflare automatically)")
            return driver
        except Exception as e:
            logger.warning(f"Failed to initialize undetected-chromedriver: {e}. Falling back to standard Selenium.")
            use_undetected = False

    if not use_undetected:
        logger.debug("Using standard Selenium with stealth plugin")
        options = webdriver.ChromeOptions()
        
        if use_headless:
            options.add_argument("--headless=new")
            logger.debug("Running in headless mode")
        
        if BROWSER_USER_DATA_DIR:
            options.add_argument(f"--user-data-dir={BROWSER_USER_DATA_DIR}")
            options.add_argument(f"--profile-directory={BROWSER_PROFILE_DIRECTORY}")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"--window-size={BROWSER_WINDOW_WIDTH},{BROWSER_WINDOW_HEIGHT}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
            stealth(
                driver,
                languages=["fr-TN", "fr", "en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
            logger.debug("✓ Selenium driver with stealth plugin initialized")
            return driver
        except Exception as e:
            logger.error(f"Failed to initialize Selenium driver: {e}")
            raise


# ── Page helpers ─────────────────────────────────────────────

def dismiss_popups(driver) -> None:
    """Attempt to dismiss common popup selectors."""
    for sel in POPUP_SELECTORS:
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            btn.click()
            time.sleep(0.5)
            logger.debug(f"Dismissed popup: {sel}")
            return
        except Exception:
            pass


def scroll_to_load_all(driver) -> None:
    """Scroll down to trigger lazy loading and load all products."""
    last_h = driver.execute_script("return document.body.scrollHeight")
    for i in range(MAX_SCROLLS):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(SCROLL_PAUSE / 2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(SCROLL_PAUSE)
        new_h = driver.execute_script("return document.body.scrollHeight")
        if new_h == last_h:
            logger.debug(f"Page fully loaded after {i+1} scroll(s)")
            return
        last_h = new_h


def _is_challenge_page(driver) -> bool:
    """Best-effort detection of anti-bot challenge pages (e.g., Cloudflare)."""
    try:
        html = str(driver.page_source).lower()
    except Exception:
        return False

    markers = [
        "just a moment",
        "un instant",
        "verify you are human",
        "checking your browser",
        "cf-challenge",
        "cloudflare",
        "challenge-error-text",
    ]
    return any(marker in html for marker in markers)


def wait_for_human_verification(driver, timeout_seconds: int = 90) -> bool:
    """
    Wait for anti-bot challenge to be solved manually or automatically.

    Returns True when challenge disappears or was never present.
    Returns False when challenge is still present after timeout.
    """
    if not _is_challenge_page(driver):
        return True

    logger.warning(
        "Anti-bot challenge detected. Waiting up to %ss for automatic/manual clearance...",
        timeout_seconds,
    )
    start = time.time()
    check_interval = 1  # Check more frequently at first
    
    while time.time() - start < timeout_seconds:
        if not _is_challenge_page(driver):
            logger.info("✓ Challenge cleared!")
            # Wait a bit longer for the page to fully load after challenge clears
            time.sleep(3)
            logger.debug("Waiting for page to stabilize after challenge clearance...")
            return True
        time.sleep(check_interval)
        elapsed = int(time.time() - start)
        if elapsed % 10 == 0:  # Log every 10 seconds
            logger.debug(f"Still waiting for challenge clearance... ({elapsed}s / {timeout_seconds}s)")

    logger.error("❌ Challenge still active after waiting; cannot extract page content")
    return False


def compress_html(driver) -> str:
    """Extract and compress HTML to focus on product grid area."""
    soup = BeautifulSoup(driver.page_source, "html.parser")
    for tag in soup(["script", "style", "svg", "img", "meta",
                      "link", "noscript", "iframe",
                      "header", "footer", "nav", "aside"]):
        tag.decompose()

    html_slice = None
    for hint in GRID_HINTS:
        section = soup.select_one(hint)
        if section and len(str(section)) > 800:
            logger.debug(f"HTML sliced at: {hint}")
            html_slice = str(section)
            break
    if not html_slice:
        html_slice = str(soup.body or soup)

    section_soup = BeautifulSoup(html_slice, "html.parser")
    for tag in section_soup.find_all(True):
        tag.attrs = {k: v for k, v in tag.attrs.items()
                     if k in ("class", "id") or k.startswith("data-")}

    return str(section_soup)[:MAX_HTML_CHARS]


# ── LLM detection ────────────────────────────────────────────

def _build_prompts(field_hints: list[str] | None = None) -> list[str]:
    hints = [h.strip() for h in (field_hints or []) if h and h.strip()]
    hints_text = ", ".join(hints) if hints else "none"

    return [
        """\
You are an expert web scraping assistant. Analyze this HTML and extract repeating structured records.
Return ONLY valid JSON with this schema:
{{
  "container": "<repeating wrapper selector>",
  "fields": {{
    "field_name_1": "<selector inside container>",
    "field_name_2": "<selector inside container>"
  }}
}}
Rules:
- Field names must be short snake_case.
- Autodiscover meaningful fields from page structure.
- Use hints if provided: {hints_text}
- Do not include markdown or explanations.
HTML:
{html}""",
        """\
Find selectors for repeating content cards/items in this HTML.
Output raw JSON only:
{{"container":"...","fields":{{"title":"...","date":"...","location":"..."}}}}
Requirements:
- container must match at least 2 records.
- fields selectors must be relative to each container.
- Prefer text-bearing fields and stable selectors.
- Optional user field hints: {hints_text}
HTML:
{html}""",
        """\
Study this page structure and infer a generic record schema.
On the LAST LINE output only JSON in this format:
{{"container":".item","fields":{{"name":".title","value":".meta"}}}}
Use any relevant fields you discover; include hints when available: {hints_text}
HTML:
{html}""",
    ]


def _parse_llm_json(raw: str) -> dict:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except Exception:
                pass
    return json.loads(raw)


def _normalize_selector_schema(sel: dict) -> dict | None:
    if not isinstance(sel, dict):
        return None

    container = sel.get("container")
    if not container or not isinstance(container, str):
        return None

    fields = sel.get("fields")
    if isinstance(fields, dict) and fields:
        normalized_fields = {
            str(k).strip(): str(v).strip()
            for k, v in fields.items()
            if str(k).strip() and str(v).strip()
        }
        return {"container": container, "fields": normalized_fields} if normalized_fields else None

    # Backward compatibility for old LLM shape
    old_fields = {}
    if sel.get("name"):
        old_fields["name"] = str(sel["name"]).strip()
    if sel.get("price"):
        old_fields["price"] = str(sel["price"]).strip()
    if old_fields:
        return {"container": container, "fields": old_fields}

    return None


def llm_detect_selectors(driver, field_hints: list[str] | None = None) -> dict | None:
    """Use Groq LLM to detect container and dynamic field selectors from HTML."""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        compressed = compress_html(driver)
    except Exception as e:
        logger.error(f"Failed to initialize Groq client or compress HTML: {e}")
        return None

    prompts = _build_prompts(field_hints)
    for attempt, prompt in enumerate(prompts[:MAX_LLM_RETRIES], start=1):
        logger.debug(f"LLM detection attempt {attempt}/{MAX_LLM_RETRIES}")
        try:
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content":
                     "You are a precise scraping assistant. Reply with JSON only."},
                    {"role": "user", "content": prompt.format(html=compressed)}
                ],
                temperature=0.1,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content.strip()
            logger.debug(f"LLM raw response: {raw[:200]}")
            sel = _normalize_selector_schema(_parse_llm_json(raw))

            if sel and sel.get("container") and sel.get("fields"):
                try:
                    found = driver.find_elements(By.CSS_SELECTOR, sel["container"])
                    if len(found) >= 2:
                        logger.info(f"LLM validated ({len(found)} containers): {sel}")
                        return sel
                    logger.debug(f"Container {sel['container']} returned {len(found)} elements")
                except Exception as e:
                    logger.debug(f"Error validating LLM selectors: {e}")
        except Exception as e:
            logger.debug(f"LLM attempt {attempt} failed: {e}")

    logger.info("LLM selector detection did not validate; trying CSS and generic fallback")
    return None


JOB_CONTAINER_SELECTORS = [
    ".listing-item",
    ".listing-item__jobs",
    ".media.listing-item",
    ".job-details",
    ".job-item",
    ".job-card",
    "[class*='job']",
    "[class*='listing']",
]


JOB_TITLE_SELECTORS = [
    ".listing-item__title",
    ".job-title",
    "a[href*='/job/']",
    "h1",
    "h2",
    "h3",
    "[class*='title']",
]


JOB_COMPANY_SELECTORS = [
    ".listing-item-info-company",
    ".company-name",
    "[class*='company']",
    "[class*='employer']",
]


JOB_LOCATION_SELECTORS = [
    ".listing-item-info-location",
    ".job-location",
    "[class*='location']",
    "[class*='city']",
    "[class*='ville']",
]


def css_fallback(driver, field_hints: list[str] | None = None) -> dict | None:
    """Fallback CSS selector detection using heuristics."""
    logger.debug("Using CSS heuristic fallback for selector detection")

    def best(candidates):
        top_sel, top_n = None, 0
        for sel in candidates:
            try:
                n = len(driver.find_elements(By.CSS_SELECTOR, sel))
                if n > top_n:
                    top_sel, top_n = sel, n
            except Exception:
                pass
        return top_sel if top_n >= 4 else None

    hints = {str(h).strip().lower() for h in (field_hints or []) if str(h).strip()}
    jobs_like = bool(hints.intersection({"title", "company", "location", "salary"}))
    ecommerce_like = bool(hints.intersection({"name", "price", "sku", "stock"}))

    # Jobs-first fallback when hints look like job listings.
    if jobs_like and not ecommerce_like:
        c = best(JOB_CONTAINER_SELECTORS)
        t = best(JOB_TITLE_SELECTORS)
        co = best(JOB_COMPANY_SELECTORS)
        lo = best(JOB_LOCATION_SELECTORS)
        fields = {}
        if t:
            fields["title"] = t
        if co:
            fields["company"] = co
        if lo:
            fields["location"] = lo

        if c and fields.get("title") and (fields.get("company") or fields.get("location")):
            selectors = {"container": c, "fields": fields}
            logger.info(f"CSS jobs fallback detected selectors: {selectors}")
            return selectors

    c = best(CSS_CONTAINERS)
    n = best(CSS_NAMES)
    p = best(CSS_PRICES)

    if c and n and p:
        selectors = {"container": c, "fields": {"name": n, "price": p}}
        logger.info(f"CSS fallback detected selectors: {selectors}")
        return selectors
    
    logger.info("CSS fallback did not find stable selectors")
    return None


# ── Scraping ─────────────────────────────────────────────────

def clean_text(text: str) -> str:
    return (
        text.replace("\xa0", " ").replace("Â", "")
            .replace("\n", " ").replace("\t", " ")
            .strip()
    ) if text else ""


# Backward compatibility alias
def clean_price(text: str) -> str:
    return (
        clean_text(text)
            .replace("TND", "")
            .replace("DT", "")
            .replace("$", "")
            .replace("€", "")
            .replace("£", "")
            .replace(",", ".")
            .strip()
    ) if text else ""


def get_next_page_url(driver) -> str | None:
    for sel in NEXT_PAGE_SELECTORS:
        try:
            el   = driver.find_element(By.CSS_SELECTOR, sel)
            href = el.get_attribute("href")
            if href and href != "#":
                return href
        except Exception:
            pass
    return None


GENERIC_CONTAINER_CANDIDATES = [
    "article",
    "li",
    ".listing-item",
    ".listing-item__jobs",
    ".media.listing-item",
    ".job-details",
    ".item",
    ".card",
    ".result",
    ".listing",
    ".job",
    ".job-item",
    ".job-card",
    ".offer",
    "[class*='job']",
    "[class*='offer']",
    "[class*='listing']",
]


FIELD_SELECTOR_HINTS = {
    "title": [
        ".listing-item__title",
        ".job-title",
        "h1",
        "h2",
        "h3",
        "a[href*='/job/']",
        "a",
        "[class*='title']",
        "[class*='job']",
    ],
    "name": ["h1", "h2", "h3", "a", "[class*='title']", "[class*='name']"],
    "company": [
        ".listing-item-info-company",
        ".company-name",
        "[class*='company']",
        "[class*='employer']",
        "[class*='societe']",
        "[class*='entreprise']",
    ],
    "location": [
        ".listing-item-info-location",
        ".job-location",
        "[class*='location']",
        "[class*='city']",
        "[class*='ville']",
        "[class*='lieu']",
        "[class*='address']",
    ],
    "salary": ["[class*='salary']", "[class*='pay']", "[class*='salaire']", "[class*='remuneration']"],
    "price": ["[class*='price']", "[class*='amount']", "[class*='value']"],
    "url": ["a"],
}


def _pick_generic_container_selector(driver) -> str | None:
    best_selector = None
    best_count = 0
    for selector in GENERIC_CONTAINER_CANDIDATES:
        try:
            count = len(driver.find_elements(By.CSS_SELECTOR, selector))
            if 4 <= count <= 400 and count > best_count:
                best_selector = selector
                best_count = count
        except Exception:
            pass
    return best_selector


def _extract_hint_field(container, field_name: str) -> str:
    key = field_name.strip().lower()
    selectors = FIELD_SELECTOR_HINTS.get(key, [])

    for selector in selectors:
        try:
            nodes = container.find_elements(By.CSS_SELECTOR, selector)
            for node in nodes:
                if key == "url":
                    href = (node.get_attribute("href") or "").strip()
                    if href and href != "#":
                        return href
                text = clean_text(node.text)
                if text:
                    return text
        except Exception:
            pass

    blob = clean_text(container.text)
    if not blob:
        return ""

    if key in {"salary", "price"}:
        match = re.search(r"(?:\d+[\d\s,.]*)\s*(?:dt|tnd|eur|usd|€|\$)?", blob, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(0))

    return ""


def _generic_scrape_with_hints(driver, field_hints: list[str] | None = None) -> list[dict]:
    hints = [h.strip() for h in (field_hints or []) if h and h.strip()]
    if not hints:
        hints = ["title", "name", "price"]

    container_selector = _pick_generic_container_selector(driver)
    if not container_selector:
        return []

    try:
        containers = driver.find_elements(By.CSS_SELECTOR, container_selector)
    except Exception:
        return []

    items = []
    for container in containers:
        item = {}
        for hint in hints:
            value = _extract_hint_field(container, hint)
            if value:
                item[hint] = value
        if item:
            items.append(item)

    if items:
        logger.info(
            f"Generic hint fallback extracted {len(items)} items using container '{container_selector}'"
        )
    return items


def preverify_challenge(url: str, timeout_seconds: int = 300, driver=None) -> bool:
    """
    Pre-verification step: Opens URL in a visible browser window and waits for Cloudflare
    challenge to clear before returning. This establishes trust with the server and allows
    the persistent profile to cache clearance tokens.
    
    Returns True if page loaded successfully without challenge, False if challenge persisted.
    """
    logger.info("Starting pre-verification: opening page for Cloudflare challenge clearance if needed...")
    owns_driver = driver is None
    try:
        if driver is None:
            driver = setup_driver(headless=False)
        logger.debug("Navigating to URL...")
        driver.get(url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        if _is_challenge_page(driver):
            logger.warning(
                f"⚠ Cloudflare challenge detected on {url}\n"
                f"Please complete the verification in the browser window.\n"
                f"Waiting up to {timeout_seconds}s for automatic/manual clearance...\n"
                f"(Browser window should remain open and active)"
            )
            if not wait_for_human_verification(driver, timeout_seconds=timeout_seconds):
                logger.error("❌ Challenge was not cleared within timeout; scraping will likely fail.")
                return False
            logger.info("✓ Challenge cleared! Cloudflare token cached to profile.")
        else:
            logger.info("✓ Page loaded successfully without challenge.")
        
        return True
    except Exception as e:
        logger.error(f"Pre-verification error: {e}")
        return False
    finally:
        if owns_driver and driver:
            try:
                driver.quit()
            except Exception:
                pass


def test_cloudflare_access(url: str, timeout_seconds: int = 30) -> bool:
    """
    Quick test to check if a URL is accessible through Cloudflare.
    Useful for early detection of Cloudflare blocks before main scraping.
    
    Returns True if accessible, False if Cloudflare blocks or error occurs.
    """
    driver = None
    try:
        logger.debug(f"Testing Cloudflare access for {url}...")
        driver = setup_driver(headless=True)  # Use headless for quick test
        driver.set_page_load_timeout(timeout_seconds)
        driver.get(url)
        
        if _is_challenge_page(driver):
            logger.warning("❌ Cloudflare/WAF challenge detected - will need manual verification or longer timeout")
            return False
        
        logger.info("✓ URL is accessible through Cloudflare")
        return True
    except Exception as e:
        logger.warning(f"Could not verify Cloudflare access: {e}")
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def scrape_items(url: str, max_pages: int = 1, existing_driver=None,
                 field_hints: list[str] | None = None,
                 headless: bool | None = None,
                 allow_headed_retry: bool = True,
                 enable_preverify: bool = True) -> list[dict]:
    """
    Full Selenium scrape loop with LLM selector detection.
    Pass an existing_driver (e.g. from SPA scraper) to reuse it.
    
    Returns:
        List of extracted item dictionaries
    """
    driver    = existing_driver or setup_driver(headless=headless)
    all_data  = []
    selectors = None
    current   = url
    owns_driver = existing_driver is None

    try:
        # Pre-verify Cloudflare challenge once if enabled and not reusing a driver
        if owns_driver and enable_preverify and not headless:
            preverify_challenge(url, timeout_seconds=CHALLENGE_WAIT_SECONDS, driver=driver)
        
        for page_num in range(1, max_pages + 1):
            logger.info(f"Loading page {page_num}: {current}")
            try:
                driver.get(current)
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body")))
            except Exception as e:
                logger.error(f"Failed to load page {page_num}: {e}")
                break

            if not wait_for_human_verification(driver, timeout_seconds=CHALLENGE_WAIT_SECONDS):
                running_headless = BROWSER_HEADLESS if headless is None else bool(headless)
                if allow_headed_retry and running_headless:
                    logger.warning(
                        "Challenge blocked headless extraction; retrying once in headed mode"
                    )
                    if owns_driver:
                        try:
                            driver.quit()
                        except Exception:
                            pass
                    return scrape_items(
                        url,
                        max_pages=max_pages,
                        existing_driver=None,
                        field_hints=field_hints,
                        headless=False,
                        allow_headed_retry=False,
                    )

                if not BROWSER_USE_PROFILE:
                    logger.warning(
                        "Challenge did not clear. Enable persistent profile (BROWSER_USE_PROFILE=true) to keep Cloudflare verification cookies across runs."
                    )
                break
                
            dismiss_popups(driver)
            scroll_to_load_all(driver)

            if selectors is None:
                selectors = llm_detect_selectors(driver, field_hints=field_hints) or css_fallback(
                    driver, field_hints=field_hints
                )
                if not selectors:
                    hinted_items = _generic_scrape_with_hints(driver, field_hints=field_hints)
                    if hinted_items:
                        all_data.extend(hinted_items)
                        logger.info(
                            f"Page {page_num}: {len(hinted_items)} items via generic field-hint fallback"
                        )
                        break
                    logger.error("Could not detect selectors on page 1")
                    break
                logger.info(f"Using selectors: {selectors}")

            try:
                containers = driver.find_elements(
                    By.CSS_SELECTOR, selectors["container"])
                logger.debug(f"Found {len(containers)} containers")
            except Exception as e:
                logger.error(f"Failed to find containers: {e}")
                break

            page_items_count = 0
            for c in containers:
                try:
                    item = {}
                    for field_name, field_selector in selectors.get("fields", {}).items():
                        value = ""
                        try:
                            nodes = c.find_elements(By.CSS_SELECTOR, field_selector)
                            if nodes:
                                texts = [clean_text(n.text) for n in nodes if clean_text(n.text)]
                                if texts:
                                    key = str(field_name).strip().lower()
                                    if key in {"title", "name", "company", "location"}:
                                        value = texts[0]
                                    else:
                                        value = texts[-1]
                        except Exception:
                            pass

                        if value:
                            item[field_name] = value

                    if item:
                        all_data.append(item)
                        page_items_count += 1
                except Exception as e:
                    logger.debug(f"Error extracting item from container: {e}")

            logger.info(f"Page {page_num}: {page_items_count} items (total: {len(all_data)})")

            if page_num < max_pages:
                try:
                    nxt = get_next_page_url(driver)
                    if not nxt:
                        logger.info("No next page found")
                        break
                    current = nxt
                except Exception as e:
                    logger.error(f"Error getting next page URL: {e}")
                    break

    except Exception as e:
        logger.error(f"Unexpected error during Selenium scraping: {e}")
    finally:
        if owns_driver:
            try:
                driver.quit()
            except Exception as e:
                logger.warning(f"Error quitting driver: {e}")

    return all_data


def scrape_with_selenium(url: str, max_pages: int = 1,
                        existing_driver=None, field_hints: list[str] | None = None,
                        headless: bool | None = None,
                        enable_preverify: bool = True) -> list[dict]:
    """Backward-compatible wrapper for generic Selenium extraction."""
    return scrape_items(
        url,
        max_pages=max_pages,
        existing_driver=existing_driver,
        field_hints=field_hints,
        headless=headless,
        enable_preverify=enable_preverify,
    )