"""Monthly valuation snapshot tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.valuation import snapshot_valuations
from app.models import Valuation, ValuationItem

SNAPSHOT_DATE = date(2026, 11, 21)
PREVIOUS_DATE = date(2026, 10, 1)


def _snapshot(as_of: date) -> Any:
    return snapshot_valuations(as_of=as_of)


def test_snapshot_stores_total_and_class_breakdown(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
    backend_scope: Any,
    db_session: Session,
) -> None:
    asset_factory(name="SBER", ticker="SBER", quantity=10, currentPrice=300)
    asset_factory(name="RUB account", assetClassId=4, unit="RUB", quantity=1000)

    result = _snapshot(SNAPSHOT_DATE)
    assert result.snapshots == 1
    assert result.unpriced == 0

    snapshot = db_session.execute(select(Valuation)).scalar_one()
    assert snapshot.valuation_date == SNAPSHOT_DATE
    assert snapshot.total_value == 4000
    assert snapshot.currency == "RUB"
    assert snapshot.created_by == "backend"

    items = db_session.execute(
        select(ValuationItem).order_by(ValuationItem.asset_class_id)
    ).scalars().all()
    assert [(item.asset_class_id, item.value) for item in items] == [
        (1, 3000),
        (4, 1000),
    ]

    latest = client.get("/valuations/latest", headers=admin)
    assert latest.status_code == 200
    body = latest.json()
    assert body["totalValue"] == 4000.0
    assert [item["assetClassCode"] for item in body["items"]] == ["EQUITY", "CASH"]


def test_snapshot_is_idempotent_and_tracks_price_changes(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
    backend_scope: Any,
    db_session: Session,
) -> None:
    asset = asset_factory(name="SBER", ticker="SBER", quantity=10, currentPrice=300)

    _snapshot(SNAPSHOT_DATE)
    client.patch(f"/assets/{asset['id']}", headers=admin, json={"currentPrice": 350})
    _snapshot(SNAPSHOT_DATE)

    snapshots = db_session.execute(select(Valuation)).scalars().all()
    assert len(snapshots) == 1
    assert snapshots[0].total_value == 3500

    items = db_session.execute(select(ValuationItem)).scalars().all()
    assert len(items) == 1
    assert items[0].value == 3500


def test_snapshot_skips_portfolios_without_positions(
    client: TestClient,
    admin: dict[str, str],
    auth: Callable[..., dict[str, str]],
    asset_factory: Callable[..., dict[str, Any]],
    backend_scope: Any,
    db_session: Session,
) -> None:
    asset_factory(name="SBER", ticker="SBER", quantity=10, currentPrice=300)
    client.post("/users", headers=admin, json={"login": "bob"})
    client.get("/auth/me", headers=auth("bob"))

    result = _snapshot(SNAPSHOT_DATE)
    assert result.snapshots == 1
    assert result.skipped == 1
    assert len(db_session.execute(select(Valuation)).scalars().all()) == 1


def test_snapshot_skips_a_portfolio_that_could_not_be_valued(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
    backend_scope: Any,
) -> None:
    asset_factory(name="SBER", ticker="SBER", quantity=10)

    result = _snapshot(SNAPSHOT_DATE)
    assert result.snapshots == 0
    assert result.skipped == 1
    assert client.get("/valuations/latest", headers=admin).status_code == 404


def test_valuations_are_listed_newest_first(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
    backend_scope: Any,
) -> None:
    asset_factory(name="SBER", ticker="SBER", quantity=10, currentPrice=300)
    _snapshot(PREVIOUS_DATE)
    _snapshot(SNAPSHOT_DATE)

    listed = client.get("/valuations", headers=admin)
    assert listed.status_code == 200
    assert [item["valuationDate"] for item in listed.json()] == [
        "2026-11-21",
        "2026-10-01",
    ]

    filtered = client.get(
        "/valuations", headers=admin, params={"dateFrom": "2026-11-01"}
    ).json()
    assert [item["valuationDate"] for item in filtered] == ["2026-11-21"]

    limited = client.get("/valuations", headers=admin, params={"limit": 1}).json()
    assert [item["valuationDate"] for item in limited] == ["2026-11-21"]


def test_valuations_are_isolated_between_users(
    client: TestClient,
    admin: dict[str, str],
    auth: Callable[..., dict[str, str]],
    asset_factory: Callable[..., dict[str, Any]],
    backend_scope: Any,
) -> None:
    asset_factory(name="SBER", ticker="SBER", quantity=10, currentPrice=300)
    client.post("/users", headers=admin, json={"login": "bob"})
    bob = auth("bob")
    client.get("/auth/me", headers=bob)

    _snapshot(SNAPSHOT_DATE)

    assert client.get("/valuations", headers=bob).json() == []
    assert client.get("/valuations/latest", headers=bob).status_code == 404
