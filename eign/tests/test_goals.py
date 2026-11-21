"""Portfolio goal tests: saving targets and comparing them with reality."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, Valuation

EQUITY = 1
CASH = 4


def _goal(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get("/goals", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _progress(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get("/goals/progress", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _put(client: TestClient, headers: dict[str, str], **payload: Any) -> Any:
    body: dict[str, Any] = {"currency": "RUB", "allocations": []}
    body.update(payload)
    return client.put("/goals", headers=headers, json=body)


def _snapshot(db_session: Session, login: str, day: date, total: str) -> None:
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


def test_default_goal_is_empty(client: TestClient, admin: dict[str, str]) -> None:
    goal = _goal(client, admin)
    assert goal["id"] is None
    assert goal["currency"] == "RUB"
    assert goal["targetTotalValue"] is None
    assert goal["targetAnnualReturn"] is None
    assert goal["allocations"] == []


def test_save_and_read_goal(client: TestClient, admin: dict[str, str]) -> None:
    saved = _put(
        client,
        admin,
        targetTotalValue=2000000,
        targetAnnualReturn=0.12,
        allocations=[
            {"assetClassId": EQUITY, "targetWeight": 0.6},
            {"assetClassId": CASH, "targetWeight": 0.4},
        ],
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["targetTotalValue"] == 2000000.0
    assert body["targetAnnualReturn"] == 0.12
    assert [item["assetClassCode"] for item in body["allocations"]] == ["EQUITY", "CASH"]

    reread = _goal(client, admin)
    assert reread["id"] == body["id"]
    assert reread["targetTotalValue"] == 2000000.0


def test_allocations_are_replaced(client: TestClient, admin: dict[str, str]) -> None:
    _put(
        client,
        admin,
        allocations=[
            {"assetClassId": EQUITY, "targetWeight": 0.5},
            {"assetClassId": CASH, "targetWeight": 0.5},
        ],
    )
    updated = _put(
        client, admin, allocations=[{"assetClassId": EQUITY, "targetWeight": 1.0}]
    )
    assert updated.status_code == 200
    assert [item["assetClassCode"] for item in updated.json()["allocations"]] == ["EQUITY"]


def test_allocation_weights_must_sum_to_one(
    client: TestClient, admin: dict[str, str]
) -> None:
    response = _put(
        client, admin, allocations=[{"assetClassId": EQUITY, "targetWeight": 0.5}]
    )
    assert response.status_code == 422
    assert "sum to 1.0" in response.json()["detail"]


def test_allocation_validation(client: TestClient, admin: dict[str, str]) -> None:
    duplicate = _put(
        client,
        admin,
        allocations=[
            {"assetClassId": EQUITY, "targetWeight": 0.5},
            {"assetClassId": EQUITY, "targetWeight": 0.5},
        ],
    )
    assert duplicate.status_code == 422

    unknown = _put(
        client, admin, allocations=[{"assetClassId": 999, "targetWeight": 1.0}]
    )
    assert unknown.status_code == 409

    bad_currency = _put(client, admin, currency="RUBLE")
    assert bad_currency.status_code == 422

    negative_target = _put(client, admin, targetTotalValue=-1)
    assert negative_target.status_code == 422

    bad_return = _put(client, admin, targetAnnualReturn=20)
    assert bad_return.status_code == 422


def test_goals_are_isolated_between_users(
    client: TestClient, admin: dict[str, str], auth: Callable[..., dict[str, str]]
) -> None:
    _put(client, admin, targetTotalValue=1000)
    client.post("/users", headers=admin, json={"login": "bob"})
    bob = auth("bob")

    assert _goal(client, bob)["id"] is None
    assert _progress(client, bob)["targetTotalValue"] is None


def test_value_progress(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
) -> None:
    asset_factory(name="SBER", ticker="SBER", quantity=10, currentPrice=100)
    _put(client, admin, targetTotalValue=2000)

    body = _progress(client, admin)
    assert body["currentValueBase"] == 1000.0
    assert body["targetTotalValue"] == 2000.0
    assert body["targetTotalValueBase"] == 2000.0
    assert body["valueProgress"] == 0.5
    assert body["valueGapBase"] == 1000.0
    assert body["baseCurrency"] == "RUB"


def test_goal_in_gold_is_converted_with_the_metal_price(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
) -> None:
    asset_factory(name="SBER", ticker="SBER", quantity=10, currentPrice=100)
    price = client.post(
        "/prices",
        headers=admin,
        json={"instrument": "XAU", "instrumentType": "metal", "price": 7000},
    )
    assert price.status_code == 201

    _put(client, admin, currency="XAU", targetTotalValue=2)

    body = _progress(client, admin)
    assert body["currency"] == "XAU"
    assert body["targetTotalValue"] == 2.0
    assert body["targetTotalValueBase"] == 14000.0
    assert body["valueProgress"] == 0.071429


def test_allocation_progress(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
) -> None:
    asset_factory(name="SBER", ticker="SBER", quantity=6, currentPrice=100)
    asset_factory(name="RUB account", assetClassId=CASH, unit="RUB", quantity=400)
    _put(
        client,
        admin,
        targetTotalValue=1000,
        allocations=[
            {"assetClassId": EQUITY, "targetWeight": 0.6},
            {"assetClassId": CASH, "targetWeight": 0.4},
        ],
    )

    body = _progress(client, admin)
    allocations = {item["assetClassCode"]: item for item in body["allocations"]}
    assert allocations["EQUITY"]["targetWeight"] == 0.6
    assert allocations["EQUITY"]["actualWeight"] == 0.6
    assert allocations["EQUITY"]["delta"] == 0.0
    assert allocations["CASH"]["actualWeight"] == 0.4
    assert allocations["CASH"]["delta"] == 0.0


def test_return_progress_uses_annualised_twr(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
    db_session: Session,
) -> None:
    asset_factory(name="SBER", ticker="SBER", quantity=10, currentPrice=100)
    client.get("/auth/me", headers=admin)
    _snapshot(db_session, "alice", date(2026, 1, 1), "1000")
    _snapshot(db_session, "alice", date(2026, 2, 1), "1100")
    _put(client, admin, targetAnnualReturn=0.2)

    body = _progress(client, admin)
    assert body["actualAnnualReturn"] is not None
    assert body["targetAnnualReturn"] == 0.2
    assert body["returnGap"] == round(
        body["actualAnnualReturn"] - body["targetAnnualReturn"], 6
    )


def test_progress_without_history_has_no_return(
    client: TestClient, admin: dict[str, str]
) -> None:
    _put(client, admin, targetAnnualReturn=0.2)

    body = _progress(client, admin)
    assert body["actualAnnualReturn"] is None
    assert body["returnGap"] is None
