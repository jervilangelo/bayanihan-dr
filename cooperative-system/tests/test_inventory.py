from decimal import Decimal

from tests.conftest import item_payload


def test_create_inventory_item(client):
    resp = client.post("/api/v1/inventory", json=item_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["sku"] == "FERT-UREA-50"
    assert Decimal(body["quantity_on_hand"]) == Decimal("100")
    assert body["is_low_stock"] is False


def test_duplicate_sku_is_rejected_with_409(client, item):
    assert client.post("/api/v1/inventory", json=item_payload(name="dup")).status_code == 409


def test_invalid_inventory_payloads_are_rejected_with_422(client):
    assert client.post("/api/v1/inventory", json=item_payload(unit_price="-5")).status_code == 422
    assert client.post("/api/v1/inventory", json=item_payload(quantity_on_hand="-1")).status_code == 422
    assert client.post("/api/v1/inventory", json=item_payload(category="spaceship")).status_code == 422
    assert client.post("/api/v1/inventory", json=item_payload(sku="bad sku!")).status_code == 422


def test_get_item_and_404(client, item):
    assert client.get(f"/api/v1/inventory/{item['id']}").status_code == 200
    assert client.get("/api/v1/inventory/424242").status_code == 404


def test_low_stock_flag_and_filter(client):
    client.post("/api/v1/inventory", json=item_payload(sku="A-001", quantity_on_hand="5", reorder_level="10"))
    client.post("/api/v1/inventory", json=item_payload(sku="A-002", quantity_on_hand="50", reorder_level="10"))

    low = client.get("/api/v1/inventory", params={"low_stock": True}).json()
    assert [i["sku"] for i in low["items"]] == ["A-001"]
    assert low["items"][0]["is_low_stock"] is True


def test_filter_by_category(client):
    client.post("/api/v1/inventory", json=item_payload(sku="S-001", category="seed"))
    client.post("/api/v1/inventory", json=item_payload(sku="F-001", category="fertilizer"))
    seeds = client.get("/api/v1/inventory", params={"category": "seed"}).json()
    assert seeds["total"] == 1 and seeds["items"][0]["sku"] == "S-001"


def test_patch_item(client, item):
    resp = client.patch(f"/api/v1/inventory/{item['id']}", json={"unit_price": "1500.00", "quantity_on_hand": "80"})
    assert resp.status_code == 200
    assert Decimal(resp.json()["unit_price"]) == Decimal("1500")
    assert Decimal(resp.json()["quantity_on_hand"]) == Decimal("80")


def test_delete_item_without_transactions(client, item):
    assert client.delete(f"/api/v1/inventory/{item['id']}").status_code == 204
    assert client.get(f"/api/v1/inventory/{item['id']}").status_code == 404


def test_delete_item_with_transactions_is_blocked(client, farmer, item):
    client.post(
        "/api/v1/transactions",
        json={"type": "sale", "farmer_id": farmer["id"], "item_id": item["id"], "quantity": "1"},
    )
    assert client.delete(f"/api/v1/inventory/{item['id']}").status_code == 409
