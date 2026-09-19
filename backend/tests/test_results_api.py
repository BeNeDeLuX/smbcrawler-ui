def test_summary_and_targets(client, sample_scan):
    sid = sample_scan["id"]
    r = client.get(f"/api/scans/{sid}/summary")
    assert r.status_code == 200
    assert r.json()["summary"]["number_secrets"] == 1

    r = client.get(f"/api/scans/{sid}/targets")
    assert [t["name"] for t in r.json()] == ["samba:445"]


def test_shares_filters(client, sample_scan):
    sid = sample_scan["id"]
    assert len(client.get(f"/api/scans/{sid}/shares").json()) == 1
    assert client.get(f"/api/scans/{sid}/shares?writable=true").json() == []
    assert len(client.get(f"/api/scans/{sid}/shares?readable=true").json()) == 1


def test_paths_and_tree(client, sample_scan):
    sid = sample_scan["id"]
    res = client.get(f"/api/scans/{sid}/paths?downloaded_only=true").json()
    paths = {p["path"] for p in res["items"]}
    assert "config\\default.ini" in paths
    assert any(p["high_value"] for p in res["items"])

    roots = client.get(f"/api/scans/{sid}/tree?target=samba:445&share=public").json()
    names = {n["name"] for n in roots}
    assert {"config", "hello.txt"} <= names
    cfg = next(n for n in roots if n["name"] == "config")
    assert cfg["child_count"] == 1
    kids = client.get(
        f"/api/scans/{sid}/tree?target=samba:445&share=public&parent_id={cfg['id']}"
    ).json()
    assert kids[0]["name"] == "default.ini"


def test_secrets_and_preview(client, sample_scan):
    sid, h = sample_scan["id"], sample_scan["content_hash"]
    secrets = client.get(f"/api/scans/{sid}/secrets").json()
    assert secrets[0]["secret"] == "iloveyou"
    assert secrets[0]["path"].endswith("default.ini")

    prev = client.get(f"/api/scans/{sid}/files/{h}/preview")
    assert "iloveyou" in prev.text
    assert client.get(f"/api/scans/{sid}/files/{h}").status_code == 200
    assert client.get(f"/api/scans/{sid}/files/{'0' * 64}").status_code == 404


def test_stats(client, sample_scan):
    sid = sample_scan["id"]
    st = client.get(f"/api/scans/{sid}/stats").json()
    assert st["totals"]["files"] == 3  # default.ini + hello.txt + notes.txt
    exts = {e["ext"]: e["count"] for e in st["by_extension"]}
    assert exts.get("ini") == 1 and exts.get("txt") == 2
    assert st["by_share"][0]["share"] == "public"
    assert st["by_share"][0]["count"] == 3
    assert sum(b["count"] for b in st["size_buckets"]) == 3
    assert st["largest"][0]["size"] >= st["largest"][-1]["size"]

    sec = st["secrets"]
    assert sec["total"] == 1 and sec["unique"] == 1
    assert sec["by_share"][0] == {"target": "samba:445", "share": "public", "count": 1}
    assert sec["by_rule"][0]["count"] == 1
    assert sec["by_rule"][0]["rule"] != "(unmatched)"


def test_search(client, sample_scan):
    sid = sample_scan["id"]
    res = client.get(f"/api/scans/{sid}/search?q=iloveyou").json()
    assert res["indexed"] is True
    assert res["total"] == 1
    assert res["items"][0]["path"].endswith("default.ini")
    assert "iloveyou" in res["items"][0]["snippet"]


def test_fetch_paths(client, sample_scan):
    sid = sample_scan["id"]
    paths = client.get(f"/api/scans/{sid}/paths").json()["items"]
    downloaded = next(p for p in paths if p["path"].endswith("default.ini"))
    notdl = next(p for p in paths if p["path"].endswith("notes.txt"))

    # already have the bytes -> no-op
    r = client.post(f"/api/scans/{sid}/paths/{downloaded['id']}/fetch", json={})
    assert r.status_code == 200 and r.json()["already"] is True

    # host 'samba' is unresolvable in the test env -> clean 502, not a crash
    r = client.post(f"/api/scans/{sid}/paths/{notdl['id']}/fetch", json={})
    assert r.status_code == 502

    # unknown path id
    assert client.post(f"/api/scans/{sid}/paths/999999/fetch", json={}).status_code == 404


def test_report_json(client, sample_scan):
    sid = sample_scan["id"]
    r = client.get(f"/api/scans/{sid}/report?format=json&section=secrets")
    assert r.status_code == 200
    assert "iloveyou" in r.text
