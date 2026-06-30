import httpx
import pytest
from fastapi import HTTPException

from app.services.url_ingestion_service import UrlIngestionService


class DummyResponse:
    def __init__(
        self,
        *,
        text: str,
        headers: dict[str, str] | None = None,
        status_code: int = 200,
        url: str = "https://example.com/article",
    ) -> None:
        self.text = text
        self.headers = headers or {"content-type": "text/html; charset=utf-8"}
        self.status_code = status_code
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(self.status_code),
            )


def test_url_ingestion_service_extracts_readable_html_content() -> None:
    service = UrlIngestionService(
        fetcher=lambda url: DummyResponse(
            text="""
            <html>
              <head>
                <title>Launch Update</title>
                <style>.hidden { display:none; }</style>
              </head>
              <body>
                <article>
                  <h1>Launch Update</h1>
                  <p>Human review remains mandatory before export.</p>
                  <p>Visible citations help reviewers verify claims.</p>
                </article>
                <script>console.log('ignore me')</script>
              </body>
            </html>
            """,
        )
    )

    extracted = service.fetch_public_text("https://example.com/article")

    assert "Human review remains mandatory before export." in extracted
    assert "Visible citations help reviewers verify claims." in extracted
    assert "console.log" not in extracted


def test_url_ingestion_service_prefers_article_content_and_returns_metadata() -> None:
    service = UrlIngestionService(
        fetcher=lambda url: DummyResponse(
            text="""
            <html>
              <head>
                <title>Weekly Launch Brief</title>
              </head>
              <body>
                <header>
                  <nav>
                    <a href="/home">Home</a>
                    <a href="/archive">Archive</a>
                  </nav>
                </header>
                <article>
                  <h1>Weekly Launch Brief</h1>
                  <p>Human review remains mandatory before export.</p>
                  <p>Visible citations help reviewers verify every launch claim.</p>
                </article>
                <footer>Copyright footer links and unrelated navigation.</footer>
              </body>
            </html>
            """,
        )
    )

    extracted = service.fetch_public_content("https://example.com/article")

    assert extracted["title"] == "Weekly Launch Brief"
    assert extracted["extractor"] == "article"
    assert extracted["text"].startswith("Weekly Launch Brief")
    assert "Human review remains mandatory before export." in extracted["text"]
    assert "Visible citations help reviewers verify every launch claim." in extracted["text"]
    assert "Archive" not in extracted["text"]
    assert extracted["quality_flags"] == []


def test_url_ingestion_service_marks_shallow_or_fallback_extractions() -> None:
    service = UrlIngestionService(
        fetcher=lambda url: DummyResponse(
            text="""
            <html>
              <head>
                <title>Status Page</title>
              </head>
              <body>
                <div>Launch status</div>
              </body>
            </html>
            """,
        )
    )

    extracted = service.fetch_public_content("https://example.com/status")

    assert extracted["extractor"] == "body"
    assert "shallow_url_extract" in extracted["quality_flags"]
    assert "fallback_html_extract" in extracted["quality_flags"]


def test_url_ingestion_service_rejects_non_html_payloads() -> None:
    service = UrlIngestionService(
        fetcher=lambda url: DummyResponse(
            text='{"status":"ok"}',
            headers={"content-type": "application/json"},
        )
    )

    with pytest.raises(ValueError, match="URL content type is not supported for text extraction."):
        service.fetch_public_text("https://example.com/api")


def test_url_ingestion_service_wraps_fetch_failures() -> None:
    def failing_fetcher(url: str):
        raise httpx.TimeoutException("timed out")

    service = UrlIngestionService(fetcher=failing_fetcher)

    with pytest.raises(ValueError, match="Failed to fetch URL content safely."):
        service.fetch_public_text("https://example.com/article")


def test_url_ingestion_service_rejects_redirected_private_destinations() -> None:
    service = UrlIngestionService(
        fetcher=lambda url: DummyResponse(
            text="<html><body><article><p>Unsafe redirect.</p></article></body></html>",
            url="http://127.0.0.1/internal",
        )
    )

    with pytest.raises(HTTPException, match="Localhost URLs are not allowed."):
        service.fetch_public_content("https://example.com/redirect")
