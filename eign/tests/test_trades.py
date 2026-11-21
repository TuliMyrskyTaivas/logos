"""Trade registration tests: position recalculation and ownership."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def _trade(
    client: TestClient,
    headers: dict[str, str],
    asset_id: int,
    *,
    trade_type: str = "BUY",
    quantity: float = 10,
    price: float = 100,
    fee: float = 0,
    trade_date: str = "2025-01-15",
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
            "fee": fee,
        },
    )


def _position(client: TestClient, headers: dict[str, str], asset_id: int) -> dict[str, Any]:
    response = client.get(f"/assets/{asset_id}", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_buy_updates_quantity_and_average(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")

    created = _trade(client, admin, asset["id"], quantity=10, price=100, fee=50)
    assert created.status_code == 201
    assert created.json()["assetId"] == asset["id"]
    assert created.json()["currency"] == "RUB"

    position = _position(client, admin, asset["id"])
    assert position["quantity"] == 10
    assert position["avgPurchasePrice"] == 105
    assert position["currentPrice"] == 100


def test_second_buy_uses_weighted_average(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _trade(client, admin, asset["id"], quantity=10, price=100, fee=50)
    _trade(client, admin, asset["id"], quantity=10, price=200, trade_date="2025-02-15")

    position = _position(client, admin, asset["id"])
    assert position["quantity"] == 20
    assert position["avgPurchasePrice"] == 152.5


def test_sell_keeps_average_and_reduces_quantity(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _trade(client, admin, asset["id"], quantity=20, price=100)
    sell = _trade(
        client,
        admin,
        asset["id"],
        trade_type="SELL",
        quantity=5,
        price=210,
        trade_date="2025-02-15",
    )
    assert sell.status_code == 201

    position = _position(client, admin, asset["id"])
    assert position["quantity"] == 15
    assert position["avgPurchasePrice"] == 100
    assert position["currentPrice"] == 210


def test_selling_everything_resets_average(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _trade(client, admin, asset["id"], quantity=10, price=100)
    _trade(
        client,
        admin,
        asset["id"],
        trade_type="SELL",
        quantity=10,
        price=150,
        trade_date="2025-02-15",
    )

    position = _position(client, admin, asset["id"])
    assert position["quantity"] == 0
    assert position["avgPurchasePrice"] is None


def test_position_reentry_uses_new_cost(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _trade(client, admin, asset["id"], quantity=10, price=100)
    _trade(
        client,
        admin,
        asset["id"],
        trade_type="SELL",
        quantity=10,
        price=150,
        trade_date="2025-02-15",
    )
    _trade(client, admin, asset["id"], quantity=5, price=300, trade_date="2025-03-15")

    position = _position(client, admin, asset["id"])
    assert position["quantity"] == 5
    assert position["avgPurchasePrice"] == 300


def test_oversell_is_rejected_and_position_is_unchanged(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _trade(client, admin, asset["id"], quantity=10, price=100)

    oversell = _trade(
        client,
        admin,
        asset["id"],
        trade_type="SELL",
        quantity=15,
        price=120,
        trade_date="2025-02-15",
    )
    assert oversell.status_code == 409

    position = _position(client, admin, asset["id"])
    assert position["quantity"] == 10
    assert client.get("/trades", headers=admin).json() != []


def test_sell_before_purchase_is_rejected(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _trade(client, admin, asset["id"], quantity=10, price=100, trade_date="2025-02-15")
    too_early = _trade(
        client,
        admin,
        asset["id"],
        trade_type="SELL",
        quantity=5,
        price=120,
        trade_date="2025-01-15",
    )
    assert too_early.status_code == 409
    assert _position(client, admin, asset["id"])["quantity"] == 10


def test_delete_trade_recalculates_position(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    first = _trade(client, admin, asset["id"], quantity=10, price=100)
    _trade(client, admin, asset["id"], quantity=10, price=200, trade_date="2025-02-15")

    assert client.delete(f"/trades/{first.json()['id']}", headers=admin).status_code == 204

    position = _position(client, admin, asset["id"])
    assert position["quantity"] == 10
    assert position["avgPurchasePrice"] == 200


def test_update_trade_recalculates_position(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    trade = _trade(client, admin, asset["id"], quantity=10, price=100)

    updated = client.patch(
        f"/trades/{trade.json()['id']}", headers=admin, json={"quantity": 20, "price": 110}
    )
    assert updated.status_code == 200
    assert updated.json()["quantity"] == 20

    position = _position(client, admin, asset["id"])
    assert position["quantity"] == 20
    assert position["avgPurchasePrice"] == 110


def test_corrupting_trade_into_oversell_is_rejected(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    buy = _trade(client, admin, asset["id"], quantity=10, price=100)
    _trade(
        client,
        admin,
        asset["id"],
        trade_type="SELL",
        quantity=8,
        price=120,
        trade_date="2025-02-15",
    )

    response = client.patch(
        f"/trades/{buy.json()['id']}", headers=admin, json={"quantity": 5}
    )
    assert response.status_code == 409
    assert _position(client, admin, asset["id"])["quantity"] == 2


def test_derived_position_fields_are_locked_after_trades(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _trade(client, admin, asset["id"], quantity=10, price=100)

    response = client.patch(
        f"/assets/{asset['id']}", headers=admin, json={"quantity": 999}
    )
    assert response.status_code == 409
    assert _position(client, admin, asset["id"])["quantity"] == 10


def test_trade_currency_must_match_position(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    response = client.post(
        "/trades",
        headers=admin,
        json={
            "assetId": asset["id"],
            "tradeType": "BUY",
            "tradeDate": "2025-01-15",
            "quantity": 1,
            "price": 100,
            "currency": "USD",
        },
    )
    assert response.status_code == 422


def test_trade_list_filters(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    sber = asset_factory(name="SBER")
    ofz = asset_factory(name="ОФЗ", assetClassId=2, unit="bond")
    _trade(client, admin, sber["id"], trade_date="2025-01-15")
    _trade(client, admin, ofz["id"], trade_date="2025-02-15")
    _trade(
        client,
        admin,
        sber["id"],
        trade_type="SELL",
        quantity=1,
        trade_date="2025-03-15",
    )

    assert len(client.get("/trades", headers=admin).json()) == 3
    assert len(client.get("/trades", headers=admin, params={"assetId": sber["id"]}).json()) == 2
    assert len(client.get("/trades", headers=admin, params={"tradeType": "SELL"}).json()) == 1
    ranged = client.get(
        "/trades", headers=admin, params={"dateFrom": "2025-02-01", "dateTo": "2025-02-28"}
    ).json()
    assert len(ranged) == 1
    assert ranged[0]["assetId"] == ofz["id"]


def test_deleting_position_removes_its_trades(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    _trade(client, admin, asset["id"], quantity=10, price=100)

    assert client.delete(f"/assets/{asset['id']}", headers=admin).status_code == 204
    assert client.get(f"/assets/{asset['id']}", headers=admin).status_code == 404
    assert client.get("/trades", headers=admin).json() == []


def test_trades_are_isolated_between_users(
    client: TestClient,
    admin: dict[str, str],
    auth: Callable[..., dict[str, str]],
    asset_factory: Callable[..., dict[str, Any]],
) -> None:
    asset = asset_factory(name="SBER")
    trade = _trade(client, admin, asset["id"], quantity=10)
    client.post("/users", headers=admin, json={"login": "bob"})
    bob = auth("bob")

    assert client.get("/trades", headers=bob).json() == []
    assert _trade(client, bob, asset["id"], quantity=1).status_code == 404
    assert client.patch(
        f"/trades/{trade.json()['id']}", headers=bob, json={"quantity": 1}
    ).status_code == 404
    assert client.delete(
        f"/trades/{trade.json()['id']}", headers=bob
    ).status_code == 404
