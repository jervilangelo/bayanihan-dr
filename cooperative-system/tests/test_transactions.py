import re
from decimal import Decimal


def _stock(client, item_id) -> Decimal:
    return Decimal(client.get(f"/api/v1/inventory/{item_id}").json()["quantity_on_hand"])


def test_sale_reduces_stock_and_computes_amount(client, farmer, item):
    resp = client.post(
        "/api/v1/transactions",
        json={"type": "sale", "farmer_id": farmer["id"], "item_id": item["id"], "quantity": "3"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert re.fullmatch(r"TXN-\d{7}", body["reference"])
    assert Decimal(body["unit_price"]) == Decimal("1450")
    assert Decimal(body["amount"]) == Decimal("4350.00")
    assert _stock(client, item["id"]) == Decimal("97")


def test_sale_exceeding_stock_is_rejected_and_stock_unchanged(client, farmer, item):
    resp = client.post(
        "/api/v1/transactions",
        json={"type": "sale", "farmer_id": farmer["id"], "item_id": item["id"], "quantity": "101"},
    )
    assert resp.status_code == 409
    assert _stock(client, item["id"]) == Decimal("100")
    assert client.get("/api/v1/transactions").json()["total"] == 0


def test_sale_to_inactive_member_is_rejected(client, farmer, item):
    client.patch(f"/api/v1/farmers/{farmer['id']}", json={"status": "inactive"})
    resp = client.post(
        "/api/v1/transactions",
        json={"type": "sale", "farmer_id": farmer["id"], "item_id": item["id"], "quantity": "1"},
    )
    assert resp.status_code == 409


def test_purchase_of_produce_increases_stock(client, farmer, produce_item):
    resp = client.post(
        "/api/v1/transactions",
        json={
            "type": "purchase",
            "farmer_id": farmer["id"],
            "item_id": produce_item["id"],
            "quantity": "500",
            "unit_price": "21.50",
        },
    )
    assert resp.status_code == 201, resp.text
    assert Decimal(resp.json()["amount"]) == Decimal("10750.00")
    assert _stock(client, produce_item["id"]) == Decimal("500")


def test_purchase_of_non_produce_is_rejected(client, farmer, item):
    resp = client.post(
        "/api/v1/transactions",
        json={"type": "purchase", "farmer_id": farmer["id"], "item_id": item["id"], "quantity": "1"},
    )
    assert resp.status_code == 422


def test_contribution_increases_share_capital(client, farmer):
    for amount in ("500.00", "250.50"):
        resp = client.post(
            "/api/v1/transactions",
            json={"type": "contribution", "farmer_id": farmer["id"], "amount": amount},
        )
        assert resp.status_code == 201, resp.text
    member = client.get(f"/api/v1/farmers/{farmer['id']}").json()
    assert Decimal(member["share_capital"]) == Decimal("750.50")


def test_transaction_shape_is_validated(client, farmer, item):
    # contribution must not reference an item
    assert client.post(
        "/api/v1/transactions",
        json={"type": "contribution", "farmer_id": farmer["id"], "item_id": item["id"], "amount": "10"},
    ).status_code == 422
    # contribution requires a positive amount
    assert client.post(
        "/api/v1/transactions",
        json={"type": "contribution", "farmer_id": farmer["id"], "amount": "0"},
    ).status_code == 422
    # sale requires item and quantity
    assert client.post(
        "/api/v1/transactions", json={"type": "sale", "farmer_id": farmer["id"]}
    ).status_code == 422
    # unknown type
    assert client.post(
        "/api/v1/transactions", json={"type": "refund", "farmer_id": farmer["id"], "amount": "5"}
    ).status_code == 422


def test_unknown_farmer_or_item_returns_404(client, farmer, item):
    assert client.post(
        "/api/v1/transactions", json={"type": "contribution", "farmer_id": 999999, "amount": "5"}
    ).status_code == 404
    assert client.post(
        "/api/v1/transactions",
        json={"type": "sale", "farmer_id": farmer["id"], "item_id": 999999, "quantity": "1"},
    ).status_code == 404


def test_list_get_and_filter_transactions(client, farmer, item):
    client.post("/api/v1/transactions", json={"type": "contribution", "farmer_id": farmer["id"], "amount": "100"})
    created = client.post(
        "/api/v1/transactions",
        json={"type": "sale", "farmer_id": farmer["id"], "item_id": item["id"], "quantity": "2"},
    ).json()

    listing = client.get("/api/v1/transactions", params={"farmer_id": farmer["id"]}).json()
    assert listing["total"] == 2
    sales = client.get("/api/v1/transactions", params={"type": "sale"}).json()
    assert sales["total"] == 1

    fetched = client.get(f"/api/v1/transactions/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["reference"] == created["reference"]
    assert client.get("/api/v1/transactions/888888").status_code == 404


def test_transactions_are_immutable(client, farmer):
    txn = client.post(
        "/api/v1/transactions", json={"type": "contribution", "farmer_id": farmer["id"], "amount": "100"}
    ).json()
    assert client.delete(f"/api/v1/transactions/{txn['id']}").status_code == 405
    assert client.patch(f"/api/v1/transactions/{txn['id']}", json={"amount": "1"}).status_code == 405
