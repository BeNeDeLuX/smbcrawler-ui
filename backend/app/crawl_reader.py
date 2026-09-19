"""Read-only access to a single scan's smbcrawler `.crwl` SQLite database.

The `.crwl` file is a plain SQLite DB produced by smbcrawler. Foreign keys are
stored as *name strings* (not ids), so every join is on `name`. smbcrawler bakes
a set of analytical VIEWs into the file (see ``smbcrawler.queries.ALL_QUERIES``);
we reuse `summary` / `secrets_*` directly and use our own recursive CTE for the
path tree so we can also surface each row's `id` and `content_hash`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_SHARE_COLS = (
    "name, remark, high_value, auth_access, guest_access, "
    "write_access, read_level, maxed_out, target_id AS target"
)

# Recursive CTE: full '\'-joined path for every Path row, carrying id + content_hash.
_FULLPATH_CTE = """
WITH RECURSIVE fp(id, parent_id, target, share, size, high_value, content_hash, full_path) AS (
    SELECT p.id, p.parent_id, p.target_id, p.share_id, p.size, p.high_value, p.content_hash, p.name
    FROM path p
    WHERE p.parent_id IS NULL
    UNION ALL
    SELECT p.id, p.parent_id, p.target_id, p.share_id, p.size, p.high_value, p.content_hash,
           fp.full_path || '\\' || p.name
    FROM path p JOIN fp ON p.parent_id = fp.id
)
"""


class CrawlNotFound(FileNotFoundError):
    pass


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    p = Path(db_path)
    if not p.is_file():
        raise CrawlNotFound(str(p))
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #
def config(conn: sqlite3.Connection) -> dict[str, Any] | None:
    rows = _rows(conn, "SELECT smbcrawler_version, created, cmd FROM config LIMIT 1")
    return rows[0] if rows else None


def summary(conn: sqlite3.Connection) -> dict[str, int]:
    return {r["key"]: r["value"] for r in _rows(conn, "SELECT key, value FROM summary")}


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    out: dict[str, int] = {}
    for name in ("target", "share", "path", "secret"):
        out[name] = _rows(conn, f"SELECT count(*) AS n FROM {name}")[0]["n"]
    out["downloaded"] = _rows(
        conn, "SELECT count(*) AS n FROM path WHERE content_hash IS NOT NULL"
    )[0]["n"]
    return out


# --------------------------------------------------------------------------- #
# Targets / shares
# --------------------------------------------------------------------------- #
def targets(
    conn: sqlite3.Connection, *, no_access: bool | None = None
) -> list[dict[str, Any]]:
    """All targets, with a per-target share count.

    ``no_access=True`` restricts to SMB servers that were *reachable* (port 445
    open) but where neither authenticated nor guest share enumeration worked --
    i.e. the ones worth retrying with different credentials.
    """
    where = ""
    if no_access:
        where = (
            " WHERE t.port_open = 1 "
            "AND COALESCE(t.listable_authenticated, 0) = 0 "
            "AND COALESCE(t.listable_unauthenticated, 0) = 0"
        )
    return _rows(
        conn,
        "SELECT t.name, t.netbios_name, t.port_open, t.listable_authenticated, "
        "t.listable_unauthenticated, "
        "(SELECT count(*) FROM share s WHERE s.target_id = t.name) AS share_count, "
        "(SELECT min(l.timestamp) FROM logitem l WHERE l.target_id = t.name) AS first_seen, "
        "(SELECT max(l.timestamp) FROM logitem l WHERE l.target_id = t.name) AS last_activity "
        f"FROM target t{where} ORDER BY t.name",
    )


def shares(
    conn: sqlite3.Connection,
    *,
    high_value: bool | None = None,
    readable: bool | None = None,
    writable: bool | None = None,
    guest: bool | None = None,
) -> list[dict[str, Any]]:
    where = []
    if high_value:
        where.append("high_value = 1")
    if readable:
        where.append("(read_level > 0 OR (read_level = 0 AND maxed_out = 1))")
    if writable:
        where.append("write_access = 1")
    if guest:
        where.append("guest_access = 1")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    return _rows(conn, f"SELECT {_SHARE_COLS} FROM share{clause} ORDER BY target_id, name")


# --------------------------------------------------------------------------- #
# Paths -- flat listing
# --------------------------------------------------------------------------- #
def paths(
    conn: sqlite3.Connection,
    *,
    target: str | None = None,
    share: str | None = None,
    name_like: str | None = None,
    high_value: bool | None = None,
    downloaded_only: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    if target:
        where.append("target = ?")
        params.append(target)
    if share:
        where.append("share = ?")
        params.append(share)
    if name_like:
        where.append("full_path LIKE ?")
        params.append(f"%{name_like}%")
    if high_value:
        where.append("high_value = 1")
    if downloaded_only:
        where.append("content_hash IS NOT NULL")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(
        f"{_FULLPATH_CTE} SELECT count(*) AS n FROM fp{clause}", tuple(params)
    ).fetchone()["n"]
    items = _rows(
        conn,
        f"{_FULLPATH_CTE} SELECT id, target, share, full_path AS path, size, "
        f"high_value, content_hash FROM fp{clause} "
        "ORDER BY target, share, full_path LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    return {"total": total, "items": items, "limit": limit, "offset": offset}


# --------------------------------------------------------------------------- #
# Tree -- lazy children of one node
# --------------------------------------------------------------------------- #
def tree_children(
    conn: sqlite3.Connection,
    *,
    target: str,
    share: str,
    parent_id: int | None,
) -> list[dict[str, Any]]:
    parent_clause = "p.parent_id IS NULL" if parent_id is None else "p.parent_id = ?"
    extra: tuple = () if parent_id is None else (parent_id,)
    return _rows(
        conn,
        f"""
        SELECT p.id, p.name, p.size, p.content_hash, p.high_value,
               (SELECT count(*) FROM path c WHERE c.parent_id = p.id) AS child_count
        FROM path p
        WHERE p.target_id = ? AND p.share_id = ? AND {parent_clause}
        ORDER BY (child_count = 0), p.name
        """,
        (target, share, *extra),
    )


def path_by_id(conn: sqlite3.Connection, path_id: int) -> dict[str, Any] | None:
    rows = _rows(
        conn,
        f"{_FULLPATH_CTE} SELECT id, target, share, full_path AS path, size, "
        "high_value, content_hash FROM fp WHERE id = ?",
        (path_id,),
    )
    return rows[0] if rows else None


# --------------------------------------------------------------------------- #
# Secrets
# --------------------------------------------------------------------------- #
def secrets(conn: sqlite3.Connection, *, unique: bool = False) -> list[dict[str, Any]]:
    if unique:
        return _rows(conn, "SELECT secret FROM secrets_unique")
    return _rows(
        conn,
        "SELECT secret, line, line_number, target_name AS target, "
        "share_name AS share, path, content_hash FROM secrets_with_paths",
    )


_SIZE_BUCKETS = [
    (1024, "≤ 1 KiB"),
    (10 * 1024, "1–10 KiB"),
    (100 * 1024, "10–100 KiB"),
    (1024 * 1024, "100 KiB–1 MiB"),
    (10 * 1024 * 1024, "1–10 MiB"),
    (100 * 1024 * 1024, "10–100 MiB"),
    (1024 * 1024 * 1024, "100 MiB–1 GiB"),
]


def _ext_of(name: str) -> str:
    base = name.rsplit("\\", 1)[-1]
    if "." not in base[1:]:
        return "(none)"
    ext = base.rsplit(".", 1)[-1].lower()
    return ext if (0 < len(ext) <= 12 and ext.isalnum()) else "(other)"


def file_stats(conn: sqlite3.Connection, *, top: int = 20) -> dict[str, Any]:
    """Aggregate statistics over the *files* found (leaf Path rows).

    A leaf that has no content hash, zero size and no extension is treated as an
    empty directory and excluded.
    """
    rows = _rows(
        conn,
        f"{_FULLPATH_CTE} "
        "SELECT fp.target, fp.share, fp.full_path, fp.size, fp.high_value, fp.content_hash "
        "FROM fp WHERE NOT EXISTS (SELECT 1 FROM path c WHERE c.parent_id = fp.id)",
    )

    by_ext: dict[str, dict[str, int]] = {}
    by_share: dict[tuple[str, str], dict[str, int]] = {}
    by_target: dict[str, dict[str, int]] = {}
    buckets = {label: 0 for _, label in _SIZE_BUCKETS}
    buckets["> 1 GiB"] = 0
    totals = {"files": 0, "size": 0, "downloaded": 0, "high_value": 0, "empty_dirs": 0}

    for r in rows:
        name = r["full_path"].rsplit("\\", 1)[-1]
        size = r["size"] or 0
        if not r["content_hash"] and size == 0 and "." not in name[1:]:
            totals["empty_dirs"] += 1
            continue

        totals["files"] += 1
        totals["size"] += size
        if r["content_hash"]:
            totals["downloaded"] += 1
        if r["high_value"]:
            totals["high_value"] += 1

        e = by_ext.setdefault(_ext_of(name), {"count": 0, "size": 0})
        e["count"] += 1
        e["size"] += size

        s = by_share.setdefault((r["target"], r["share"]), {"count": 0, "size": 0})
        s["count"] += 1
        s["size"] += size

        t = by_target.setdefault(r["target"], {"count": 0, "size": 0})
        t["count"] += 1
        t["size"] += size

        for limit, label in _SIZE_BUCKETS:
            if size <= limit:
                buckets[label] += 1
                break
        else:
            buckets["> 1 GiB"] += 1

    largest = sorted(
        (
            {
                "target": r["target"],
                "share": r["share"],
                "path": r["full_path"],
                "size": r["size"] or 0,
                "content_hash": r["content_hash"],
            }
            for r in rows
        ),
        key=lambda x: x["size"],
        reverse=True,
    )[:top]

    return {
        "totals": totals,
        "by_extension": sorted(
            ({"ext": k, **v} for k, v in by_ext.items()),
            key=lambda x: x["count"],
            reverse=True,
        ),
        "by_share": sorted(
            ({"target": k[0], "share": k[1], **v} for k, v in by_share.items()),
            key=lambda x: x["count"],
            reverse=True,
        ),
        "by_target": sorted(
            ({"target": k, **v} for k, v in by_target.items()),
            key=lambda x: x["count"],
            reverse=True,
        ),
        "size_buckets": [
            {"label": label, "count": buckets[label]}
            for _, label in _SIZE_BUCKETS
        ]
        + [{"label": "> 1 GiB", "count": buckets["> 1 GiB"]}],
        "largest": largest,
    }


def secret_stats(
    conn: sqlite3.Connection,
    *,
    classifier: "Callable[[str], tuple[str, str]] | None" = None,
) -> dict[str, Any]:
    """Secrets aggregated per share and per detection rule.

    ``classifier(line) -> (rule_label, comment)`` is injected by the caller so
    this module stays free of the smbcrawler dependency.
    """
    rows = _rows(
        conn,
        "SELECT secret, line, target_name AS target, share_name AS share "
        "FROM secrets_with_paths",
    )
    by_share: dict[tuple[str, str], int] = {}
    by_rule: dict[str, dict[str, Any]] = {}
    unique: set[str] = set()

    for r in rows:
        unique.add(r["secret"])
        key = (r["target"], r["share"])
        by_share[key] = by_share.get(key, 0) + 1
        label, comment = classifier(r["line"]) if classifier else ("(all)", "")
        e = by_rule.setdefault(label, {"count": 0, "comment": comment})
        e["count"] += 1

    return {
        "total": len(rows),
        "unique": len(unique),
        "by_share": sorted(
            ({"target": t, "share": s, "count": c} for (t, s), c in by_share.items()),
            key=lambda x: x["count"],
            reverse=True,
        ),
        "by_rule": sorted(
            ({"rule": k, **v} for k, v in by_rule.items()),
            key=lambda x: x["count"],
            reverse=True,
        ),
    }


def content_hash_paths(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every downloaded file with its full path -- used to build the search index."""
    return _rows(
        conn,
        f"{_FULLPATH_CTE} SELECT target, share, full_path AS path, content_hash "
        "FROM fp WHERE content_hash IS NOT NULL",
    )
