"""
main.py — Universal Structured Data Extractor (Platform-Aware)

Usage:
    python main.py <URL> [--pages N] [--fields "title,company,location"]

Examples:
    python main.py https://shop.com/products --pages 3
    python main.py https://jobs.example.com --fields "title,company,salary,location"
    python main.py https://blog.com/articles --fields "headline,author,date" --pages 5
"""

import argparse
import json
import logging
import re
from detector        import detect_platform, detect_content_type
from api_scrapers    import scrape_shopify, scrape_woocommerce
from selenium_scraper import setup_driver, scrape_with_selenium
from spa_scraper     import scrape_spa
from content_api_scrapers import scrape_wordpress, scrape_ghost
from source_adapters import try_source_adapter
from config import OUTPUT_FILENAME
from validators import Product, deduplicate_products

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PLATFORM_LABELS = {
    "shopify":     "Shopify   → API mode",
    "woocommerce": "WooCommerce → API mode (with Selenium fallback)",
    "wordpress":   "WordPress  → Content API mode",
    "ghost":       "Ghost      → Content API mode",
    "prestashop":  "PrestaShop → Selenium + LLM",
    "magento":     "Magento    → Selenium + LLM",
    "react_spa":   "React/Next.js SPA → XHR intercept",
    "unknown":     "Unknown    → Selenium + LLM",
}


def _parse_field_hints(fields_csv: str | None) -> list[str]:
    if not fields_csv:
        return []
    return [field.strip() for field in fields_csv.split(",") if field.strip()]


def _item_to_dict(item: Product | dict) -> dict:
    if isinstance(item, Product):
        return item.to_dict()
    if isinstance(item, dict):
        return {k: v for k, v in item.items() if v is not None and v != ""}
    return {}


def _deduplicate_items(items: list[dict], field_hints: list[str] | None = None) -> list[dict]:
    if not items:
        return []

    hints = field_hints or []
    key_candidates = hints + ["name", "title", "headline", "url", "id"]
    dedupe_key = next((k for k in key_candidates if any(k in it for it in items)), None)
    if not dedupe_key:
        return items

    seen = set()
    unique = []
    for item in items:
        value = str(item.get(dedupe_key, "")).strip()
        if not value:
            unique.append(item)
            continue
        sig = (dedupe_key, value.lower())
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(item)
    return unique


def _detect_fields(items: list[dict], field_hints: list[str] | None = None) -> list[str]:
    if not items:
        return field_hints or []

    ordered = []
    if field_hints:
        for hint in field_hints:
            if hint not in ordered:
                ordered.append(hint)

    for item in items:
        for key in item.keys():
            if key not in ordered:
                ordered.append(key)
    return ordered


def _infer_content_type_from_items(items: list[dict], current: str) -> str:
    """Lightweight post-scrape content-type correction based on extracted fields."""
    if not items:
        return current

    if current == "ecommerce":
        return current

    ecommerce_keys = {"price", "stock", "sku", "product", "cart", "title_fr", "lien"}
    sample = items[:20]
    hits = 0
    for item in sample:
        keys = {str(k).lower() for k in item.keys()}
        if keys.intersection(ecommerce_keys):
            hits += 1

    if hits >= max(2, len(sample) // 3):
        return "ecommerce"

    if current == "jobs":
        return current

    jobs_hits = 0
    for item in sample:
        keys = {str(k).lower() for k in item.keys()}
        if "title" in keys and ({"company", "location"}.intersection(keys)):
            jobs_hits += 2
        elif {"company", "location"}.issubset(keys):
            jobs_hits += 1

    return "jobs" if jobs_hits >= max(3, len(sample) // 2) else current


def _clean_company_name(value: str) -> str:
    cleaned = str(value or "").strip()
    cleaned = re.sub(r"\s*-\s*$", "", cleaned)
    return cleaned.strip()


def _clean_salary_value(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    lowered = text.lower()
    has_currency = any(token in lowered for token in ("dt", "tnd", "eur", "usd", "€", "$", "£"))
    digits = re.sub(r"\D", "", text)

    if not has_currency:
        if len(digits) < 3:
            return ""
        if text.endswith(",") or text.endswith("."):
            text = text[:-1].strip()

    return text


def _normalize_job_items(items: list[dict]) -> list[dict]:
    """Clean and merge noisy fallback output from job listing pages."""
    if not items:
        return []

    cleaned: list[dict] = []
    for raw in items:
        item = _item_to_dict(raw)
        if not item:
            continue

        if "company" in item:
            company = _clean_company_name(item.get("company", ""))
            if company:
                item["company"] = company
            else:
                item.pop("company", None)

        if "salary" in item:
            salary = _clean_salary_value(item.get("salary", ""))
            if salary:
                item["salary"] = salary
            else:
                item.pop("salary", None)

        if set(item.keys()) == {"salary"}:
            continue

        cleaned.append(item)

    merged: list[dict] = []
    for item in cleaned:
        if merged:
            prev = merged[-1]
            item_has_title = bool(item.get("title"))
            prev_has_title = bool(prev.get("title"))

            same_company = item.get("company") and item.get("company") == prev.get("company")
            same_location = item.get("location") and item.get("location") == prev.get("location")
            same_identity = same_company or same_location

            if (not item_has_title) and prev_has_title and same_identity:
                for key, value in item.items():
                    prev.setdefault(key, value)
                continue

            if item_has_title and (not prev_has_title) and same_identity:
                promoted = dict(prev)
                promoted.update(item)
                merged[-1] = promoted
                continue

        merged.append(item)

    filtered = [
        item for item in merged
        if item.get("title") and (item.get("company") or item.get("location"))
    ]
    # Some job boards expose only titles in listing views.
    # If strict filtering wipes all rows, keep title-only rows as fallback.
    if not filtered:
        filtered = [item for item in merged if item.get("title")]

    noise_title_markers = {
        "accueil",
        "espace entreprise",
        "publiez vos offres d'emploi",
        "publiez vos offres d’emploi",
        "tunisie travail",
        "pavée emploi",
        "contact",
        "a propos",
        "à propos",
        "mentions legales",
        "mentions légales",
    }

    deduped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for item in filtered:
        title_text = str(item.get("title", "")).strip()
        title_norm = title_text.lower()
        if not title_text or len(title_text) < 8:
            continue
        if title_norm in noise_title_markers:
            continue

        sig = (
            title_norm,
            str(item.get("company", "")).strip().lower(),
            str(item.get("location", "")).strip().lower(),
        )
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(item)

    return deduped


def run(url: str, max_pages: int = 1,
        field_hints: list[str] | None = None) -> tuple[list[dict], str, str]:

    adapter_result = try_source_adapter(url, max_pages=max_pages, field_hints=field_hints)
    if adapter_result is not None:
        return adapter_result.items, adapter_result.platform, adapter_result.content_type

    # ── 1. Detect platform ───────────────────────────────────
    logger.info("Detecting platform...")
    try:
        platform, html = detect_platform(url)
        content_type = detect_content_type(html, url=url)
        logger.info(f"Platform detected: {PLATFORM_LABELS.get(platform, platform)}")
        logger.info(f"Content type detected: {content_type}")
    except Exception as e:
        logger.error(f"Error detecting platform: {e}")
        return [], "unknown", "unknown"

    items: list[dict] = []

    # ── 2. Route to the right strategy ───────────────────────

    try:
        if platform == "shopify":
            # ✅ Best case: pure API, no browser needed
            products = scrape_shopify(url, max_pages=max_pages)
            items = [_item_to_dict(p) for p in products]

        elif platform == "woocommerce":
            # Try the REST API first
            products = scrape_woocommerce(url, max_pages=max_pages)
            if products is None:
                # API disabled — fall back to Selenium
                logger.info("WooCommerce API unavailable, falling back to Selenium...")
                items = scrape_with_selenium(url, max_pages=max_pages, field_hints=field_hints)
            else:
                items = [_item_to_dict(p) for p in products]

        elif platform == "react_spa":
            # XHR intercept via Selenium
            driver = setup_driver()
            try:
                items = scrape_spa(driver, url, field_hints=field_hints)
                if not items:
                    # SPA XHR mining failed — last resort Selenium DOM
                    logger.info("SPA intercept failed, trying Selenium DOM...")
                    items = scrape_with_selenium(
                        url, max_pages=max_pages, existing_driver=driver, field_hints=field_hints
                    )
            except Exception as e:
                logger.error(f"Error in SPA scraping: {e}")
            finally:
                try:
                    driver.quit()
                except:
                    pass

        elif platform == "wordpress" and content_type == "jobs":
            # WordPress-backed job boards usually expose clean job post titles via wp-json.
            wp_items = scrape_wordpress(url, max_pages=max_pages)
            if wp_items:
                items = wp_items
            else:
                items = scrape_with_selenium(url, max_pages=max_pages, field_hints=field_hints)

        else:
            # Try content APIs first for non-ecommerce/news-like extraction paths.
            # Job boards often run on WordPress, but should use Selenium field extraction.
            if content_type in {"news", "unknown", "real_estate"}:
                wp_items = scrape_wordpress(url, max_pages=max_pages)
                if wp_items:
                    platform = "wordpress"
                    items = wp_items
                else:
                    ghost_items = scrape_ghost(url, max_pages=max_pages)
                    if ghost_items:
                        platform = "ghost"
                        items = ghost_items

            # prestashop / magento / unknown → standard Selenium + LLM
            if not items:
                items = scrape_with_selenium(url, max_pages=max_pages, field_hints=field_hints)
    except Exception as e:
        logger.error(f"Error during scraping: {e}")

    content_type = _infer_content_type_from_items(items, content_type)
    return items, platform, content_type


def save(payload: dict, filename: str = OUTPUT_FILENAME) -> None:
    """Save extraction payload to JSON file."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(payload.get('items', []))} items to {filename}")
    except Exception as e:
        logger.error(f"Error saving products: {e}")


def preview(items: list[dict], n: int = 5,
            fields: list[str] | None = None) -> None:
    """Display a generic preview of extracted items."""
    if not items:
        logger.warning("No items extracted")
        return

    preview_fields = fields or []
    if not preview_fields and items:
        preview_fields = list(items[0].keys())[:3]

    print(f"\nPreview (first {min(n, len(items))}):")
    for idx, item in enumerate(items[:n], start=1):
        values = []
        for field in preview_fields[:3]:
            values.append(f"{field}={item.get(field, 'N/A')}")
        line = " | ".join(values) if values else str(item)
        print(f"   {idx}. {line}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Universal structured data extractor"
    )
    parser.add_argument("url", help="Target URL to scrape")
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="Maximum number of pages to crawl (default: 1)",
    )
    parser.add_argument(
        "--fields",
        type=str,
        default="",
        help="Comma-separated field hints, e.g. 'title,company,location'",
    )
    return parser


# ── Entry point ──────────────────────────────────────────────

def main():
    parser = build_parser()
    args = parser.parse_args()

    url = args.url
    max_pages = args.pages
    field_hints = _parse_field_hints(args.fields)

    print(f"\n{'='*55}")
    print("Universal Structured Extractor")
    print(f"    URL       : {url}")
    print(f"    Max pages : {max_pages}")
    print(f"    Fields    : {', '.join(field_hints) if field_hints else 'auto'}")
    print(f"{'='*55}")

    logger.info(
        f"Starting scrape: URL={url}, max_pages={max_pages}, field_hints={field_hints}"
    )
    
    try:
        items, platform, content_type = run(
            url,
            max_pages=max_pages,
            field_hints=field_hints,
        )

        items = [_item_to_dict(item) for item in items]
        logger.info(f"Raw items: {len(items)}")

        if content_type == "ecommerce":
            # Keep backward-compatible dedupe path for Product-like records
            products = []
            for item in items:
                if "name" in item:
                    products.append(Product(name=item.get("name", ""), price=item.get("price")))
            if products:
                deduped = deduplicate_products(products, key="name")
                keep_names = {p.name for p in deduped if p.name}
                items = [it for it in items if it.get("name") in keep_names] or items
        elif content_type == "jobs":
            items = _normalize_job_items(items)
            items = _deduplicate_items(items, field_hints=field_hints or ["title", "company", "location"])
        else:
            items = _deduplicate_items(items, field_hints=field_hints)

        detected_fields = _detect_fields(items, field_hints=field_hints)
        payload = {
            "url": url,
            "platform": platform,
            "content_type": content_type,
            "detected_fields": detected_fields,
            "items": items,
        }

        print(f"\n{'='*55}")
        print(f"Total extracted: {len(items)}")

        save(payload)
        preview(items, n=5, fields=detected_fields)
    except KeyboardInterrupt:
        logger.warning("Scrape interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()