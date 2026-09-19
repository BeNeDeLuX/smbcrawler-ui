from __future__ import annotations

from fastapi import APIRouter

from .. import sc

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("/default")
def default_profile() -> dict:
    """The effective built-in smbcrawler profile collection (high-value rules,
    secret regexes) -- shown in the 'new scan' form."""
    return sc.default_profile()
