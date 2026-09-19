"""Per-scan full-text search over the converted text of downloaded files.

Built as a standalone SQLite FTS5 database (`search.db`) that lives next to the
scan's `.crwl`, so the API can open it read-only without touching the crawl DB.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from . import crawl_reader

SEARCH_DB = "search.db"
_MAX_BYTES = 2 * 1024 * 1024  # skip absurdly large blobs


def _search_db_path(scan_dir: Path) -> Path:
    return scan_dir / SEARCH_DB


def _read_text(content_dir: Path, content_hash: str) -> str | None:
    txt = content_dir / f"{content_hash}.txt"
    raw = content_dir / content_hash
    for candidate in (txt, raw):
        if not candidate.is_file() or candidate.stat().st_size > _MAX_BYTES:
            continue
        try:
            data = candidate.read_bytes()
        except OSError:
            continue
        if b"\x00" in data[:8192] and candidate is raw:
            continue  # looks binary and we have no conversion
        return data.decode("utf-8", errors="replace")
    return None


def build(scan_dir: Path, crawl_db: Path) -> dict[str, int]:
    """(Re)build the search index. Returns {'files': n, 'indexed': m}."""
    content_dir = Path(str(crawl_db) + ".d") / "content"
    out = _search_db_path(scan_dir)
    if out.exists():
        out.unlink()

    con = sqlite3.connect(out)
    con.execute(
        "CREATE VIRTUAL TABLE docs USING fts5("
        "target, share, path, content_hash UNINDEXED, body, tokenize='unicode61')"
    )

    files = indexed = 0
    with crawl_reader.connect(crawl_db) as crawl:
        rows = crawl_reader.content_hash_paths(crawl)
    for r in rows:
        files += 1
        body = _read_text(content_dir, r["content_hash"])
        if body is None:
            continue
        con.execute(
            "INSERT INTO docs(target, share, path, content_hash, body) VALUES (?,?,?,?,?)",
            (r["target"], r["share"], r["path"], r["content_hash"], body),
        )
        indexed += 1
    con.commit()
    con.close()
    return {"files": files, "indexed": indexed}


def query(scan_dir: Path, q: str, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    db = _search_db_path(scan_dir)
    if not db.is_file():
        return {"total": 0, "items": [], "indexed": False}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        total = con.execute(
            "SELECT count(*) AS n FROM docs WHERE docs MATCH ?", (q,)
        ).fetchone()["n"]
        items = [
            dict(r)
            for r in con.execute(
                "SELECT target, share, path, content_hash, "
                "snippet(docs, 4, '<<', '>>', ' … ', 12) AS snippet "
                "FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ? OFFSET ?",
                (q, limit, offset),
            ).fetchall()
        ]
        return {"total": total, "items": items, "indexed": True}
    except sqlite3.OperationalError as exc:
        # malformed FTS query string
        return {"total": 0, "items": [], "indexed": True, "error": str(exc)}
    finally:
        con.close()
