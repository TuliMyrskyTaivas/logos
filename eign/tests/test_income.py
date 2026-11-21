"""Income plan/fact tests: CRUD, monthly summary and its effect on analytics."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, Valuation


def _income(
    client: TestClient, headers: dict[str, str], **payload: Any
) -> Any:
    body: dict[str, Any] = {"month": "2026-01-15", "incomeType": "dividend"}
    body.update(payload)
    return client.post("/income", headers=headers, json=body)


def _summary(
    client: TestClient, headers: dict[str, str], year: int = 2026
) -> dict[str, Any]:
    response = client.get("/income/summary", headers=headers, params={"year": year})
    assert response.status_code == 200, response.text
    return response.json()


def test_create_list_update_delete(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
) -> None:
    asset = asset_factory(name="REIT A", assetClassId=3, unit="unit")

    created = _income(
        client,
        admin,
        assetId=asset["id"],
        incomeType="dividend",
        plannedAmount=1000,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["month"] == "2026-01-01"
    assert body["currency"] == "RUB"
    assert body["actualAmount"] is None

    listed = client.get("/income", headers=admin).json()
    assert [row["id"] for row in listed] == [body["id"]]

    updated = client.patch(
        f"/income/{body['id']}", headers=admin, json={"actualAmount": 900, "note": "paid"}
    )
    assert updated.status_code == 200
    assert updated.json()["actualAmount"] == 900
    assert updated.json()["note"] == "paid"

    assert client.delete(f"/income/{body['id']}", headers=admin).status_code == 204
    assert client.get("/income", headers=admin).json() == []


def test_currency_defaults_to_position_currency(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
) -> None:
    asset = asset_factory(name="AAPL", currency="USD")
    created = _income(client, admin, assetId=asset["id"], plannedAmount=10)
    assert created.json()["currency"] == "USD"

    other = _income(client, admin, plannedAmount=5, incomeType="other")
    assert other.json()["currency"] == "RUB"


def test_income_requires_an_amount(client: TestClient, admin: dict[str, str]) -> None:
    response = _income(client, admin, incomeType="other")
    assert response.status_code == 422


def test_duplicate_income_is_rejected(
    client: TestClient, admin: dict[str, str]
) -> None:
    assert _income(client, admin, plannedAmount=100, incomeType="other").status_code == 201
    duplicate = _income(client, admin, plannedAmount=200, incomeType="other")
    assert duplicate.status_code == 409


def test_unknown_asset_is_rejected(
    client: TestClient, admin: dict[str, str]
) -> None:
    assert _income(client, admin, assetId=999, plannedAmount=100).status_code == 404


def test_income_is_isolated_between_users(
    client: TestClient,
    admin: dict[str, str],
    auth: Callable[..., dict[str, str]],
    asset_factory: Callable[..., dict[str, Any]],
) -> None:
    asset = asset_factory(name="SBER")
    row = _income(client, admin, assetId=asset["id"], plannedAmount=100).json()
    client.post("/users", headers=admin, json={"login": "bob"})
    bob = auth("bob")

    assert client.get("/income", headers=bob).json() == []
    assert client.patch(
        f"/income/{row['id']}", headers=bob, json={"plannedAmount": 1}
    ).status_code == 404
    assert client.delete(f"/income/{row['id']}", headers=bob).status_code == 404
    assert _income(client, bob, assetId=asset["id"], plannedAmount=1).status_code == 404


def test_summary_groups_months_and_converts_currency(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
) -> None:
    rub_asset = asset_factory(name="SBER")
    usd_asset = asset_factory(name="AAPL", currency="USD")

    _income(client, admin, assetId=rub_asset["id"], month="2026-01-10", plannedAmount=1000, actualAmount=900)
    _income(client, admin, assetId=rub_asset["id"], month="2026-02-10", incomeType="coupon", plannedAmount=500)
    _income(client, admin, assetId=usd_asset["id"], month="2026-02-20", plannedAmount=10)

    without_rate = _summary(client, admin)
    assert without_rate["unconvertedCount"] == 1
    assert without_rate["plannedYearToDate"] == 1500.0
    assert without_rate["actualYearToDate"] == 900.0

    rate = client.post(
        "/prices",
        headers=admin,
        json={"instrument": "USD", "instrumentType": "currency", "price": 80},
    )
    assert rate.status_code == 201

    with_rate = _summary(client, admin)
    assert with_rate["unconvertedCount"] == 0
    assert with_rate["plannedYearToDate"] == 2300.0
    months = {item["month"]: item for item in with_rate["months"]}
    assert months["2026-01-01"]["actualBase"] == 900.0
    assert months["2026-02-01"]["plannedBase"] == 1300.0
    assert months["2026-02-01"]["planCount"] == 2


def test_dashboard_shows_year_to_date_income(
    client: TestClient,
    admin: dict[str, str],
    asset_factory: Callable[..., dict[str, Any]],
) -> None:
    asset = asset_factory(name="SBER", quantity=10, currentPrice=100)
    _income(
        client,
        admin,
        assetId=asset["id"],
        month=f"{date.today().year}-01-10",
        plannedAmount=1000,
        actualAmount=800,
    )

    summary = client.get("/portfolio/summary", headers=admin).json()
    assert summary["incomeYearToDate"] == 800.0
    assert summary["incomePlanYearToDate"] == 1000.0


def test_income_is_included_in_performance(
    client: TestClient,
    admin: dict[str, str],
    db_session: Session,
) -> None:
    client.get("/auth/me", headers=admin)
    user = db_session.query(User).filter(User.login == "alice").one()
    for day, total in (("2026-01-01", "1000"), ("2026-02-01", "1050")):
        db_session.add(
            Valuation(
                owner_id=user.id,
                valuation_date=date.fromisoformat(day),
                total_value=Decimal(total),
                currency="RUB",
                created_by="backend",
            )
        )
    db_session.flush()

    assert _income(client, admin, month="2026-01-05", actualAmount=50, incomeType="other").status_code == 201

    body = client.get("/portfolio/performance", headers=admin).json()
    assert body["income"] == 50.0
    assert body["contributions"] == 0.0
    assert body["twr"] == 0.1
    assert body["simpleReturn"] == 0.1
