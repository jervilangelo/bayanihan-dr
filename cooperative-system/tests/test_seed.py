from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app import seed
from app.models import Farmer, InventoryItem, Transaction


def _summary(client) -> dict:
    body = client.get("/api/v1/reports/summary").json()
    body.pop("generated_at")
    return body


def test_seed_populates_synthetic_dataset(client):
    result = seed.run(reset=False)
    assert result == {
        "farmers": seed.FARMER_COUNT,
        "inventory_items": len(seed.CATALOGUE),
        "transactions": seed.TRANSACTION_COUNT,
    }
    summary = _summary(client)
    assert summary["members"]["total"] == seed.FARMER_COUNT >= 1000
    assert summary["transactions"]["count"] == seed.TRANSACTION_COUNT


def test_seed_is_deterministic(client):
    seed.run(reset=False)
    first = _summary(client)
    seed.run(reset=True)
    second = _summary(client)
    assert first == second


def test_seed_refuses_non_empty_database_without_reset(client, farmer):
    with pytest.raises(seed.SeedError):
        seed.run(reset=False)


def test_seeded_ledger_is_internally_consistent(db_session):
    seed.run(reset=False)

    negative_stock = db_session.scalar(
        select(func.count()).select_from(InventoryItem).where(InventoryItem.quantity_on_hand < 0)
    )
    assert negative_stock == 0

    contributions = db_session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.type == "contribution")
    )
    share_capital = db_session.scalar(select(func.coalesce(func.sum(Farmer.share_capital), 0)))
    assert Decimal(contributions) == Decimal(share_capital)

    # every phone number uses the synthetic 0900-000-xxxx range
    phones = db_session.scalars(select(Farmer.phone)).all()
    assert all(p.startswith("0900-000-") for p in phones)
