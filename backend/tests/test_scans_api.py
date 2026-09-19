def test_auth_required(client):
    from fastapi.testclient import TestClient
    from app.main import app

    anon = TestClient(app)
    assert anon.get("/api/scans").status_code == 401


def test_list_and_get_scan(client, sample_scan):
    rows = client.get("/api/scans").json()
    assert any(s["id"] == sample_scan["id"] for s in rows)
    one = client.get(f"/api/scans/{sample_scan['id']}").json()
    assert one["name"] == "sample"
    assert one["status"] == "imported"


def test_create_scan_validation(client):
    r = client.post("/api/scans", json={"name": "x", "targets": []})
    assert r.status_code == 422


def test_dry_run(client):
    r = client.post("/api/scans/dry-run", json={"targets": ["10.0.0.0/30"]})
    assert r.status_code == 200
    body = r.json()
    assert set(body["targets"]) == {"10.0.0.1:445", "10.0.0.2:445"}
    assert "secrets" in body["profiles"]


def test_delete_scan(client, sample_scan):
    sid = sample_scan["id"]
    assert client.delete(f"/api/scans/{sid}").status_code == 204
    assert client.get(f"/api/scans/{sid}").status_code == 404
    assert not sample_scan["dir"].exists()
