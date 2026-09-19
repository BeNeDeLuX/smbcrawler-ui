from __future__ import annotations

import posixpath
import sqlite3
import tarfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import new_scan_dir
from ..models import Credential, Scan, ScanSource, ScanStatus
from ..queue import get_queue
from ..schemas import ScanOut
from ..worker import jobs

router = APIRouter(prefix="/api/imports", tags=["imports"])

_CHUNK = 1 << 20


async def _save(upload: UploadFile, dest: Path) -> None:
    with dest.open("wb") as fh:
        while chunk := await upload.read(_CHUNK):
            fh.write(chunk)


def _looks_like_crwl(path: Path) -> bool:
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            con.execute("SELECT smbcrawler_version FROM config LIMIT 1").fetchone()
            return True
        finally:
            con.close()
    except sqlite3.DatabaseError:
        return False


@router.post("", response_model=ScanOut, status_code=201)
async def import_crawl(
    db: Session = Depends(get_db),
    name: str = Form(...),
    crawl: UploadFile = File(..., description="the .crwl SQLite database"),
    content: UploadFile | None = File(
        None, description="optional tar of the <crawl>.d directory contents"
    ),
) -> Scan:
    sid, d = new_scan_dir()
    crawl_path = d / "output.crwl"
    await _save(crawl, crawl_path)

    if not _looks_like_crwl(crawl_path):
        import shutil

        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=422, detail="not a valid smbcrawler .crwl database")

    if content is not None:
        tar_path = d / "_content_upload"
        await _save(content, tar_path)
        content_root = d / "output.crwl.d"
        content_root.mkdir(exist_ok=True)
        try:
            with tarfile.open(tar_path) as tf:
                # Keep only regular files/dirs under content/. smbcrawler's tree/
                # dir is just a symlink mirror we don't need, and absolute-path
                # symlinks would (rightly) be rejected by the data filter anyway.
                members = [
                    m
                    for m in tf.getmembers()
                    if (m.isreg() or m.isdir())
                    and posixpath.normpath(m.name).split("/", 1)[0] == "content"
                ]
                if not members:
                    raise HTTPException(
                        status_code=422,
                        detail="content archive has no content/ directory "
                        "(tar the *inside* of <crawl>.d)",
                    )
                tf.extractall(content_root, members=members, filter="data")
        except (tarfile.TarError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"bad content archive: {exc}") from exc
        finally:
            tar_path.unlink(missing_ok=True)

    scan = Scan(
        id=sid,
        name=name,
        source=ScanSource.import_,
        status=ScanStatus.imported,
        dir=str(d),
        params={"imported": True},
        progress={},
    )
    db.add(scan)
    db.commit()

    job = get_queue().enqueue(jobs.index_scan, str(sid), job_id=f"index-{sid}", result_ttl=3600, failure_ttl=86400)
    scan.rq_job_id = job.id
    db.commit()
    db.refresh(scan)
    return scan
