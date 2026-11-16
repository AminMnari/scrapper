"""
source_adapters.py - Pluggable source adapters for compliant integrations.

Adapters can short-circuit the default scraping flow when a source requires
special handling (for example LinkedIn through an authorized provider API).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from config import HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


@dataclass
class AdapterResult:
    items: list[dict]
    platform: str
    content_type: str


def _hostname(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _is_linkedin_url(url: str) -> bool:
    host = _hostname(url)
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def _normalize_items(raw: object) -> list[dict]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        items = raw.get("items", [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _fetch_from_linkedin_provider(url: str, max_pages: int, field_hints: list[str]) -> list[dict] | None:
    provider_url = os.environ.get("LINKEDIN_PROVIDER_URL", "").strip()
    if not provider_url:
        return None

    token = os.environ.get("LINKEDIN_PROVIDER_TOKEN", "").strip()
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "target_url": url,
        "max_pages": max_pages,
        "fields": field_hints,
    }

    try:
        response = requests.post(
            provider_url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return _normalize_items(response.json())
    except requests.RequestException as exc:
        logger.error("LinkedIn provider request failed: %s", exc)
        return []
    except ValueError:
        logger.error("LinkedIn provider did not return valid JSON")
        return []


def try_source_adapter(url: str, max_pages: int, field_hints: list[str] | None) -> AdapterResult | None:
    """
    Try adapter-based extraction first for restricted/special sources.

    Returns AdapterResult when an adapter handles the source, otherwise None.
    """
    hints = field_hints or []

    if not _is_linkedin_url(url):
        return None

    items = _fetch_from_linkedin_provider(url, max_pages=max_pages, field_hints=hints)
    if items is None:
        logger.warning(
            "LinkedIn URL detected but no compliant provider configured. "
            "Set LINKEDIN_PROVIDER_URL (and optional LINKEDIN_PROVIDER_TOKEN)."
        )
        return AdapterResult(items=[], platform="linkedin", content_type="jobs")

    logger.info("LinkedIn adapter fetched %s item(s) from provider", len(items))
    return AdapterResult(items=items, platform="linkedin_provider", content_type="jobs")
