"""Tests for the industries endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_industries_seeded(client: TestClient) -> None:
    resp = client.get("/industries")
    assert resp.status_code == 200
    industries = resp.json()
    assert len(industries) >= 1
    assert any(i["code"] == "FINANCE_BANKS" for i in industries)


def test_create_industry(client: TestClient) -> None:
    resp = client.post("/industries", json={"name": "Banks", "code": "BANKS"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] > 0
    assert body["name"] == "Banks"
    assert body["code"] == "BANKS"
    assert body["parentId"] is None


def test_create_industry_duplicate_code(client: TestClient) -> None:
    client.post("/industries", json={"name": "Banks", "code": "BANKS"})
    resp = client.post("/industries", json={"name": "Other", "code": "BANKS"})
    assert resp.status_code == 409


def test_create_industry_with_parent(client: TestClient) -> None:
    parent = client.post("/industries", json={"name": "Sector", "code": "SECTOR"}).json()
    resp = client.post(
        "/industries",
        json={"name": "Child", "code": "CHILD", "parentId": parent["id"]},
    )
    assert resp.status_code == 201
    assert resp.json()["parentId"] == parent["id"]


def test_create_industry_missing_parent(client: TestClient) -> None:
    resp = client.post(
        "/industries",
        json={"name": "Child", "code": "CHILD", "parentId": 9999},
    )
    assert resp.status_code == 404


def test_update_industry(client: TestClient) -> None:
    created = client.post("/industries", json={"name": "Banks", "code": "BANKS"}).json()
    resp = client.patch(f"/industries/{created['id']}", json={"name": "Banks Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Banks Updated"
    assert resp.json()["code"] == "BANKS"


def test_update_industry_not_found(client: TestClient) -> None:
    resp = client.patch("/industries/9999", json={"name": "x"})
    assert resp.status_code == 404


def test_delete_industry(client: TestClient) -> None:
    created = client.post("/industries", json={"name": "Banks", "code": "BANKS"}).json()
    resp = client.delete(f"/industries/{created['id']}")
    assert resp.status_code == 204
    remaining_ids = {i["id"] for i in client.get("/industries").json()}
    assert created["id"] not in remaining_ids


def test_delete_industry_with_child(client: TestClient) -> None:
    parent = client.post("/industries", json={"name": "Sector", "code": "SECTOR"}).json()
    client.post("/industries", json={"name": "Child", "code": "CHILD", "parentId": parent["id"]})
    resp = client.delete(f"/industries/{parent['id']}")
    assert resp.status_code == 409
