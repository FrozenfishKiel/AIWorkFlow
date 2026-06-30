from __future__ import annotations

import re
from html import unescape
from typing import Callable
from urllib.parse import urlparse

import httpx

from app.services.input_security import validate_public_url

SCRIPT_STYLE_PATTERN = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
ARTICLE_PATTERN = re.compile(r"<article\b[^>]*>(.*?)</article>", re.IGNORECASE | re.DOTALL)
MAIN_PATTERN = re.compile(r"<main\b[^>]*>(.*?)</main>", re.IGNORECASE | re.DOTALL)
BODY_PATTERN = re.compile(r"<body\b[^>]*>(.*?)</body>", re.IGNORECASE | re.DOTALL)
TITLE_PATTERN = re.compile(r"<title\b[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
HEADER_FOOTER_NAV_PATTERN = re.compile(
    r"<(header|footer|nav|aside)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")


class UrlIngestionService:
    """Fetches public web pages and extracts reviewer-usable plain text.

    This service keeps URL-specific network and extraction behavior out of the
    task pipeline so later upgrades can swap parsing strategy without blurring
    the pipeline orchestration boundary.
    """

    def __init__(
        self,
        fetcher: Callable[[str], httpx.Response] | None = None,
    ) -> None:
        self.fetcher = fetcher or self._default_fetcher

    def fetch_public_text(self, url: str) -> str:
        """Return readable plain text from one public URL.

        The current implementation is intentionally conservative:
        - validate the URL before any network call
        - only accept HTML-ish payloads
        - strip scripts/styles/tags into stable plain text
        """

        return self.fetch_public_content(url)["text"]

    def fetch_public_content(self, url: str) -> dict[str, object]:
        """Return extracted URL content plus reviewer-visible extraction metadata."""

        safe_url = validate_public_url(url)
        try:
            response = self.fetcher(safe_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ValueError("Failed to fetch URL content safely.") from exc

        final_url = str(getattr(response, "url", safe_url))
        final_hostname = urlparse(final_url).hostname
        if final_hostname:
            validate_public_url(final_url)

        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            raise ValueError("URL content type is not supported for text extraction.")

        extracted = self._extract_content(response.text)
        if not extracted["text"]:
            extracted["text"] = f"Fetched public URL content from {safe_url}"
            extracted["quality_flags"].append("empty_url_extract")
        return extracted

    def _default_fetcher(self, url: str) -> httpx.Response:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            return client.get(
                url,
                headers={
                    "User-Agent": "ai-content-ops/0.2 (+human-reviewed-content-workflow)",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )

    def _extract_content(self, html: str) -> dict[str, object]:
        cleaned_html = SCRIPT_STYLE_PATTERN.sub(" ", html)
        title = self._extract_title(cleaned_html)
        extractor = "body"

        primary_block = self._extract_block(ARTICLE_PATTERN, cleaned_html)
        if primary_block:
            extractor = "article"
        else:
            primary_block = self._extract_block(MAIN_PATTERN, cleaned_html)
            if primary_block:
                extractor = "main"
            else:
                primary_block = self._extract_block(BODY_PATTERN, cleaned_html) or cleaned_html

        stripped_block = HEADER_FOOTER_NAV_PATTERN.sub(" ", primary_block)
        text = self._extract_text(stripped_block)
        if title and not text.lower().startswith(title.lower()):
            text = f"{title} {text}".strip()

        quality_flags: list[str] = []
        if extractor == "body":
            quality_flags.append("fallback_html_extract")
        if len(text) < 120:
            quality_flags.append("shallow_url_extract")

        return {
            "title": title,
            "text": text,
            "extractor": extractor,
            "quality_flags": quality_flags,
        }

    def _extract_block(self, pattern: re.Pattern[str], html: str) -> str | None:
        match = pattern.search(html)
        if not match:
            return None
        return match.group(1)

    def _extract_title(self, html: str) -> str:
        match = TITLE_PATTERN.search(html)
        if not match:
            return ""
        return self._extract_text(match.group(1))

    def _extract_text(self, html: str) -> str:
        cleaned = TAG_PATTERN.sub(" ", html)
        cleaned = unescape(cleaned)
        cleaned = WHITESPACE_PATTERN.sub(" ", cleaned).strip()
        return cleaned
