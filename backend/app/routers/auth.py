from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from ..auth import clear_session, is_https_request, issue_session, verify_password
from ..schemas import LoginIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    if not verify_password(body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wrong password")
    issue_session(response, secure=is_https_request(request))
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    clear_session(response)
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> dict:
    from ..auth import _serializer
    from ..config import settings
    from itsdangerous import BadSignature

    raw = request.cookies.get(settings.session_cookie)
    if not raw:
        return {"authenticated": False}
    try:
        _serializer.loads(raw, max_age=settings.session_max_age)
        return {"authenticated": True}
    except BadSignature:
        return {"authenticated": False}
