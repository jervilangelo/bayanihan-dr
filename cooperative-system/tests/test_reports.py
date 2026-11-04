from decimal import Decimal

from tests.conftest import farmer_payload


def test_summary_on_empty_database(client):
    body = client.get("/api/v1/reports/summary").json()
    assert body["members"] == {"total": 0, "active": 0, "inactive": 0}
    assert body["inventory"]["items"] == 0
    assert Decimal(body["inventory"]["stock_value"]) == Decimal("0")
    assert body["transactions"]["count"] == 0
    assert Decimal(body["total_share_capital"]) == Decimal("0")


def test_summary_reflects_activity(client, farmer, item, produce_item):
    client.post("/api/v1/farmers", json=farmer_payload(member_code="BFC-00002", status="inactive"))
    client.post("/api/v1/transactions", json={"type": "contribution", "farmer_id": farmer["id"], "amount": "300"})
    client.post(
        "/api/v1/transactions",
        json={"type": "sale", "farmer_id": farmer["id"], "item_id": item["id"], "quantity": "2"},
    )
    client.post(
        "/api/v1/transactions",
        json={"type": "purchase", "farmer_id": farmer["id"], "item_id": produce_item["id"], "quantity": "10"},
    )

    body = client.get("/api/v1/reports/summary").json()
    assert body["members"] == {"total": 2, "active": 1, "inactive": 1}
    assert body["inventory"]["items"] == 2
    # 98 bags * 1450 + 10 kg * 22
    assert Decimal(body["inventory"]["stock_value"]) == Decimal("142320.00")
    assert body["transactions"]["count"] == 3
    assert body["transactions"]["by_type"]["sale"] == {"count": 1, "amount": "2900.00"}
    assert body["transactions"]["by_type"]["purchase"] == {"count": 1, "amount": "220.00"}
    assert body["transactions"]["by_type"]["contribution"] == {"count": 1, "amount": "300.00"}
    assert Decimal(body["total_share_capital"]) == Decimal("300.00")
    assert body["generated_at"]
