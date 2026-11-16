"""
api_scrapers.py — Fast, API-based scrapers for Shopify and WooCommerce.
No browser required — just HTTP requests against their public JSON endpoints.
"""

import re
import logging
import requests
import json

from config import HEADERS, REQUEST_TIMEOUT
from validators import Product, clean_price, validate_product, validate_batch

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  SHOPIFY
# ═══════════════════════════════════════════════════════════

def scrape_shopify(url: str, max_pages: int = 10) -> list[Product]:
    """
    Scrape a Shopify collection via the public /products.json endpoint.

    Shopify exposes every collection as:
        /collections/<handle>/products.json?limit=250&page=N

    No authentication, no browser, no rate limit issues.
    
    Returns:
        List of validated Product instances
    """
    # Extract the collection base URL
    # e.g. https://store.com/collections/shoes  → base = https://store.com/collections/shoes
    match = re.match(r"(https?://[^/]+/collections/[^/?#]+)", url)
    if not match:
        logger.error(f"Could not parse Shopify collection URL: {url}")
        return []

    base = match.group(1)
    all_products = []

    logger.info(f"Scraping Shopify API: {base}/products.json")

    for page in range(1, max_pages + 1):
        api_url = f"{base}/products.json?limit=250&page={page}"
        try:
            r = requests.get(api_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()  # Raise HTTPError for bad status codes
            data = r.json()
        except requests.Timeout:
            logger.error(f"Request timeout on Shopify page {page}: {api_url}")
            break
        except requests.HTTPError as e:
            logger.error(f"HTTP error on Shopify page {page}: {e}")
            break
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response from Shopify page {page}")
            break
        except requests.RequestException as e:
            logger.error(f"Request error on Shopify page {page}: {e}")
            break

        products = data.get("products", [])
        if not products:
            break

        for p in products:
            # Use the cheapest variant price as the displayed price
            variants = p.get("variants", [])
            price = min(
                (v.get("price", "0") for v in variants),
                default="N/A",
                key=lambda x: float(x) if x else 0
            )
            
            # Create and validate product
            product_data = {
                "name": p.get("title", ""),
                "price": price,
                "url": f"{base.split('/collections')[0]}/products/{p.get('handle', '')}",
                "currency": "USD",
                "description": p.get("body_html", ""),
                "image_url": p.get("featured_image", ""),
            }
            
            product = validate_product(product_data, require_url=True)
            if product:
                all_products.append(product)

        logger.info(f"Shopify page {page}: {len(products)} products (validated: {len([p for p in all_products if p])})")

        if len(products) < 250:
            break   # last page

    return all_products


# ═══════════════════════════════════════════════════════════
#  WOOCOMMERCE
# ═══════════════════════════════════════════════════════════

def scrape_woocommerce(url: str, max_pages: int = 10) -> list[Product] | None:
    """
    Try the WooCommerce public Store API (/wp-json/wc/store/products).
    Returns None if the API is disabled — caller should fall back to Selenium.
    
    Returns:
        List of validated Product instances or None if API unavailable
    """
    # Extract base domain
    match = re.match(r"(https?://[^/]+)", url)
    if not match:
        logger.warning(f"Could not parse URL for WooCommerce: {url}")
        return None

    base = match.group(1)

    # Try to detect category slug from URL for filtered requests
    # e.g. /shop/PC%20PORTABLE/PC%20PORTABLE%20PRO → last segment
    path_parts = url.rstrip("/").split("/")
    category_slug = path_parts[-1].replace("%20", "-").lower() if path_parts else ""

    logger.info(f"Scraping WooCommerce Store API: {base}/wp-json/wc/store/products")

    all_products = []

    for page in range(1, max_pages + 1):
        api_url = (
            f"{base}/wp-json/wc/store/products"
            f"?per_page=100&page={page}&orderby=date&order=desc"
        )
        try:
            r = requests.get(api_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            
            if r.status_code != 200:
                logger.warning(f"WooCommerce API returned {r.status_code} — API may be disabled")
                return None

            products = r.json()
        except requests.Timeout:
            logger.error(f"Request timeout on WooCommerce page {page}")
            return None
        except requests.HTTPError as e:
            status_code = getattr(getattr(e, "response", None), "status_code", "unknown")
            logger.warning(f"HTTP error on WooCommerce API: {status_code} — API may be disabled")
            return None
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from WooCommerce API on page {page}")
            return None
        except requests.RequestException as e:
            logger.error(f"Request failed on WooCommerce API: {e}")
            return None

        if not products:
            break

        for p in products:
            prices = p.get("prices", {})
            # prices are in minor currency units (e.g. 120000 = 120.000 TND)
            raw_price = prices.get("price", "")
            decimals  = int(prices.get("currency_minor_unit", 3))
            try:
                price = f"{int(raw_price) / (10 ** decimals):.{decimals}f}"
            except (ValueError, TypeError):
                price = raw_price

            product_data = {
                "name": p.get("name", ""),
                "price": price,
                "url": p.get("permalink", ""),
                "currency": "TND",
                "description": p.get("description", ""),
                "image_url": p.get("images", [{}])[0].get("src", ""),
            }
            
            product = validate_product(product_data, require_url=True)
            if product:
                all_products.append(product)

        logger.info(f"WooCommerce page {page}: {len(products)} products (validated: {len([p for p in all_products if p])})")

        if len(products) < 100:
            break

    return all_products if all_products else None