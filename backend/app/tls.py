"""Manage the TLS certificate the `proxy` (nginx) container serves.

nginx always reads `active.crt`/`active.key` from the shared `certs` volume
and reloads whenever they change (it watches the directory). This module is
the only writer of those two files from the backend side; `proxy/entrypoint.sh`
is the only other writer, and only once, on first boot, if nothing exists yet.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

from .config import settings


class CertError(ValueError):
    """A certificate/key pair failed validation, or no cert is available yet."""


def _paths() -> dict[str, Path]:
    d = settings.certs_dir
    return {
        "active_crt": d / "active.crt",
        "active_key": d / "active.key",
        "self_crt": d / "self-signed.crt",
        "self_key": d / "self-signed.key",
        "custom_crt": d / "custom.crt",
        "custom_key": d / "custom.key",
        "source": d / "active.source",
    }


def _parse_pair(cert_pem: bytes, key_pem: bytes) -> x509.Certificate:
    try:
        cert = x509.load_pem_x509_certificate(cert_pem)
    except ValueError as exc:
        raise CertError(f"invalid PEM certificate: {exc}") from exc

    try:
        key = serialization.load_pem_private_key(key_pem, password=None)
    except TypeError as exc:
        raise CertError(
            "private key appears to be password-protected; remove the "
            "passphrase before uploading (e.g. `openssl rsa -in key.pem -out key.pem`)"
        ) from exc
    except ValueError as exc:
        raise CertError(f"invalid PEM private key: {exc}") from exc

    cert_pub = cert.public_key()
    key_pub = key.public_key()
    if not hasattr(cert_pub, "public_numbers") or not hasattr(key_pub, "public_numbers"):
        raise CertError("unsupported key type")
    if cert_pub.public_numbers() != key_pub.public_numbers():
        raise CertError("the certificate and private key do not match")

    now = datetime.datetime.now(datetime.timezone.utc)
    if cert.not_valid_after_utc < now:
        raise CertError(f"certificate expired on {cert.not_valid_after_utc.isoformat()}")

    return cert


def _describe(cert: x509.Certificate, source: str) -> dict[str, Any]:
    return {
        "present": True,
        "source": source,  # "self-signed" | "custom"
        "subject": cert.subject.rfc4514_string(),
        "issuer": cert.issuer.rfc4514_string(),
        "not_before": cert.not_valid_before_utc.isoformat(),
        "not_after": cert.not_valid_after_utc.isoformat(),
        "serial_number": format(cert.serial_number, "x"),
        "fingerprint_sha256": cert.fingerprint(hashes.SHA256()).hex(),
    }


def get_active() -> dict[str, Any]:
    p = _paths()
    if not p["active_crt"].is_file():
        return {"present": False}
    cert = x509.load_pem_x509_certificate(p["active_crt"].read_bytes())
    source = p["source"].read_text().strip() if p["source"].is_file() else "unknown"
    return _describe(cert, source)


def _activate(crt: Path, key: Path, source: str) -> None:
    p = _paths()
    p["active_crt"].parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace so nginx's directory watch sees a clean swap rather than
    # a half-written file (and so it can't briefly serve a mismatched pair).
    tmp_crt = p["active_crt"].with_name("active.crt.tmp")
    tmp_key = p["active_key"].with_name("active.key.tmp")
    tmp_crt.write_bytes(crt.read_bytes())
    tmp_key.write_bytes(key.read_bytes())
    tmp_crt.replace(p["active_crt"])
    tmp_key.replace(p["active_key"])
    p["source"].write_text(source)


def install_custom(cert_pem: bytes, key_pem: bytes) -> dict[str, Any]:
    cert = _parse_pair(cert_pem, key_pem)
    p = _paths()
    p["custom_crt"].parent.mkdir(parents=True, exist_ok=True)
    p["custom_crt"].write_bytes(cert_pem)
    p["custom_key"].write_bytes(key_pem)
    _activate(p["custom_crt"], p["custom_key"], "custom")
    return _describe(cert, "custom")


def reset_to_self_signed() -> dict[str, Any]:
    p = _paths()
    if not p["self_crt"].is_file() or not p["self_key"].is_file():
        raise CertError(
            "no self-signed certificate on disk yet (the proxy container "
            "generates one on first boot -- make sure it's running)"
        )
    _activate(p["self_crt"], p["self_key"], "self-signed")
    cert = x509.load_pem_x509_certificate(p["self_crt"].read_bytes())
    return _describe(cert, "self-signed")
