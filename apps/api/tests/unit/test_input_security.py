from socket import AF_INET, SOCK_STREAM

import pytest
from fastapi import HTTPException

from app.services.input_security import validate_public_url


def test_validate_public_url_rejects_hostnames_that_resolve_to_private_ips(
    monkeypatch,
) -> None:
    def fake_getaddrinfo(*args, **kwargs):
        return [(AF_INET, SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    monkeypatch.setattr("app.services.input_security.socket.getaddrinfo", fake_getaddrinfo)

    with pytest.raises(HTTPException) as error:
        validate_public_url("https://example.com/article")

    assert error.value.status_code == 422
    assert error.value.detail == "Private or local network URLs are not allowed."


def test_validate_public_url_allows_public_resolved_hostnames(monkeypatch) -> None:
    def fake_getaddrinfo(*args, **kwargs):
        return [(AF_INET, SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("app.services.input_security.socket.getaddrinfo", fake_getaddrinfo)

    assert validate_public_url("https://example.com/article") == "https://example.com/article"
