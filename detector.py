"""
detector.py — Identify which e-commerce platform a page runs on.
"""

import re
import logging
import requests

from config import USER_AGENT, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": USER_AGENT
}


def detect_content_type(html: str, url: str = "") -> str:
    """
    Detect broad content type from page HTML.

    Returns one of: "ecommerce", "jobs", "real_estate", "news", "unknown".
    """
    if not html:
        return "unknown"

    text = html.lower()
    url_text = (url or "").lower()
    combined = f"{url_text} {text}"

    if any(sig in combined for sig in [
        "add to cart",
        "add-to-cart",
        "buy now",
        "product-price",
        "woocommerce",
        "shopify",
        "bershka",
        "zara",
        "pullandbear",
        "stradivarius",
        "massimodutti",
        "oysho",
        "lefties",
    ]):
        return "ecommerce"

    job_signals = [
        "apply now",
        "job description",
        "career",
        "vacancy",
        "full-time",
        "part-time",
        "emploi",
        "offre d'emploi",
        "offres d'emploi",
        "recrute",
        "recrutement",
        "candidature",
        "poste",
        "cv",
        "rh",
        "travail",
        "tunisie travail",
        "job",
        "jobs",
    ]

    news_signals = [
        "<article",
        "published",
        "byline",
        "breaking news",
        "news",
        "actualite",
        "actualites",
    ]

    jobs_score = sum(1 for sig in job_signals if sig in combined)
    news_score = sum(1 for sig in news_signals if sig in combined)

    # Prefer jobs when job-board cues are present, even on WordPress pages.
    if jobs_score >= 2:
        return "jobs"
    if news_score >= 2 and jobs_score == 0:
        return "news"

    if any(sig in combined for sig in [
        "bedrooms",
        "bathrooms",
        "sqft",
        "square feet",
        "property details",
        "for rent",
        "for sale",
    ]):
        return "real_estate"

    if news_score > 0 and jobs_score == 0:
        return "news"

    return "unknown"


def detect_platform(url: str) -> tuple[str, str]:
    """
    Fetch the page and detect the e-commerce platform.

    Returns:
        (platform, html)
        platform is one of: 'shopify', 'woocommerce', 'wordpress',
                            'prestashop', 'magento', 'react_spa', 'unknown'
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        html = r.text
    except requests.Timeout:
        logger.warning(f"Request timeout while detecting platform for {url}")
        return "unknown", ""
    except requests.RequestException as e:
        logger.warning(f"Could not fetch page for detection: {e}")
        return "unknown", ""
    except Exception as e:
        logger.error(f"Unexpected error during platform detection: {e}")
        return "unknown", ""

    url_l = (url or "").lower()

    # ── Shopify ──────────────────────────────────────────────
    if any(sig in html for sig in [
        "cdn.shopify.com",
        "shopify.com/s/files",
        "Shopify.theme",
        '"platform":"shopify"',
    ]):
        return "shopify", html

    # ── WooCommerce ────────────────────────────────────────────
    if any(sig in html for sig in [
        "wp-json/wc/store/products",
        "woocommerce",
        "WooCommerce",
        "wp-content/plugins/woocommerce",
        "product_cat",
    ]):
        return "woocommerce", html

    # ── WordPress (non-WooCommerce) ───────────────────────────
    if any(sig in html for sig in [
        "wp-content",
        "wp-includes",
        "wp-json/wp/v2",
        'name="generator" content="WordPress',
        "class=\"wp-",
    ]):
        # Guard: WooCommerce signatures should have been caught above
        return "wordpress", html

    # ── PrestaShop ────────────────────────────────────────────
    if any(sig in html for sig in [
        "PrestaShop",
        "/modules/ps_",
        "prestashop",
        "id_product",
    ]):
        return "prestashop", html

    # ── Magento ───────────────────────────────────────────────
    if any(sig in html for sig in [
        "Mage.Cookies",
        "require(['mage/",
        "\"mage/",
        "MAGE_",
        "magento",
        "Magento_",
    ]):
        return "magento", html

    # ── React / Vue / Angular SPA ─────────────────────────────
    # Page has almost no product content in static HTML
    # (body text is sparse but JS bundles are large)
    product_text_density = len(re.findall(r'\d+[\.,]\d+\s*(TND|DT|\$|€)', html))
    has_heavy_js = any(sig in html for sig in [
        "_next/static",         # Next.js (Zara)
        "__NEXT_DATA__",
        "nuxt",
        "vue",
        "react",
        "bundle.js",
        "chunk.js",
    ])

    known_spa_ecommerce_hosts = [
        "bershka.com",
        "zara.com",
        "pullandbear.com",
        "stradivarius.com",
        "massimodutti.com",
        "oysho.com",
        "lefties.com",
    ]
    if any(host in url_l for host in known_spa_ecommerce_hosts):
        return "react_spa", html

    if has_heavy_js and product_text_density < 3:
        return "react_spa", html

    return "unknown", html