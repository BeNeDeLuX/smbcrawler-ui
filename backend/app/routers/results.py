from __future__ import annotations

import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import crawl_reader
from ..db import get_db
from ..deps import get_scan, require_crawl_db
from ..models import Annotation, Scan
from ..schemas import FetchIn
from ..search import query as search_query

router = APIRouter(prefix="/api/scans", tags=["results"])

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_REPORT_FORMATS = {"html", "json", "yaml", "csv"}
_REPORT_SECTIONS = {
    "summary", "targets", "shares", "secrets", "secrets_unique",
    "secrets_cleanup_guide", "high_value_files",
}


def _content_dir(scan: Scan) -> Path:
    return Path(scan.dir) / "output.crwl.d" / "content"


def _annotation_map(db: Session, scan_id) -> dict[tuple[str, str], dict]:
    rows = db.scalars(select(Annotation).where(Annotation.scan_id == scan_id))
    return {
        (a.kind.value, a.ref): {"status": a.status.value, "note": a.note}
        for a in rows
    }


@router.get("/{scan_id}/targets", summary="Targets: reachability + share-listing outcome + timestamps")
def targets(
    db_path: Path = Depends(require_crawl_db),
    no_access: bool | None = Query(
        None, description="only reachable servers where share listing failed"
    ),
) -> list[dict]:
    with crawl_reader.connect(db_path) as conn:
        return crawl_reader.targets(conn, no_access=no_access)


@router.get("/{scan_id}/shares", summary="Shares with permission columns (filterable)")
def shares(
    db_path: Path = Depends(require_crawl_db),
    high_value: bool | None = None,
    readable: bool | None = None,
    writable: bool | None = None,
    guest: bool | None = None,
) -> list[dict]:
    with crawl_reader.connect(db_path) as conn:
        return crawl_reader.shares(
            conn, high_value=high_value, readable=readable, writable=writable, guest=guest
        )


@router.get("/{scan_id}/tree", summary="Lazy children of one path node")
def tree(
    target: str,
    share: str,
    parent_id: int | None = None,
    db_path: Path = Depends(require_crawl_db),
) -> list[dict]:
    with crawl_reader.connect(db_path) as conn:
        return crawl_reader.tree_children(
            conn, target=target, share=share, parent_id=parent_id
        )


@router.get("/{scan_id}/paths", summary="Flat, paginated path listing (+ annotation overlay)")
def paths(
    scan: Scan = Depends(get_scan),
    db_path: Path = Depends(require_crawl_db),
    db: Session = Depends(get_db),
    target: str | None = None,
    share: str | None = None,
    q: str | None = Query(None, description="substring match on the full path"),
    high_value: bool | None = None,
    downloaded_only: bool = False,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict:
    with crawl_reader.connect(db_path) as conn:
        res = crawl_reader.paths(
            conn,
            target=target,
            share=share,
            name_like=q,
            high_value=high_value,
            downloaded_only=downloaded_only,
            limit=limit,
            offset=offset,
        )
    ann = _annotation_map(db, scan.id)
    for item in res["items"]:
        a = ann.get(("path", str(item["id"]))) or (
            ann.get(("file", item["content_hash"])) if item.get("content_hash") else None
        )
        item["annotation"] = a
    return res


@router.get("/{scan_id}/stats", summary="File + secret statistics (types, sizes, per share, per rule)")
def stats(db_path: Path = Depends(require_crawl_db)) -> dict:
    from .. import sc

    with crawl_reader.connect(db_path) as conn:
        out = crawl_reader.file_stats(conn)
        out["secrets"] = crawl_reader.secret_stats(conn, classifier=sc.classify_secret)
    return out


@router.get("/{scan_id}/secrets", summary="Secrets with full paths (+ annotation overlay)")
def secrets(
    scan: Scan = Depends(get_scan),
    db_path: Path = Depends(require_crawl_db),
    db: Session = Depends(get_db),
    unique: bool = False,
) -> list[dict]:
    with crawl_reader.connect(db_path) as conn:
        rows = crawl_reader.secrets(conn, unique=unique)
    if unique:
        return rows
    ann = _annotation_map(db, scan.id)
    for r in rows:
        r["annotation"] = ann.get(("secret", r["secret"]))
    return rows


@router.post(
    "/{scan_id}/paths/{path_id}/fetch",
    summary="On-demand SMB download of a file the crawl did not fetch",
)
def fetch_file(path_id: int, body: FetchIn, scan: Scan = Depends(get_scan)) -> dict:
    """Connect to the share with the supplied credentials, download this one file,
    store it in the scan, update the `.crwl` (content hash + any new secrets) and
    refresh the search index. Returns the new ``content_hash``.
    """
    from ..ondemand import FetchError, PathNotFound, fetch_path

    if not (Path(scan.dir) / "output.crwl").is_file():
        raise HTTPException(status_code=409, detail="scan has no results")
    try:
        return fetch_path(
            Path(scan.dir),
            path_id,
            username=body.username,
            password=body.password,
            domain=body.domain,
            nthash=body.nthash,
            timeout=body.timeout,
            max_mib=body.max_mib,
        )
    except PathNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{scan_id}/files/{content_hash}", summary="Download a stored file (raw bytes)")
def file_raw(content_hash: str, scan: Scan = Depends(get_scan)) -> FileResponse:
    if not _HASH_RE.match(content_hash):
        raise HTTPException(status_code=400, detail="bad content hash")
    f = _content_dir(scan) / content_hash
    if not f.is_file():
        raise HTTPException(status_code=404, detail="file not stored")
    return FileResponse(f, filename=content_hash)


@router.get("/{scan_id}/files/{content_hash}/preview", response_class=PlainTextResponse, summary="Converted text preview of a stored file")
def file_preview(content_hash: str, scan: Scan = Depends(get_scan)) -> str:
    if not _HASH_RE.match(content_hash):
        raise HTTPException(status_code=400, detail="bad content hash")
    cdir = _content_dir(scan)
    txt = cdir / f"{content_hash}.txt"
    raw = cdir / content_hash
    if txt.is_file():
        return txt.read_text(encoding="utf-8", errors="replace")
    if raw.is_file():
        data = raw.read_bytes()
        if b"\x00" in data[:8192]:
            raise HTTPException(status_code=415, detail="binary file, no text preview")
        return data.decode("utf-8", errors="replace")
    raise HTTPException(status_code=404, detail="file not stored")


@router.get("/{scan_id}/search", summary="FTS5 full-text search over converted file text")
def search(
    scan: Scan = Depends(get_scan),
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    return search_query(Path(scan.dir), q, limit=limit, offset=offset)


@router.get("/{scan_id}/report", summary="smbcrawler report (html | json | yaml | csv)")
def report(
    scan: Scan = Depends(get_scan),
    db_path: Path = Depends(require_crawl_db),
    format: str = Query("json"),
    section: str = Query("summary"),
) -> Response:
    if format not in _REPORT_FORMATS:
        raise HTTPException(status_code=422, detail=f"format must be one of {_REPORT_FORMATS}")
    if section not in _REPORT_SECTIONS:
        raise HTTPException(status_code=422, detail=f"section must be one of {_REPORT_SECTIONS}")

    from smbcrawler.reporting import generate

    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=f".{format}") as fh:
        generate(str(db_path), format, fh, section=section)
        fh.seek(0)
        content = fh.read()

    media = {
        "html": "text/html",
        "json": "application/json",
        "yaml": "application/yaml",
        "csv": "text/tab-separated-values",
    }[format]
    ext = "tsv" if format == "csv" else format
    return Response(
        content,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{scan.name}-{section}.{ext}"'
        },
    )
