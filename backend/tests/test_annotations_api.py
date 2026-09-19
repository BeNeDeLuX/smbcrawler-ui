def test_annotation_upsert_and_overlay(client, sample_scan):
    sid = sample_scan["id"]

    # mark the only secret as a false positive
    r = client.put(
        f"/api/scans/{sid}/annotations",
        json={"kind": "secret", "ref": "iloveyou", "status": "false_positive", "note": "test acct"},
    )
    assert r.status_code == 200

    # overlay shows up on the secrets listing
    secrets = client.get(f"/api/scans/{sid}/secrets").json()
    assert secrets[0]["annotation"]["status"] == "false_positive"
    assert secrets[0]["annotation"]["note"] == "test acct"

    # update in place (no duplicate row)
    client.put(
        f"/api/scans/{sid}/annotations",
        json={"kind": "secret", "ref": "iloveyou", "status": "important", "note": ""},
    )
    listed = client.get(f"/api/scans/{sid}/annotations").json()
    assert len(listed) == 1
    assert listed[0]["status"] == "important"

    assert client.get(f"/api/scans/{sid}/annotations?status=reviewed").json() == []


def test_file_annotation_overlay_on_paths(client, sample_scan):
    sid, h = sample_scan["id"], sample_scan["content_hash"]
    client.put(
        f"/api/scans/{sid}/annotations",
        json={"kind": "file", "ref": h, "status": "reviewed", "note": ""},
    )
    res = client.get(f"/api/scans/{sid}/paths?downloaded_only=true").json()
    hit = next(p for p in res["items"] if p["content_hash"] == h)
    assert hit["annotation"]["status"] == "reviewed"
