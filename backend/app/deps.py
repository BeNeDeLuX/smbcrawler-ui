from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import Depends, HTTPException, Path as PathParam
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Scan


def get_scan(
    scan_id: uuid.UUID = PathParam(...),
    db: Session = Depends(get_db),
) -> Scan:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")
    return scan


def scan_dir(scan: Scan) -> Path:
    return Path(scan.dir)


def crawl_db_path(scan: Scan) -> Path:
    return Path(scan.dir) / "output.crwl"


def require_crawl_db(scan: Scan = Depends(get_scan)) -> Path:
    p = crawl_db_path(scan)
    if not p.is_file():
        raise HTTPException(status_code=409, detail="scan has no results yet")
    return p


def new_scan_dir() -> tuple[uuid.UUID, Path]:
    sid = uuid.uuid4()
    d = settings.scans_dir / str(sid)
    d.mkdir(parents=True, exist_ok=True)
    return sid, d
