from decimal import Decimal

from tests.conftest import farmer_payload


def test_create_farmer_returns_201_with_server_fields(client):
    resp = client.post("/api/v1/farmers", json=farmer_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] > 0
    assert body["member_code"] == "BFC-00001"
    assert body["last_name"] == "Dela Cruz"
    assert Decimal(body["share_capital"]) == Decimal("0")
    assert body["created_at"] and body["updated_at"]


def test_duplicate_member_code_is_rejected_with_409(client, farmer):
    resp = client.post("/api/v1/farmers", json=farmer_payload(first_name="Other"))
    assert resp.status_code == 409


def test_invalid_farmer_payloads_are_rejected_with_422(client):
    assert client.post("/api/v1/farmers", json=farmer_payload(member_code="X-1")).status_code == 422
    assert client.post("/api/v1/farmers", json=farmer_payload(status="retired")).status_code == 422
    assert client.post("/api/v1/farmers", json=farmer_payload(farm_size_hectares="-1")).status_code == 422
    assert client.post("/api/v1/farmers", json=farmer_payload(first_name="")).status_code == 422


def test_share_capital_cannot_be_set_directly(client):
    resp = client.post("/api/v1/farmers", json=farmer_payload(share_capital="99999.00"))
    assert resp.status_code == 422


def test_get_farmer_by_id_and_404_for_unknown(client, farmer):
    assert client.get(f"/api/v1/farmers/{farmer['id']}").json()["member_code"] == "BFC-00001"
    assert client.get("/api/v1/farmers/999999").status_code == 404


def test_list_farmers_supports_pagination_search_and_status_filter(client):
    for i in range(1, 6):
        status = "inactive" if i == 5 else "active"
        client.post(
            "/api/v1/farmers",
            json=farmer_payload(member_code=f"BFC-{i:05d}", last_name=f"Santos{i}", status=status),
        )

    page = client.get("/api/v1/farmers", params={"limit": 2, "offset": 0}).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert page["limit"] == 2 and page["offset"] == 0

    search = client.get("/api/v1/farmers", params={"q": "santos3"}).json()
    assert [f["member_code"] for f in search["items"]] == ["BFC-00003"]

    inactive = client.get("/api/v1/farmers", params={"status": "inactive"}).json()
    assert inactive["total"] == 1


def test_list_limit_is_bounded(client):
    assert client.get("/api/v1/farmers", params={"limit": 1000}).status_code == 422


def test_patch_farmer_updates_only_given_fields(client, farmer):
    resp = client.patch(f"/api/v1/farmers/{farmer['id']}", json={"status": "inactive", "barangay": "Carolina"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "inactive"
    assert body["barangay"] == "Carolina"
    assert body["first_name"] == "Maria"


def test_patch_cannot_change_member_code(client, farmer):
    resp = client.patch(f"/api/v1/farmers/{farmer['id']}", json={"member_code": "BFC-09999"})
    assert resp.status_code == 422


def test_delete_farmer_without_transactions(client, farmer):
    assert client.delete(f"/api/v1/farmers/{farmer['id']}").status_code == 204
    assert client.get(f"/api/v1/farmers/{farmer['id']}").status_code == 404


def test_delete_farmer_with_transactions_is_blocked(client, farmer):
    client.post(
        "/api/v1/transactions",
        json={"type": "contribution", "farmer_id": farmer["id"], "amount": "500.00"},
    )
    assert client.delete(f"/api/v1/farmers/{farmer['id']}").status_code == 409
