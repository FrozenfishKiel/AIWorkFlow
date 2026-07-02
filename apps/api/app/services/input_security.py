from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException, status


def _reject_private_ip(ip_text: str) -> None:
  """Block local, private, and reserved IP destinations.

  This is the first SSRF guardrail for URL ingestion. The current project only
  accepts public web pages, so any direct IP that points at loopback, RFC1918,
  link-local, or other reserved ranges is rejected before later fetch logic can
  touch it.
  """

  ip = ipaddress.ip_address(ip_text)
  if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
      detail="Private or local network URLs are not allowed.",
    )


def _validate_hostname_resolution(hostname: str) -> None:
  """Resolve hostnames and reject them if any answer falls into blocked ranges.

  This closes the obvious DNS-rebinding style gap where a public-looking host
  name resolves to loopback, private network, or other non-public addresses.
  """

  try:
    resolved = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
  except OSError as error:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
      detail="URL hostname could not be resolved safely.",
    ) from error

  for _, _, _, _, address in resolved:
    _reject_private_ip(address[0])


def validate_public_url(url: str) -> str:
  """Reject non-public URLs before they reach any fetch or parsing layer.

  This is intentionally narrow rather than fully general-purpose crawling
  protection. It blocks the obvious Phase 1 SSRF classes and leaves more
  advanced network-policy enforcement to future deployment hardening.
  """

  parsed = urlparse(url)
  if parsed.scheme not in {"http", "https"}:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
      detail="Only public http/https URLs are allowed.",
    )

  hostname = parsed.hostname
  if not hostname:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
      detail="URL hostname is required.",
    )

  lowered = hostname.lower()
  if lowered in {"localhost", "127.0.0.1", "::1"}:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
      detail="Localhost URLs are not allowed.",
    )

  try:
    _reject_private_ip(lowered)
  except ValueError:
    _validate_hostname_resolution(lowered)

  return url
