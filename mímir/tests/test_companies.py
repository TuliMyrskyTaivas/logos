"""Tests for the companies endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ._json_types import IndustryJson


def _create_industry(client: TestClient, code: str = "TEST_IT") -> IndustryJson:
    return client.post("/industries", json={"name": "IT", "code": code}).json()


def test_create_company(client: TestClient) -> None:
    industry = _create_industry(client)
    resp = client.post(
        "/companies",
        json={"name": "Yandex", "ticker": "YNDX", "industryId": industry["id"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] > 0
    assert body["name"] == "Yandex"
    assert body["ticker"] == "YNDX"
    assert body["industryId"] == industry["id"]


def test_create_company_bad_industry(client: TestClient) -> None:
    resp = client.post("/companies", json={"name": "Yandex", "industryId": 9999})
    assert resp.status_code == 409


def test_list_companies_filters(client: TestClient) -> None:
    ind_a = client.post("/industries", json={"name": "A", "code": "A"}).json()
    ind_b = client.post("/industries", json={"name": "B", "code": "B"}).json()
    client.post("/companies", json={"name": "Alpha", "industryId": ind_a["id"]})
    client.post("/companies", json={"name": "Beta", "industryId": ind_b["id"]})

    assert len(client.get("/companies").json()) == 2
    assert len(client.get(f"/companies?industryId={ind_a['id']}").json()) == 1

    by_name = client.get("/companies", params={"name": "Beta"}).json()
    assert len(by_name) == 1 and by_name[0]["name"] == "Beta"


def test_update_company(client: TestClient) -> None:
    industry = _create_industry(client)
    company = client.post("/companies", json={"name": "Yandex", "industryId": industry["id"]}).json()
    resp = client.patch(f"/companies/{company['id']}", json={"inn": "7700000000"})
    assert resp.status_code == 200
    assert resp.json()["inn"] == "7700000000"


def test_update_company_not_found(client: TestClient) -> None:
    resp = client.patch("/companies/9999", json={"name": "x"})
    assert resp.status_code == 404


def test_delete_company(client: TestClient) -> None:
    industry = _create_industry(client)
    company = client.post("/companies", json={"name": "Yandex", "industryId": industry["id"]}).json()
    resp = client.delete(f"/companies/{company['id']}")
    assert resp.status_code == 204
    assert client.get("/companies").json() == []
