"""Tests for the per-request client identity logging middleware."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_logs_client_identity_headers(caplog: pytest.LogCaptureFixture) -> None:
    """X-Client-CN and X-SSL-Client-Serial are logged for every request."""
    app = create_app()
    caplog.set_level(logging.INFO)

    with TestClient(app) as client:
        client.get(
            "/nonexistent",
            headers={
                "X-Client-CN": "alice@example.com",
                "X-SSL-Client-Serial": "1234ABCD",
            },
        )

    assert "X-Client-CN=alice@example.com" in caplog.text
    assert "X-SSL-Client-Serial=1234ABCD" in caplog.text
