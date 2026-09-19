"""On-demand retrieval of a single file that the crawl enumerated but did not
auto-download. Connects over SMB with caller-supplied credentials, stores the
bytes in the scan's content dir, updates the `.crwl` (content_hash + any new
secrets) and rebuilds the search index.
"""

from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


class FetchError(RuntimeError):
    pass


class PathNotFound(FetchError):
    pass


def _smb_download(
    host: str,
    port: int,
    share: str,
    rel_path: str,
    *,
    username: str,
    password: str,
    domain: str,
    nthash: str,
    timeout: int,
    max_bytes: int,
) -> bytes:
    from impacket.smbconnection import SMBConnection, SessionError

    try:
        conn = SMBConnection(host, host, sess_port=port, timeout=timeout)
    except Exception as exc:  # OSError, socket errors, negotiation failures
        raise FetchError(f"cannot connect to {host}:{port}: {exc}") from exc

    try:
        try:
            conn.login(username or "", password or "", domain or "", nthash=nthash or "")
        except SessionError as exc:
            raise FetchError(f"SMB login failed: {exc}") from exc

        buf = bytearray()
        too_big = False

        def _cb(data: bytes) -> None:
            nonlocal too_big
            if len(buf) >= max_bytes:
                too_big = True
                return
            buf.extend(data[: max_bytes - len(buf)])

        try:
            conn.getFile(share, rel_path, _cb)
        except SessionError as exc:
            raise FetchError(f"cannot read \\\\{host}\\{share}\\{rel_path}: {exc}") from exc

        if too_big:
            raise FetchError(
                f"file exceeds the {max_bytes // (1024 * 1024)} MiB limit for on-demand fetch"
            )
        return bytes(buf)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def fetch_path(
    scan_dir: Path,
    path_id: int,
    *,
    username: str = "",
    password: str = "",
    domain: str = "",
    nthash: str = "",
    timeout: int = 8,
    max_mib: int = 50,
) -> dict[str, Any]:
    crawl_db = scan_dir / "output.crwl"
    content_dir = scan_dir / "output.crwl.d" / "content"
    content_dir.mkdir(parents=True, exist_ok=True)

    # Resolve the path row -> target/share/relative path (read-only).
    from . import crawl_reader

    with crawl_reader.connect(crawl_db) as conn:
        row = crawl_reader.path_by_id(conn, path_id)
    if row is None:
        raise PathNotFound("path not found in this scan")
    if row["content_hash"]:
        return {"content_hash": row["content_hash"], "size": row["size"], "already": True}

    target = str(row["target"])
    host, _, port_s = target.partition(":")
    port = int(port_s) if port_s else 445
    share = str(row["share"])
    # crawl_reader's full_path is '\'-joined and already relative to the share
    # root -- exactly what impacket's getFile() expects.
    rel_path = str(row["path"])

    data = _smb_download(
        host,
        port,
        share,
        rel_path,
        username=username,
        password=password,
        domain=domain,
        nthash=nthash,
        timeout=timeout,
        max_bytes=max_mib * 1024 * 1024,
    )

    content_hash = hashlib.sha256(data).hexdigest()
    blob_path = content_dir / content_hash
    if not blob_path.exists():
        blob_path.write_bytes(data)

    # Convert + scan for secrets (best effort), mirroring smbcrawler.
    secrets_found = 0
    clean_text: str | None = None
    try:
        from smbcrawler.io import convert, find_secrets
        from . import sc

        clean_text = convert(str(blob_path))
        if clean_text and clean_text.encode(errors="replace") != data:
            (content_dir / f"{content_hash}.txt").write_text(clean_text, errors="replace")
        rules = sc._profile_collection().secrets
        found = find_secrets(clean_text or "", rules)
    except Exception:
        found = []

    # Update the .crwl (read-write) -- set content_hash + insert new secrets.
    wconn = sqlite3.connect(crawl_db)
    try:
        wconn.execute(
            "UPDATE path SET content_hash = ?, size = ? WHERE id = ?",
            (content_hash, len(data), path_id),
        )
        for s in found:
            if len(s.get("secret", "")) < 3:
                continue
            dup = wconn.execute(
                "SELECT 1 FROM secret WHERE content_hash = ? AND line = ? AND secret = ?",
                (content_hash, s["line"], s["secret"]),
            ).fetchone()
            if dup:
                continue
            wconn.execute(
                "INSERT INTO secret (content_hash, line, line_number, secret) VALUES (?,?,?,?)",
                (content_hash, s["line"], s["line_number"], s["secret"]),
            )
            secrets_found += 1
        wconn.commit()
    finally:
        wconn.close()

    # Refresh the FTS index so the new content is searchable.
    try:
        from .search import build as build_index

        build_index(scan_dir, crawl_db)
    except Exception:
        pass

    return {
        "content_hash": content_hash,
        "size": len(data),
        "secrets_found": secrets_found,
        "already": False,
    }
