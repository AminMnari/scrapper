"""
content_api_scrapers.py — API-based scrapers for non-commerce content platforms.
"""

import os
import re
import logging
import requests

from config import HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


def _base_url(url: str) -> str | None:
    match = re.match(r"(https?://[^/]+)", url)
    return match.group(1) if match else None


def scrape_wordpress(url: str, max_pages: int = 10) -> list[dict] | None:
    """
    Scrape WordPress posts from /wp-json/wp/v2/posts.

    Returns None when endpoint is unavailable to allow fallback routing.
    """
    base = _base_url(url)
    if not base:
        return None

    items = []
    for page in range(1, max_pages + 1):
        api_url = f"{base}/wp-json/wp/v2/posts?per_page=100&page={page}&_embed"
        try:
            response = requests.get(api_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if response.status_code in (401, 403, 404):
                return None if page == 1 else (items or None)
            response.raise_for_status()
            posts = response.json()
        except requests.RequestException as exc:
            logger.debug(f"WordPress API request failed: {exc}")
            return None if page == 1 else (items or None)
        except ValueError:
            return None if page == 1 else (items or None)

        if not posts:
            break

        for post in posts:
            title = (post.get("title") or {}).get("rendered", "")
            excerpt = (post.get("excerpt") or {}).get("rendered", "")
            content = (post.get("content") or {}).get("rendered", "")
            author = ""
            embedded = post.get("_embedded", {}) if isinstance(post, dict) else {}
            if isinstance(embedded, dict):
                authors = embedded.get("author", [])
                if authors and isinstance(authors[0], dict):
                    author = str(authors[0].get("name", "")).strip()

            item = {
                "title": str(title).strip(),
                "excerpt": str(excerpt).strip(),
                "content": str(content).strip(),
                "author": author,
                "date": str(post.get("date", "")).strip(),
                "url": str(post.get("link", "")).strip(),
            }
            normalized = {k: v for k, v in item.items() if v}
            if normalized:
                items.append(normalized)

        if len(posts) < 100:
            break

    return items or None


def scrape_ghost(url: str, max_pages: int = 10) -> list[dict] | None:
    """
    Scrape Ghost posts from /ghost/api/content/posts.

    Requires GHOST_CONTENT_API_KEY in environment.
    Returns None when unavailable so callers can fallback.
    """
    base = _base_url(url)
    if not base:
        return None

    api_key = os.environ.get("GHOST_CONTENT_API_KEY", "").strip()
    if not api_key:
        logger.debug("GHOST_CONTENT_API_KEY is not set; skipping Ghost API")
        return None

    items = []
    for page in range(1, max_pages + 1):
        api_url = (
            f"{base}/ghost/api/content/posts/"
            f"?key={api_key}&limit=100&page={page}&include=authors,tags"
        )
        try:
            response = requests.get(api_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if response.status_code in (401, 403, 404):
                return None if page == 1 else (items or None)
            response.raise_for_status()
            payload = response.json()
            posts = payload.get("posts", []) if isinstance(payload, dict) else []
        except requests.RequestException as exc:
            logger.debug(f"Ghost API request failed: {exc}")
            return None if page == 1 else (items or None)
        except ValueError:
            return None if page == 1 else (items or None)

        if not posts:
            break

        for post in posts:
            authors = post.get("authors", []) if isinstance(post, dict) else []
            author = ""
            if authors and isinstance(authors[0], dict):
                author = str(authors[0].get("name", "")).strip()

            tags = []
            for tag in post.get("tags", []) if isinstance(post, dict) else []:
                if isinstance(tag, dict):
                    name = str(tag.get("name", "")).strip()
                    if name:
                        tags.append(name)

            item = {
                "title": str(post.get("title", "")).strip(),
                "excerpt": str(post.get("excerpt", "")).strip(),
                "content": str(post.get("html", "")).strip(),
                "author": author,
                "date": str(post.get("published_at", "")).strip(),
                "url": str(post.get("url", "")).strip(),
                "tags": ", ".join(tags) if tags else "",
            }
            normalized = {k: v for k, v in item.items() if v}
            if normalized:
                items.append(normalized)

        if len(posts) < 100:
            break

    return items or None
