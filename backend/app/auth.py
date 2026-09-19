from __future__ import annotations

import hmac
import time

from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import settings

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="smbui-session")


def verify_password(candidate: str) -> bool:
    return hmac.compare_digest(candidate.encode(), settings.app_password.encode())


def issue_session(response: Response) -> None:
    token = _serializer.dumps({"t": int(time.time())})
    response.set_cookie(
        settings.session_cookie,
        token,
        max_age=settings.session_max_age,
        httponly=True,
        samesite="lax",
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
