"""HTTP client for the mímir service (JSON over HTTPS with optional mTLS)."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any

MIMIR_URL_DEFAULT = "https://localhost:8443"


def _ssl_context() -> ssl.SSLContext | None:
    """Build an SSL context using the configured CA / client certificate.

    Set `MIMIR_VERIFY_SSL=0` to disable server certificate verification
    (e.g. for testing against a self-signed server certificate).
    """
    ca_file = os.getenv("MIMIR_CA_FILE")
    cert_file = os.getenv("MIMIR_CLIENT_CERT_FILE")
    key_file = os.getenv("MIMIR_CLIENT_KEY_FILE")
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


def request(mimir_url: str, method: str, path: str, body: Any = None) -> Any:
    """Send a JSON request to mímir and return the decoded JSON response."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{mimir_url.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method,
    )
    context = _ssl_context()
    try:
        with urllib.request.urlopen(req, timeout=60, context=context) as response:
            content = response.read().decode("utf-8")
            return json.loads(content) if content else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"mímir returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"cannot reach mímir at {mimir_url}: {exc.reason}") from exc
