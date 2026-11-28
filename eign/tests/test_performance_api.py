"""API tests of the performance endpoint."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, Valuation


def _add_snapshot(
    db_session: Session, login: str, day: date, total: str
) -> None:
    user = db_session.query(User).filter(User.login == login).one()
    db_session.add(
        Valuation(
            owner_id=user.id,
            valuation_date=day,
            total_value=Decimal(total),
            currency="RUB",
            created_by="backend",
        )
    )
    db_session.flush()


def _performance(client: TestClient, headers: dict[str, str], **params: Any) -> dict[str, Any]:
    response = client.get("/portfolio/performance", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_performance_without_snapshots(
    client: TestClient, admin: dict[str, str]
) -> None:
    body = _performance(client, admin)
    assert body["periodStart"] is None
    assert body["twr"] is None
    assert body["periods"] == 0
    assert body["monthly"] == []


def test_performance_over_two_snapshots(
    client: TestClient, admin: dict[str, str], db_session: Session
) -> None:
    client.get("/auth/me", headers=admin)
    _add_snapshot(db_session, "alice", date(2026, 1, 1), "1000")
    _add_snapshot(db_session, "alice", date(2026, 2, 1), "1100")

    body = _performance(client, admin)
    assert body["baseCurrency"] == "RUB"
    assert body["periodStart"] == "2026-01-01"
    assert body["periodEnd"] == "2026-02-01"
    assert body["initialValue"] == 1000.0
    assert body["finalValue"] == 1100.0
    assert body["twr"] == 0.1
    assert body["contributions"] == 0.0
    assert body["periods"] == 1
    assert body["monthly"][0]["returnPct"] == 0.1


def test_performance_filters_by_date(
    client: TestClient, admin: dict[str, str], db_session: Session
) -> None:
    client.get("/auth/me", headers=admin)
    _add_snapshot(db_session, "alice", date(2026, 1, 1), "1000")
    _add_snapshot(db_session, "alice", date(2026, 2, 1), "1100")

    body = _performance(client, admin, dateFrom="2026-02-01")
    assert body["twr"] is None
    assert body["periods"] == 0
    assert body["initialValue"] == 1100.0


def test_risk_free_rate_precedence(
    client: TestClient, admin: dict[str, str], db_session: Session
) -> None:
    """Query parameter → own setting → service default."""
    client.get("/auth/me", headers=admin)
    _add_snapshot(db_session, "alice", date(2026, 1, 1), "1000")
    _add_snapshot(db_session, "alice", date(2026, 2, 1), "1100")
    _add_snapshot(db_session, "alice", date(2026, 3, 1), "1200")
    _add_snapshot(db_session, "alice", date(2026, 4, 1), "1300")

    own_zero = client.patch("/auth/me", headers=admin, json={"riskFreeRate": 0.0})
    assert own_zero.status_code == 200
    sharpe_at_zero = _performance(client, admin)["sharpe"]
    assert sharpe_at_zero is not None

    client.patch("/auth/me", headers=admin, json={"riskFreeRate": 0.5})
    sharpe_with_setting = _performance(client, admin)["sharpe"]
    assert sharpe_with_setting is not None
    assert sharpe_with_setting < sharpe_at_zero

    # The query parameter still overrides the stored preference.
    sharpe_with_param = _performance(client, admin, riskFreeRate=0.0)["sharpe"]
    assert sharpe_with_param == sharpe_at_zero


def test_performance_counts_trades_as_capital_flows(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
    db_session: Session,
) -> None:
    asset = asset_factory(name="SBER", ticker="SBER", quantity=10, currentPrice=100)
    client.get("/auth/me", headers=admin)

    trade = client.post(
        "/trades",
        headers=admin,
        json={
            "assetId": asset["id"],
            "tradeType": "BUY",
            "tradeDate": "2026-01-15",
            "quantity": 10,
            "price": 100,
            "fee": 50,
        },
    )
    assert trade.status_code == 201

    _add_snapshot(db_session, "alice", date(2026, 1, 1), "0")
    _add_snapshot(db_session, "alice", date(2026, 2, 1), "1100")

    body = _performance(client, admin)
    assert body["contributions"] == 1050.0
    assert body["twr"] is None
    assert body["periods"] == 0
