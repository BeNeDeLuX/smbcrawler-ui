from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import tls

router = APIRouter(prefix="/api/tls", tags=["tls"])


@router.get("/certificate", summary="Currently active TLS certificate (self-signed or custom)")
def get_certificate() -> dict:
    return tls.get_active()


@router.post("/certificate", summary="Upload a custom PEM certificate + private key")
async def upload_certificate(
    cert: UploadFile = File(..., description="PEM certificate (leaf, optionally with chain appended)"),
    key: UploadFile = File(..., description="PEM private key, unencrypted"),
) -> dict:
    cert_pem = await cert.read()
    key_pem = await key.read()
    try:
        return tls.install_custom(cert_pem, key_pem)
    except tls.CertError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/certificate", summary="Revert to the auto-generated self-signed certificate")
def reset_certificate() -> dict:
    try:
        return tls.reset_to_self_signed()
    except tls.CertError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
