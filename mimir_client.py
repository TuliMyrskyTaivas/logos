"""HTTP client for the mímir service (JSON over HTTPS with optional mTLS)."""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MIMIR_URL_DEFAULT = "https://localhost:8443"


def uses_https(mimir_url: str) -> bool:
    """Return True if the URL uses the https scheme."""
    return urllib.parse.urlparse(mimir_url).scheme == "https"


def _ssl_context(
    ca_file: str | None,
    cert_file: str | None,
    key_file: str | None,
) -> ssl.SSLContext | None:
    """Build an SSL context using the given CA / client certificate files.

    Set `MIMIR_VERIFY_SSL=0` to disable server certificate verification
    (e.g. for testing against a self-signed server certificate).
    """
    verify_ssl = os.getenv("MIMIR_VERIFY_SSL", "1").strip().lower() not in ("0", "false", "no", "off")

    if not verify_ssl:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    elif not (ca_file or cert_file):
        return None
    else:
        context = ssl.create_default_context(cafile=ca_file)

    if cert_file:
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)
    return context


def _ssl_error_details(exc: ssl.SSLError) -> str:
    """Return a human-readable description of an SSL error for logging."""
    parts: list[str] = [str(exc) or type(exc).__name__]
    if isinstance(exc, ssl.SSLCertVerificationError):
        parts.append(f"verify_message={exc.verify_message!r}")
        parts.append(f"verify_code={exc.verify_code}")
    library = getattr(exc, "library", None)
    reason = getattr(exc, "reason", None)
    filename = getattr(exc, "filename", None)
    if library:
        parts.append(f"library={library}")
    if reason:
        parts.append(f"reason={reason}")
    if filename:
        parts.append(f"filename={filename!r}")
    return "; ".join(parts)


def request(
    mimir_url: str,
    method: str,
    path: str,
    body: Any = None,
    *,
    logger: logging.Logger,
    cert_file: str | None = None,
    key_file: str | None = None,
) -> Any:
    """Send a JSON request to mímir and return the decoded JSON response.

    `cert_file` and `key_file` override the MIMIR_CLIENT_CERT_FILE /
    MIMIR_CLIENT_KEY_FILE environment variables and are used only when
    `mimir_url` uses the https scheme.
    """
    url = f"{mimir_url.rstrip('/')}{path}"
    logger.debug("mímir request: %s %s", method, url)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method,
    )

    use_tls = uses_https(mimir_url)
    ca_file = os.getenv("MIMIR_CA_FILE")

    context: ssl.SSLContext | None = None
    if use_tls:
        try:
            context = _ssl_context(ca_file=ca_file, cert_file=cert_file, key_file=key_file)
        except ssl.SSLError as exc:
            logger.error(
                "failed to build TLS context for mímir at %s "
                "(ca_file=%r, cert_file=%r, key_file=%r): %s",
                mimir_url,
                ca_file,
                cert_file,
                key_file,
                _ssl_error_details(exc),
            )
            raise
    try:
        with urllib.request.urlopen(req, timeout=60, context=context) as response:
            content = response.read().decode("utf-8")
            result = json.loads(content) if content else None
            logger.debug("mímir response: %s", content or result)
            return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"mímir returned HTTP {exc.code}: {detail}") from exc
    except ssl.SSLError as exc:
        details = _ssl_error_details(exc)
        logger.error("TLS error while talking to mímir at %s: %s", url, details)
        raise RuntimeError(f"TLS error talking to mímir at {mimir_url}: {details}") from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ssl.SSLError):
            details = _ssl_error_details(reason)
            logger.error("TLS error while talking to mímir at %s: %s", url, details)
            raise RuntimeError(f"TLS error talking to mímir at {mimir_url}: {details}") from exc
        raise RuntimeError(f"cannot reach mímir at {mimir_url}: {reason}") from exc
