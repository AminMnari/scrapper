"""
spa_scraper.py — Scrape React/Next.js/Vue SPAs by intercepting network requests.

Strategy: inject a JS hook before page load that captures all fetch() and
XHR calls, then inspect the captured responses for list-like structured JSON.

Works on: Zara (Next.js), and most other React/Vue/Angular storefronts.
"""

import json
import time
import re
import logging
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


def _to_scalar(value) -> str:
    if isinstance(value, (str, int, float, bool)):
        text = str(value).strip()
        return text

    if isinstance(value, dict):
        preferred = ("name", "title", "label", "text", "value", "displayname")
        lowered = {str(k).strip().lower(): v for k, v in value.items()}
        for key in preferred:
            if key in lowered:
                nested = _to_scalar(lowered[key])
                if nested:
                    return nested
        for v in value.values():
            nested = _to_scalar(v)
            if nested:
                return nested
        return ""

    if isinstance(value, list):
        for item in value:
            nested = _to_scalar(item)
            if nested:
                return nested
        return ""

    return ""


# JS snippet injected into the page BEFORE it loads.
# It monkey-patches fetch() and XMLHttpRequest to log all JSON responses
# that look like product data into window.__captured_responses.
INTERCEPT_SCRIPT = """
window.__captured_responses = [];

// Patch fetch()
const _fetch = window.fetch;
window.fetch = async function(...args) {
    const response = await _fetch(...args);
    try {
        const clone = response.clone();
        const text  = await clone.text();
        if (text.length > 100 && text.length < 2000000) {
            window.__captured_responses.push({
                url:  args[0] || '',
                body: text
            });
        }
    } catch(e) {}
    return response;
};

// Patch XMLHttpRequest
const _open = XMLHttpRequest.prototype.open;
const _send = XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.open = function(method, url) {
    this._url = url;
    return _open.apply(this, arguments);
};
XMLHttpRequest.prototype.send = function() {
    this.addEventListener('load', function() {
        try {
            if (this.responseText && this.responseText.length > 100) {
                window.__captured_responses.push({
                    url:  this._url || '',
                    body: this.responseText
                });
            }
        } catch(e) {}
    });
    return _send.apply(this, arguments);
};
"""


def _looks_like_items(data: any) -> list[dict] | None:
    """
    Heuristically check if a parsed JSON object contains repeating records.
    Returns a flat list of normalized dict items if yes, else None.
    """
    def collect_lists(obj, out: list[list], depth: int = 0):
        if depth > 6:
            return
        if isinstance(obj, list):
            dict_items = [x for x in obj if isinstance(x, dict)]
            if len(dict_items) >= 2:
                out.append(dict_items)
            for item in obj:
                collect_lists(item, out, depth + 1)
            return
        if isinstance(obj, dict):
            for value in obj.values():
                collect_lists(value, out, depth + 1)

    all_lists: list[list] = []
    collect_lists(data, all_lists)
    if not all_lists:
        return None

    def score_list(dict_list: list[dict]) -> int:
        sample_local = dict_list[:25]
        keys = set()
        for item in sample_local:
            keys.update(str(k).strip().lower() for k in item.keys())

        score = min(len(dict_list), 250)
        if keys.intersection({"name", "title", "productname", "displayname"}):
            score += 60
        if keys.intersection({"price", "amount", "saleprice", "currentprice", "formattedprice"}):
            score += 90
        if keys.intersection({"id", "sku", "reference", "productid"}):
            score += 20
        if keys.intersection({"image", "images", "thumbnail", "media"}):
            score += 20

        # Penalize non-product metadata list shapes.
        if keys.intersection({"countrycode", "phoneprefix", "continent", "hostname"}):
            score -= 140
        if keys.intersection({"storedefaultlanguageid", "isopenforsaleios", "isopenforsaleandroid"}):
            score -= 120

        return score

    dict_candidates = max(all_lists, key=score_list)

    sample_items = dict_candidates[:20]
    key_counts = {}
    for item in sample_items:
        for key, value in item.items():
            scalar = _to_scalar(value)
            if scalar:
                key_counts[key] = key_counts.get(key, 0) + 1

    min_occ = max(2, len(sample_items) // 2)
    selected_keys = [k for k, c in key_counts.items() if c >= min_occ]
    priority_keys = {
        "name", "title", "productname", "displayname",
        "price", "amount", "saleprice", "currentprice", "formattedprice",
        "id", "sku", "reference", "productid",
    }
    for key, count in key_counts.items():
        if count >= 1 and str(key).strip().lower() in priority_keys and key not in selected_keys:
            selected_keys.append(key)
    if not selected_keys:
        return None

    results = []
    for item in dict_candidates:
        if not isinstance(item, dict):
            continue

        record = {}
        for key in selected_keys:
            value = item.get(key)
            if value is None:
                continue
            text = _to_scalar(value)
            if text:
                record[key] = text

        if record:
            results.append(record)

    return results if len(results) >= 2 else None


def _score_candidate(results: list[dict], endpoint: str, field_hints: list[str] | None = None) -> int:
    endpoint_l = (endpoint or "").lower()
    hints = [h.strip().lower() for h in (field_hints or []) if h and h.strip()]

    sample = results[:25]
    keys = set()
    for row in sample:
        if isinstance(row, dict):
            keys.update(str(k).strip().lower() for k in row.keys())

    score = min(len(results), 200)

    # Prefer product/listing endpoints and penalize locale/store metadata endpoints.
    if any(token in endpoint_l for token in ("product", "products", "listing", "plp", "catalog", "search")):
        score += 40
    if any(token in endpoint_l for token in ("country", "countries", "language", "locale", "store?", "stores")):
        score -= 60

    synonym_map = {
        "title": {"title", "name", "productname", "displayname", "description", "seo"},
        "price": {"price", "amount", "currentprice", "saleprice", "pricevalue", "formattedprice"},
        "company": {"company", "brand", "seller"},
        "location": {"location", "city", "country"},
        "salary": {"salary", "pay", "compensation"},
    }

    matched_hints = 0
    for hint in hints:
        target_keys = synonym_map.get(hint, {hint})
        if keys.intersection(target_keys):
            matched_hints += 1
            score += 80
        else:
            # Penalize candidates that miss requested fields.
            score -= 30

    # If price is explicitly requested, strongly prefer candidates exposing price keys.
    if "price" in hints and not keys.intersection(synonym_map["price"]):
        score -= 140

    if hints and matched_hints == 0:
        score -= 120

    return score


def _promote_bershka_products(endpoint: str,
                              base_results: list[dict],
                              field_hints: list[str] | None = None) -> list[dict]:
    endpoint_l = (endpoint or "").lower()
    if "bershka.com/itxrest" not in endpoint_l or "showproducts=false" not in endpoint_l:
        return base_results

    richer_url = re.sub(r"showProducts=false", "showProducts=true", endpoint, flags=re.IGNORECASE)
    try:
        resp = requests.get(richer_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        promoted = _looks_like_items(resp.json())
    except Exception:
        return base_results

    if not promoted:
        return base_results

    base_score = _score_candidate(base_results, endpoint, field_hints=field_hints)
    promoted_score = _score_candidate(promoted, richer_url, field_hints=field_hints)
    return promoted if promoted_score >= base_score else base_results


def scrape_spa(driver: webdriver.Chrome, url: str,
               wait_seconds: int = 8,
               field_hints: list[str] | None = None) -> list[dict]:
    """
    Load the SPA page with the network interceptor active,
    wait for all XHR/fetch calls to complete, then mine the
    captured responses for list-like JSON records.
    
    Returns:
        List of extracted item dictionaries
    """
    logger.info("SPA mode: injecting network interceptor...")

    # Inject BEFORE navigation using CDP (Chrome DevTools Protocol)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": INTERCEPT_SCRIPT}
    )

    driver.get(url)

    # Wait for body
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    # Give JS time to make all API calls and render
    logger.info(f"Waiting {wait_seconds}s for API calls to complete...")
    time.sleep(wait_seconds)

    # Also try to scroll to trigger any lazy product loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2)")
    time.sleep(2)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)

    # Retrieve all captured network responses
    captured = driver.execute_script("return window.__captured_responses || []")
    logger.debug(f"Captured {len(captured)} network responses")

    # Find the response that looks most like a record list
    best_result   = []
    best_response = None
    best_score = -10**9

    for entry in captured:
        body = entry.get("body", "")
        ep   = entry.get("url", "")

        # Skip obviously non-content URLs
        if any(skip in ep for skip in [
            "analytics", "tracking", "gtm", "facebook",
            "hotjar", "sentry", "fonts", ".css", ".js"
        ]):
            continue

        try:
            data    = json.loads(body)
            results = _looks_like_items(data)
            if results:
                candidate_score = _score_candidate(results, ep, field_hints=field_hints)
                if candidate_score > best_score:
                    best_result = results
                    best_response = ep
                    best_score = candidate_score
        except (json.JSONDecodeError, Exception):
            pass

    if best_result:
        best_result = _promote_bershka_products(
            best_response,
            best_result,
            field_hints=field_hints,
        )
        logger.info(f"Found {len(best_result)} items from: {best_response}")
        return best_result

    # ── Fallback: try to read rendered DOM if XHR mining failed ──
    logger.warning("XHR mining found nothing — trying DOM fallback...")
    return _spa_dom_fallback(driver)


def _spa_dom_fallback(driver: webdriver.Chrome) -> list[dict]:
    """
    Last resort for SPAs: look for __NEXT_DATA__ / __NUXT__ / window.__STATE__
    embedded JSON in script tags, which many frameworks embed as a data island.
    
    Returns:
        List of extracted item dictionaries
    """
    scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/json'], script#__NEXT_DATA__")

    for script in scripts:
        try:
            data    = json.loads(script.get_attribute("innerHTML") or "")
            results = _looks_like_items(data)
            if results:
                logger.info(f"Found {len(results)} items in embedded JSON")
                return results
        except Exception:
            pass

    logger.warning("SPA fallback also failed")
    return []