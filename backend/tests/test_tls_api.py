import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _make_cert(cn: str, *, before_days: int = -1, after_days: int = 365, key=None):
    key = key or rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now + datetime.timedelta(days=before_days))
        .not_valid_after(now + datetime.timedelta(days=after_days))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def test_no_certificate_initially(client):
    r = client.get("/api/tls/certificate")
    assert r.status_code == 200
    assert r.json() == {"present": False}


def test_upload_and_reset(client):
    cert_pem, key_pem = _make_cert("smbui-test")

    r = client.post(
        "/api/tls/certificate",
        files={"cert": ("cert.pem", cert_pem), "key": ("key.pem", key_pem)},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["present"] is True
    assert body["source"] == "custom"
    assert "smbui-test" in body["subject"]
    assert len(body["fingerprint_sha256"]) == 64

    got = client.get("/api/tls/certificate").json()
    assert got["source"] == "custom"
    assert got["fingerprint_sha256"] == body["fingerprint_sha256"]

    # no self-signed baseline was ever generated in this test env (that's the
    # proxy container's job on boot) -> reset must fail cleanly, not crash
    r = client.delete("/api/tls/certificate")
    assert r.status_code == 422


def test_mismatched_key_rejected(client):
    cert_pem, _ = _make_cert("cert-a")
    _, other_key_pem = _make_cert("cert-b")

    r = client.post(
        "/api/tls/certificate",
        files={"cert": ("cert.pem", cert_pem), "key": ("key.pem", other_key_pem)},
    )
    assert r.status_code == 422
    assert "match" in r.json()["detail"]


def test_expired_certificate_rejected(client):
    cert_pem, key_pem = _make_cert("expired", before_days=-60, after_days=-30)
    r = client.post(
        "/api/tls/certificate",
        files={"cert": ("cert.pem", cert_pem), "key": ("key.pem", key_pem)},
    )
    assert r.status_code == 422
    assert "expired" in r.json()["detail"]


def test_garbage_rejected(client):
    r = client.post(
        "/api/tls/certificate",
        files={"cert": ("cert.pem", b"not a cert"), "key": ("key.pem", b"not a key")},
    )
    assert r.status_code == 422
