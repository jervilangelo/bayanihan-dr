def test_liveness_reports_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "bfc-cms"
    assert "version" in body


def test_readiness_checks_database_and_schema_revision(client):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["database"] == "ok"
    assert body["schema_revision"] == "0001"
