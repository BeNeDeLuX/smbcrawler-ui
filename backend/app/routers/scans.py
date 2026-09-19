from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import sc
from ..config import settings
from ..crypto import encrypt_json
from ..db import get_db
from ..deps import get_scan, new_scan_dir
from ..models import Credential, Scan, ScanSource, ScanStatus
from ..queue import get_queue, request_cancel
from ..schemas import DryRunIn, ScanCreate, ScanOut
from ..worker import jobs

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.get("", response_model=list[ScanOut])
def list_scans(db: Session = Depends(get_db)) -> list[Scan]:
    return list(db.scalars(select(Scan).order_by(Scan.created_at.desc())))


@router.post("", response_model=ScanOut, status_code=201)
def create_scan(body: ScanCreate, db: Session = Depends(get_db)) -> Scan:
    if not body.targets and not body.hostfile_text:
        raise HTTPException(status_code=422, detail="provide targets or a hostfile")

    sid, d = new_scan_dir()
    scan = Scan(
        id=sid,
        name=body.name,
        source=ScanSource.crawl,
        status=ScanStatus.queued,
        dir=str(d),
        params={
            "targets": body.targets,
            "hostfile_text": body.hostfile_text,
            "options": body.options.model_dump(),
            "extra_profile_yaml": body.extra_profile_yaml,
            "no_default": body.no_default,
        },
        progress={},
    )
    scan.credential = Credential(blob=encrypt_json(body.credentials.model_dump()))
    db.add(scan)
    db.commit()

    job = get_queue().enqueue(jobs.run_scan, str(sid), job_id=f"scan-{sid}", result_ttl=3600, failure_ttl=86400)
    scan.rq_job_id = job.id
    db.commit()
    db.refresh(scan)
    return scan


@router.post("/dry-run")
def dry_run(body: DryRunIn) -> dict:
    try:
        return sc.dry_run(body.targets, body.extra_profile_yaml)
    except Exception as exc:  # bad CIDR, bad YAML, ...
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{scan_id}", response_model=ScanOut)
def get_one(scan: Scan = Depends(get_scan)) -> Scan:
    return scan


@router.get("/{scan_id}/summary")
def scan_summary(scan: Scan = Depends(get_scan)) -> dict:
    from .. import crawl_reader

    p = Path(scan.dir) / "output.crwl"
    if not p.is_file():
        return {"config": None, "summary": {}}
    with crawl_reader.connect(p) as conn:
        return {"config": crawl_reader.config(conn), "summary": crawl_reader.summary(conn)}


@router.post("/{scan_id}/cancel")
def cancel(scan: Scan = Depends(get_scan)) -> dict:
    if scan.status not in (ScanStatus.queued, ScanStatus.running):
        raise HTTPException(status_code=409, detail=f"scan is {scan.status.value}")
    request_cancel(str(scan.id))
    try:
        get_queue().fetch_job(scan.rq_job_id or "").cancel()  # if still queued
    except Exception:
        pass
    return {"ok": True}


@router.delete("/{scan_id}", status_code=204)
def delete_scan(scan: Scan = Depends(get_scan), db: Session = Depends(get_db)) -> None:
    import shutil

    request_cancel(str(scan.id))
    d = Path(scan.dir)
    db.delete(scan)
    db.commit()
    if d.is_dir() and d.parent == settings.scans_dir:
        shutil.rmtree(d, ignore_errors=True)


@router.get("/{scan_id}/log", response_class=PlainTextResponse)
def scan_log(scan: Scan = Depends(get_scan), tail: int = 20000) -> str:
    p = Path(scan.dir) / "scan.log"
    if not p.is_file():
        return ""
    data = p.read_bytes()
    return data[-tail:].decode("utf-8", errors="replace")


@router.get("/{scan_id}/events")
async def events(scan_id: uuid.UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")

    async def gen():
        last = None
        while True:
            db.expire_all()
            fresh = db.get(Scan, scan_id)
            if fresh is None:
                break
            payload = {
                "status": fresh.status.value,
                "progress": fresh.progress or {},
            }
            blob = json.dumps(payload)
            if blob != last:
                yield f"data: {blob}\n\n"
                last = blob
            if fresh.status not in (ScanStatus.queued, ScanStatus.running):
                yield f"event: done\ndata: {blob}\n\n"
                break
            await asyncio.sleep(2)

    return StreamingResponse(gen(), media_type="text/event-stream")
