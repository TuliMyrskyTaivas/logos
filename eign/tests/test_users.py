"""User management tests (administrator-only endpoints)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

Headers = dict[str, str]


def _provision_admin(client: TestClient, auth: Callable[..., dict[str, str]]) -> Headers:
    assert client.get("/auth/me", headers=auth("alice")).status_code == 200
    return auth("alice")


def test_non_admin_cannot_manage_users(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    admin = _provision_admin(client, auth)
    client.post("/users", headers=admin, json={"login": "bob"})

    assert client.get("/users", headers=auth("bob")).status_code == 403
    assert (
        client.post("/users", headers=auth("bob"), json={"login": "eve"}).status_code
        == 403
    )


def test_admin_creates_and_lists_users(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    admin = _provision_admin(client, auth)

    created = client.post("/users", headers=admin, json={"login": "bob"})
    assert created.status_code == 201
    assert created.json()["role"] == "user"
    assert created.json()["lastLoginAt"] is None

    listed = client.get("/users", headers=admin)
    assert listed.status_code == 200
    assert [user["login"] for user in listed.json()] == ["alice", "bob"]


def test_duplicate_login_is_rejected(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    admin = _provision_admin(client, auth)
    assert client.post("/users", headers=admin, json={"login": "bob"}).status_code == 201
    assert client.post("/users", headers=admin, json={"login": "bob"}).status_code == 409


def test_invalid_role_is_rejected(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    admin = _provision_admin(client, auth)
    response = client.post("/users", headers=admin, json={"login": "bob", "role": "root"})
    assert response.status_code == 422


def test_role_can_be_promoted_and_demoted(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    admin = _provision_admin(client, auth)
    bob_id = client.post("/users", headers=admin, json={"login": "bob"}).json()["id"]

    promoted = client.patch(f"/users/{bob_id}", headers=admin, json={"role": "admin"})
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"
    assert client.get("/users", headers=auth("bob")).status_code == 200

    demoted = client.patch(f"/users/{bob_id}", headers=admin, json={"role": "user"})
    assert demoted.status_code == 200
    assert client.get("/users", headers=auth("bob")).status_code == 403


def test_last_admin_cannot_lose_admin_rights(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    admin = _provision_admin(client, auth)
    alice_id = client.get("/auth/me", headers=admin).json()["id"]

    assert (
        client.patch(f"/users/{alice_id}", headers=admin, json={"role": "user"}).status_code
        == 409
    )
    assert (
        client.patch(
            f"/users/{alice_id}", headers=admin, json={"isActive": False}
        ).status_code
        == 409
    )

    bob_id = client.post("/users", headers=admin, json={"login": "bob"}).json()["id"]
    client.patch(f"/users/{bob_id}", headers=admin, json={"role": "admin"})

    assert (
        client.patch(f"/users/{alice_id}", headers=admin, json={"role": "user"}).status_code
        == 200
    )
    assert client.get("/users", headers=admin).status_code == 403


def test_admin_cannot_deactivate_self(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    admin = _provision_admin(client, auth)
    alice_id = client.get("/auth/me", headers=admin).json()["id"]
    assert client.delete(f"/users/{alice_id}", headers=admin).status_code == 409


def test_deactivation_keeps_user_record(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    admin = _provision_admin(client, auth)
    bob_id = client.post("/users", headers=admin, json={"login": "bob"}).json()["id"]

    assert client.delete(f"/users/{bob_id}", headers=admin).status_code == 204
    users = client.get("/users", headers=admin).json()
    assert [(user["login"], user["isActive"]) for user in users] == [
        ("alice", True),
        ("bob", False),
    ]


def test_unknown_user_returns_404(
    client: TestClient, auth: Callable[..., dict[str, str]]
) -> None:
    admin = _provision_admin(client, auth)
    assert client.patch("/users/9999", headers=admin, json={"role": "user"}).status_code == 404
    assert client.delete("/users/9999", headers=admin).status_code == 404
