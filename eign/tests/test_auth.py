"""Authentication and first-user provisioning tests."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_me_requires_verified_certificate(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"X-Client-CN": "alice"}).status_code == 401
    assert (
        client.get("/auth/me", headers=auth("alice", verify="FAILED")).status_code
        == 401
    )
    assert (
        client.get("/auth/me", headers=auth("alice", verify="NONE")).status_code
        == 401
    )


def test_first_user_becomes_admin(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    response = client.get("/auth/me", headers=auth("alice"))
    assert response.status_code == 200
    body = response.json()
    assert body["login"] == "alice"
    assert body["role"] == "admin"
    assert body["isActive"] is True
    assert body["baseCurrency"] == "RUB"
    assert body["lastLoginAt"] is not None


def test_unknown_login_is_rejected_once_users_exist(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    assert client.get("/auth/me", headers=auth("alice")).status_code == 200

    response = client.get("/auth/me", headers=auth("carol"))
    assert response.status_code == 403


def test_deactivated_user_is_rejected(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    client.get("/auth/me", headers=auth("alice"))
    created = client.post("/users", headers=auth("alice"), json={"login": "bob"})
    bob_id = created.json()["id"]

    assert client.get("/auth/me", headers=auth("bob")).status_code == 200
    assert client.delete(f"/users/{bob_id}", headers=auth("alice")).status_code == 204
    assert client.get("/auth/me", headers=auth("bob")).status_code == 403


def test_last_login_is_refreshed_at_most_once_a_day(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    first = client.get("/auth/me", headers=auth("alice")).json()
    second = client.get("/auth/me", headers=auth("alice")).json()
    assert first["lastLoginAt"] == second["lastLoginAt"]
