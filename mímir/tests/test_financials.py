"""Tests for the financial data endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_industry_and_company(client: TestClient) -> tuple[dict, dict]:
    industry = client.post("/industries", json={"name": "Banks", "code": "BANKS"}).json()
    company = client.post(
        "/companies",
        json={"name": "Sber", "ticker": "SBER", "industryId": industry["id"]},
    ).json()
    return industry, company


def test_upload_and_get_financials(client: TestClient) -> None:
    _, company = _seed_industry_and_company(client)

    upload = {
        "companyName": "Sber",
        "ticker": "SBER",
        "industryName": "Banks",
        "metrics": {
            "revenue": {"2023": 1000.0, "2024": 1200.0},
            "net_profit": {"2023": 100.0, "2024": None},
        },
        "ratios": {"2023": {"Test ratio": 1.5}, "2024": {"Test ratio": 1.6}},
    }
    resp = client.post("/financials", json=upload)
    assert resp.status_code == 201
    result = resp.json()
    assert result["companyId"] == company["id"]
    assert result["metricCount"] == 3  # revenue x2 + net_profit x1
    assert result["ratioCount"] == 2

    fin = client.get(f"/companies/{company['id']}/financials")
    assert fin.status_code == 200
    body = fin.json()
    assert body["companyId"] == company["id"]
    assert body["metrics"]["revenue"]["2023"] == 1000.0
    assert body["metrics"]["revenue"]["2024"] == 1200.0
    assert "2024" not in body["metrics"]["net_profit"]
    assert body["ratios"]["2023"]["Test ratio"] == 1.5


def test_upload_financials_industry_not_found(client: TestClient) -> None:
    upload = {
        "companyName": "Sber",
        "ticker": "SBER",
        "industryName": "No Such",
        "metrics": {"revenue": {"2023": 1000.0}},
        "ratios": {},
    }
    resp = client.post("/financials", json=upload)
    assert resp.status_code == 409


def test_get_financials_not_found(client: TestClient) -> None:
    resp = client.get("/companies/9999/financials")
    assert resp.status_code == 404
