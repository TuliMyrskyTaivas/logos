"""Trade plan tests: cumulative execution across the trades of a month."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from .conftest import EQUITY_CLASS_ID


def _plan(client: TestClient, headers: dict[str, str], **overrides: Any) -> Any:
    payload: dict[str, Any] = {
        "month": "2025-01-15",
        "direction": "BUY",
        "amount": 100000,
        "assetClassId": EQUITY_CLASS_ID,
    }
    if "quantity" in overrides:
        payload.pop("amount")
    if "assetId" in overrides and "assetClassId" not in overrides:
        payload.pop("assetClassId")
    payload.update(overrides)
    return client.post("/trade-plan", headers=headers, json=payload)


def _trade(
    client: TestClient,
    headers: dict[str, str],
    asset_id: int,
    *,
    quantity: float = 1,
    price: float = 100,
    trade_date: str = "2025-01-15",
    trade_type: str = "BUY",
) -> Any:
    return client.post(
        "/trades",
        headers=headers,
        json={
            "assetId": asset_id,
            "tradeType": trade_type,
            "tradeDate": trade_date,
            "quantity": quantity,
            "price": price,
        },
    )


def _plans(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    response = client.get("/trade-plan", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_asset_classes_are_listed(client: TestClient, admin: dict[str, str]) -> None:
    response = client.get("/asset-classes", headers=admin)
    assert response.status_code == 200
    assert [item["code"] for item in response.json()] == [
        "EQUITY",
        "BOND",
        "REIT",
        "CASH",
        "METAL",
    ]
    assert response.json()[0]["name"] == "\u0410\u043a\u0446\u0438\u0438"


def test_create_and_list_plans(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    class_plan = _plan(client, admin, month="2025-01-20")
    assert class_plan.status_code == 201
    assert class_plan.json()["month"] == "2025-01-01"
    assert class_plan.json()["status"] == "planned"
    assert class_plan.json()["filled"] == 0

    unit_plan = _plan(client, admin, month="2025-02-01", assetId=asset["id"], quantity=100)
    assert unit_plan.status_code == 201
    assert unit_plan.json()["quantity"] == 100
    assert unit_plan.json()["amount"] is None
    assert unit_plan.json()["assetClassId"] == EQUITY_CLASS_ID

    assert [plan["month"] for plan in _plans(client, admin)] == ["2025-01-01", "2025-02-01"]
    assert len(client.get("/trade-plan", headers=admin, params={"month": "2025-02-28"}).json()) == 1
    assert len(client.get("/trade-plan", headers=admin, params={"assetId": asset["id"]}).json()) == 1


def test_plan_requires_exactly_one_target_metric(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")

    neither = client.post(
        "/trade-plan",
        headers=admin,
        json={"month": "2025-01-01", "direction": "BUY", "assetClassId": EQUITY_CLASS_ID},
    )
    assert neither.status_code == 422

    both = client.post(
        "/trade-plan",
        headers=admin,
        json={
            "month": "2025-01-01",
            "direction": "BUY",
            "assetId": asset["id"],
            "amount": 1000,
            "quantity": 10,
        },
    )
    assert both.status_code == 422

    units_without_asset = client.post(
        "/trade-plan",
        headers=admin,
        json={
            "month": "2025-01-01",
            "direction": "BUY",
            "assetClassId": EQUITY_CLASS_ID,
            "quantity": 10,
        },
    )
    assert units_without_asset.status_code == 422


def test_plan_validates_targets(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")

    assert _plan(client, admin, assetClassId=999).status_code == 409
    assert _plan(client, admin, assetClassId=None, assetId=999).status_code == 404
    assert _plan(client, admin, assetId=asset["id"], assetClassId=2).status_code == 422
    assert _plan(client, admin, amount=0).status_code == 422
    assert _plan(client, admin, direction="HOLD").status_code == 422


def test_update_switches_target_metric_and_cancels(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    plan = _plan(client, admin, assetId=asset["id"]).json()

    switched = client.patch(
        f"/trade-plan/{plan['id']}", headers=admin, json={"quantity": 100}
    )
    assert switched.status_code == 200
    assert switched.json()["quantity"] == 100
    assert switched.json()["amount"] is None

    back = client.patch(
        f"/trade-plan/{plan['id']}", headers=admin, json={"amount": 5000}
    )
    assert back.status_code == 200
    assert back.json()["amount"] == 5000
    assert back.json()["quantity"] is None

    cancelled = client.patch(
        f"/trade-plan/{plan['id']}", headers=admin, json={"status": "cancelled"}
    )
    assert cancelled.json()["status"] == "cancelled"


def test_update_switches_from_quantity_to_amount_in_one_request(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    """A form sends the whole state, clearing one unit and setting the other."""
    asset = asset_factory(name="SBER")
    plan = _plan(client, admin, assetId=asset["id"], quantity=10).json()
    assert plan["amount"] is None

    switched = client.patch(
        f"/trade-plan/{plan['id']}",
        headers=admin,
        json={"quantity": None, "amount": 5000},
    )
    assert switched.status_code == 200
    body = switched.json()
    assert body["amount"] == 5000
    assert body["quantity"] is None


def test_delete_plan(client: TestClient, admin: dict[str, str]) -> None:
    plan = _plan(client, admin).json()
    assert client.delete(f"/trade-plan/{plan['id']}", headers=admin).status_code == 204
    assert _plans(client, admin) == []
    assert client.delete(f"/trade-plan/{plan['id']}", headers=admin).status_code == 404


def test_plans_are_isolated_between_users(
    client: TestClient,
    admin: dict[str, str],
    auth: Callable[..., dict[str, str]],
) -> None:
    plan = _plan(client, admin).json()
    client.post("/users", headers=admin, json={"login": "bob"})
    bob = auth("bob")

    assert _plans(client, bob) == []
    assert client.patch(
        f"/trade-plan/{plan['id']}", headers=bob, json={"amount": 1}
    ).status_code == 404
    assert client.delete(f"/trade-plan/{plan['id']}", headers=bob).status_code == 404


def test_plan_is_executed_by_cumulative_quantity(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="REIT A", assetClassId=3, unit="unit")
    _plan(client, admin, assetId=asset["id"], quantity=100)

    _trade(client, admin, asset["id"], quantity=25, price=1000)
    _trade(client, admin, asset["id"], quantity=70, price=1000, trade_date="2025-01-20")
    partial = _plans(client, admin)[0]
    assert partial["filled"] == 95
    assert partial["status"] == "planned"

    _trade(client, admin, asset["id"], quantity=10, price=1000, trade_date="2025-01-25")
    finished = _plans(client, admin)[0]
    assert finished["filled"] == 105
    assert finished["status"] == "executed"


def test_plan_is_executed_by_cumulative_amount(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _plan(client, admin, assetId=asset["id"], amount=40000)

    _trade(client, admin, asset["id"], quantity=10, price=1000)
    _trade(client, admin, asset["id"], quantity=20, price=1500, trade_date="2025-01-20")
    assert _plans(client, admin)[0]["filled"] == 40000
    assert _plans(client, admin)[0]["status"] == "executed"


def test_class_plan_sums_trades_of_all_assets_in_the_class(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    sber = asset_factory(name="SBER")
    gazp = asset_factory(name="GAZP")
    bond = asset_factory(name="OFZ", assetClassId=2, unit="bond")
    _plan(client, admin, assetClassId=EQUITY_CLASS_ID, amount=50000)

    _trade(client, admin, sber["id"], quantity=10, price=1000)
    _trade(client, admin, gazp["id"], quantity=20, price=1500)
    _trade(client, admin, bond["id"], quantity=100, price=1000)
    partial = _plans(client, admin)[0]
    assert partial["filled"] == 40000
    assert partial["status"] == "planned"

    _trade(client, admin, gazp["id"], quantity=7, price=1000, trade_date="2025-01-31")
    finished = _plans(client, admin)[0]
    assert finished["filled"] == 47000
    assert finished["status"] == "planned"

    _trade(client, admin, sber["id"], quantity=3, price=1000, trade_date="2025-01-31")
    assert _plans(client, admin)[0]["status"] == "executed"


def test_direction_and_month_must_match(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _plan(client, admin, assetId=asset["id"], quantity=10, direction="SELL")
    _plan(client, admin, assetId=asset["id"], quantity=10, month="2025-02-01")

    _trade(client, admin, asset["id"], quantity=10, price=100)

    assert [plan["status"] for plan in _plans(client, admin)] == ["planned", "planned"]


def test_cancelled_plan_is_never_executed(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    plan = _plan(client, admin, assetId=asset["id"], quantity=10).json()
    client.patch(f"/trade-plan/{plan['id']}", headers=admin, json={"status": "cancelled"})

    _trade(client, admin, asset["id"], quantity=50, price=100)

    cancelled = _plans(client, admin)[0]
    assert cancelled["status"] == "cancelled"
    assert cancelled["filled"] == 50


def test_status_filter_uses_derived_state(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _plan(client, admin, assetId=asset["id"], quantity=10)
    _plan(client, admin, assetId=asset["id"], quantity=100, month="2025-02-01")

    _trade(client, admin, asset["id"], quantity=10, price=100)

    executed = client.get("/trade-plan", headers=admin, params={"status": "executed"}).json()
    planned = client.get("/trade-plan", headers=admin, params={"status": "planned"}).json()
    assert [plan["month"] for plan in executed] == ["2025-01-01"]
    assert [plan["month"] for plan in planned] == ["2025-02-01"]


def test_deleting_asset_deletes_its_plans(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _plan(client, admin, assetId=asset["id"], quantity=10)

    assert client.delete(f"/assets/{asset['id']}", headers=admin).status_code == 204
    assert _plans(client, admin) == []
