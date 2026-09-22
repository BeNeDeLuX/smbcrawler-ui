from __future__ import annotations

import hmac
import time

from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import settings

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="smbui-session")


def verify_password(candidate: str) -> bool:
    return hmac.compare_digest(candidate.encode(), settings.app_password.encode())


def issue_session(response: Response, *, secure: bool = False) -> None:
    token = _serializer.dumps({"t": int(time.time())})
    response.set_cookie(
        settings.session_cookie,
        token,
        max_age=settings.session_max_age,
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def is_https_request(request: Request) -> bool:
    """True if the request reached us over TLS -- directly, or via the `proxy`
    container, which sets X-Forwarded-Proto. uvicorn doesn't trust that header
    for request.url.scheme unless configured to, so check it explicitly.
    """
    return (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "").lower() == "https"
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(settings.session_cookie)


def require_auth(request: Request) -> None:
    """FastAPI dependency: 401 unless a valid, unexpired session cookie is present."""
    raw = request.cookies.get(settings.session_cookie)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    try:
        _serializer.loads(raw, max_age=settings.session_max_age)
    except BadSignature as exc:  # also covers SignatureExpired
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired session"
        ) from exc
