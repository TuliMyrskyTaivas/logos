"""Portfolio position (asset) CRUD tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from .conftest import METAL_CLASS_ID


def test_create_and_list_positions(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    sber = asset_factory(name="SBER", ticker="SBER")
    asset_factory(name="ОФЗ 26238", assetClassId=2, unit="bond", isin="RU000A1038V6")

    assert sber["quantity"] == 0
    assert sber["assetClassCode"] == "EQUITY"
    assert sber["currency"] == "RUB"

    listed = client.get("/assets", headers=admin)
    assert listed.status_code == 200
    assert [asset["name"] for asset in listed.json()] == ["SBER", "ОФЗ 26238"]
    assert listed.json()[1]["assetClassCode"] == "BOND"

    filtered = client.get("/assets", headers=admin, params={"assetClassId": 2})
    assert [asset["name"] for asset in filtered.json()] == ["ОФЗ 26238"]


def test_get_single_position(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    response = client.get(f"/assets/{asset['id']}", headers=admin)
    assert response.status_code == 200
    assert response.json()["name"] == "SBER"


def test_unknown_asset_class_is_rejected(
    client: TestClient, admin: dict[str, str]
) -> None:
    response = client.post(
        "/assets",
        headers=admin,
        json={"assetClassId": 999, "name": "SBER", "unit": "share"},
    )
    assert response.status_code == 409


def test_duplicate_name_is_rejected(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset_factory(name="SBER")
    response = client.post(
        "/assets",
        headers=admin,
        json={"assetClassId": 1, "name": "SBER", "unit": "share"},
    )
    assert response.status_code == 409


def test_metal_positions_require_metal_code(
    client: TestClient, admin: dict[str, str]
) -> None:
    missing = client.post(
        "/assets",
        headers=admin,
        json={"assetClassId": METAL_CLASS_ID, "name": "Золото", "unit": "g"},
    )
    assert missing.status_code == 422

    wrong = client.post(
        "/assets",
        headers=admin,
        json={"assetClassId": 1, "name": "SBER", "unit": "share", "metalCode": "XAU"},
    )
    assert wrong.status_code == 422

    gold = client.post(
        "/assets",
        headers=admin,
        json={
            "assetClassId": METAL_CLASS_ID,
            "name": "Золото",
            "unit": "g",
            "metalCode": "XAU",
        },
    )
    assert gold.status_code == 201
    assert gold.json()["metalCode"] == "XAU"
    assert gold.json()["assetClassCode"] == "METAL"


def test_update_position(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER", quantity=10, avgPurchasePrice=100)

    response = client.patch(
        f"/assets/{asset['id']}",
        headers=admin,
        json={"name": "Сбербанк", "custodian": "Брокер", "currentPrice": 250.5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Сбербанк"
    assert body["custodian"] == "Брокер"
    assert body["currentPrice"] == 250.5
    assert body["quantity"] == 10


def test_null_in_required_fields_is_ignored_and_nullable_fields_are_cleared(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER", ticker="SBER", custodian="Брокер")

    response = client.patch(
        f"/assets/{asset['id']}",
        headers=admin,
        json={"name": None, "unit": None, "ticker": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "SBER"
    assert body["unit"] == "share"
    assert body["ticker"] is None
    assert body["custodian"] == "Брокер"


def test_delete_position(
    client: TestClient, admin: dict[str, str], asset_factory: Callable[..., dict[str, Any]]
) -> None:
    asset = asset_factory(name="SBER")
    assert client.delete(f"/assets/{asset['id']}", headers=admin).status_code == 204
    assert client.get(f"/assets/{asset['id']}", headers=admin).status_code == 404


def test_positions_are_isolated_between_users(
    client: TestClient,
    admin: dict[str, str],
    auth: Callable[..., dict[str, str]],
    asset_factory: Callable[..., dict[str, Any]],
) -> None:
    asset = asset_factory(name="SBER")
    client.post("/users", headers=admin, json={"login": "bob"})
    bob = auth("bob")

    assert client.get("/assets", headers=bob).json() == []
    assert client.get(f"/assets/{asset['id']}", headers=bob).status_code == 404
    assert client.delete(f"/assets/{asset['id']}", headers=bob).status_code == 404
    assert (
        client.patch(
            f"/assets/{asset['id']}", headers=bob, json={"name": "HACK"}
        ).status_code
        == 404
    )
