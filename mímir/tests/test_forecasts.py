"""Tests for the scenarios and forecasts endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_company(client: TestClient) -> dict:
    industry = client.post("/industries", json={"name": "IT", "code": "TEST_IT"}).json()
    return client.post(
        "/companies",
        json={"name": "Yandex", "industryId": industry["id"]},
    ).json()


def _scenario_by_code(client: TestClient, code: str) -> dict:
    scenarios = client.get("/scenarios").json()
    return next(s for s in scenarios if s["code"] == code)


def test_list_scenarios(client: TestClient) -> None:
    scenarios = client.get("/scenarios").json()
    assert len(scenarios) >= 13
    codes = {s["code"] for s in scenarios}
    assert "base" in codes and "severe_stress" in codes


def test_list_scenario_variables(client: TestClient) -> None:
    severe = _scenario_by_code(client, "severe_stress")
    variables = client.get(f"/scenarios/{severe['id']}/variables").json()
    pairs = {(v["metricCode"], v["operator"], v["value"]) for v in variables}
    assert pairs == {("revenue", "multiply", 0.8), ("cogs", "multiply", 1.2)}


def test_scenario_variables_not_found(client: TestClient) -> None:
    resp = client.get("/scenarios/9999/variables")
    assert resp.status_code == 404


def test_upload_forecasts(client: TestClient) -> None:
    company = _create_company(client)

    resp = client.put(
        f"/companies/{company['id']}/forecasts",
        json={"forecastYear": 2026, "scenarios": [{"scenarioCode": "base", "metrics": {"revenue": 150.0}}]},
    )
    assert resp.status_code == 201
    assert resp.json()["scenarioCount"] == 1
    assert resp.json()["metricCount"] == 1

    # Unknown scenario -> 404
    bad = client.put(
        f"/companies/{company['id']}/forecasts",
        json={"forecastYear": 2026, "scenarios": [{"scenarioCode": "nope", "metrics": {"revenue": 1.0}}]},
    )
    assert bad.status_code == 404

    # Unknown metric is skipped (tolerant upload)
    skip = client.put(
        f"/companies/{company['id']}/forecasts",
        json={"forecastYear": 2026, "scenarios": [{"scenarioCode": "base", "metrics": {"no_such": 1.0, "revenue": 200.0}}]},
    )
    assert skip.status_code == 201
    assert skip.json()["metricCount"] == 1  # only 'revenue' stored
