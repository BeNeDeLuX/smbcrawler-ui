"""RQ job functions. Enqueued by the API, executed in the worker container."""

from __future__ import annotations

import datetime as dt
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from ..config import settings
from ..crypto import decrypt_json
from ..db import SessionLocal
from ..models import Scan, ScanStatus
from ..queue import cancel_requested, clear_cancel
from ..search import build as build_search_index

_POLL = 2.0


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _tail(path: Path, n: int = 4000) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return data[-n:].decode("utf-8", errors="replace")


def _redacted_cmd(targets: list[str], opts: dict, cred: dict) -> str:
    parts = ["smbcrawler", "-C", "output.crwl", "crawl"]
    if cred.get("username", " ").strip():
        parts += ["-u", cred["username"]]
    if cred.get("domain"):
        parts += ["-d", cred["domain"]]
    if cred.get("password"):
        parts += ["-p", "***"]
    if cred.get("nthash"):
        parts += ["-H", "***"]
    for flag, key in (("-t", "threads"), ("-D", "depth"), ("-T", "timeout")):
        if key in opts:
            parts += [flag, str(opts[key])]
    if opts.get("check_write_access"):
        parts.append("-w")
    if opts.get("disable_autodownload"):
        parts.append("-A")
    parts += list(targets)
    return " ".join(shlex.quote(p) for p in parts)


# --------------------------------------------------------------------------- #
def run_scan(scan_id: str) -> None:
    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if scan is None:
            return
        scan_dir = Path(scan.dir)
        scan_dir.mkdir(parents=True, exist_ok=True)

        cred = decrypt_json(scan.credential.blob) if scan.credential else {}
        targets = scan.params.get("targets", [])
        opts = scan.params.get("options", {})

        hostfile = None
        if scan.params.get("hostfile_text"):
            hf = scan_dir / "hosts.txt"
            hf.write_text(scan.params["hostfile_text"])
            hostfile = str(hf)
        if scan.params.get("extra_profile_yaml"):
            (scan_dir / "extra_profile.yml").write_text(scan.params["extra_profile_yaml"])

        cmd = _redacted_cmd(targets, opts, cred)
        (scan_dir / "jobspec.json").write_text(
            json.dumps(
                {
                    "targets": targets,
                    "hostfile": hostfile,
                    "options": opts,
                    "no_default": scan.params.get("no_default", False),
                    "cmd": cmd,
                }
            )
        )

        scan.status = ScanStatus.running
        scan.started_at = _utcnow()
        scan.params = {**scan.params, "cmd": cmd}
        db.commit()

        log_path = scan_dir / "scan.log"
        env = {**os.environ, "SMBUI_CRED_JSON": json.dumps(cred)}
        with log_path.open("wb") as logf:
            proc = subprocess.Popen(
                [sys.executable, "-m", "app.worker.crawl_entry", str(scan_dir)],
                stdin=subprocess.DEVNULL,
                stdout=logf,
                stderr=subprocess.STDOUT,
                env=env,
            )
            canceled = False
            while proc.poll() is None:
                if not canceled and cancel_requested(scan_id):
                    canceled = True
                    proc.terminate()
                _relay_progress(db, scan)
                time.sleep(_POLL)
            rc = proc.wait()

        if canceled and rc != 0:
            proc.wait()

        # Finalize
        scan = db.get(Scan, scan_id)
        _relay_progress(db, scan)
        if canceled:
            scan.status = ScanStatus.canceled
        elif rc == 0:
            scan.status = ScanStatus.done
        else:
            scan.status = ScanStatus.failed
            scan.error = _tail(log_path)
        scan.finished_at = _utcnow()

        try:
            stats = build_search_index(scan_dir, scan_dir / "output.crwl")
            scan.progress = {**(scan.progress or {}), "search": stats}
        except Exception as exc:  # index failure must not fail the scan
            scan.progress = {**(scan.progress or {}), "search_error": str(exc)}

        # Drop credentials at rest once the crawl is over.
        if scan.credential is not None:
            db.delete(scan.credential)
        db.commit()
    finally:
        clear_cancel(str(scan_id))
        db.close()


def _relay_progress(db, scan: Scan) -> None:
    p = Path(scan.dir) / "progress.json"
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return
    scan.progress = {**(scan.progress or {}), **data}
    db.commit()


# --------------------------------------------------------------------------- #
def index_scan(scan_id: str) -> None:
    """(Re)build the FTS index for an already-present .crwl (used after import)."""
    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if scan is None:
            return
        scan_dir = Path(scan.dir)
        stats = build_search_index(scan_dir, scan_dir / "output.crwl")
        progress = {**(scan.progress or {}), "search": stats}
        try:
            from .. import crawl_reader

            with crawl_reader.connect(scan_dir / "output.crwl") as conn:
                progress["counts"] = crawl_reader.counts(conn)
        except Exception:
            pass
        scan.progress = progress
        if scan.status == ScanStatus.queued:
            scan.status = ScanStatus.imported
        db.commit()
    finally:
        db.close()
