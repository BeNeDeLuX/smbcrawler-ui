"""Runs one smbcrawler crawl, in its own process.

Invoked by the RQ job as ``python -m app.worker.crawl_entry <scan_dir>``.

* Credentials arrive via the ``SMBUI_CRED_JSON`` env var (never argv).
* Crawl parameters are read from ``<scan_dir>/jobspec.json``.
* Progress is written to ``<scan_dir>/progress.json`` every few seconds.
* SIGTERM triggers a clean ``CrawlerApp.kill_threads()`` and exit 143.

Importing ``smbcrawler.app`` monkey-patches impacket globally -- fine here
because this process does nothing else.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path


def _write_json_atomic(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


def _write_progress(scan_dir: Path, app, phase: str) -> None:
    total = len(getattr(app, "targets", []) or [])
    done = getattr(app, "targets_finished", 0)
    counts: dict[str, int] = {}
    try:
        from app import crawl_reader

        with crawl_reader.connect(scan_dir / "output.crwl") as conn:
            counts = crawl_reader.counts(conn)
    except Exception:  # DB may not exist yet / be briefly locked
        pass
    _write_json_atomic(
        scan_dir / "progress.json",
        {
            "phase": phase,
            "targets_total": total,
            "targets_done": done,
            "percent": round(100.0 * done / total, 1) if total else 0.0,
            "counts": counts,
            "ts": time.time(),
        },
    )


def main(argv: list[str]) -> int:
    scan_dir = Path(argv[1]).resolve()
    spec = json.loads((scan_dir / "jobspec.json").read_text())
    cred = json.loads(os.environ.get("SMBUI_CRED_JSON", "{}"))

    from smbcrawler.app import CrawlerApp, Login
    from smbcrawler.log import init_logger
    from smbcrawler.profiles import collect_profiles

    init_logger(log_level="INFO")

    extra_files = []
    prof = scan_dir / "extra_profile.yml"
    if prof.is_file():
        extra_files.append(str(prof))
    profile_collection = collect_profiles(
        extra_files=extra_files, load_default=not spec.get("no_default", False)
    )

    login = Login(
        username=cred.get("username") or " ",
        domain=cred.get("domain") or ".",
        password=cred.get("password") or "",
        nthash=cred.get("nthash") or "",
        aeskey=cred.get("aeskey") or "",
        kdchost=cred.get("dc_ip") or None,
        use_kerberos=bool(cred.get("use_kerberos")),
    )

    opts = spec.get("options", {})
    hostfile = spec.get("hostfile")
    app = CrawlerApp(
        login=login,
        targets=spec.get("targets", []),
        crawl_file=str(scan_dir / "output.crwl"),
        threads=int(opts.get("threads", 1)),
        timeout=int(opts.get("timeout", 5)),
        depth=int(opts.get("depth", 1)),
        check_write_access=bool(opts.get("check_write_access", False)),
        crawl_printers_and_pipes=bool(opts.get("crawl_printers_and_pipes", False)),
        disable_autodownload=bool(opts.get("disable_autodownload", False)),
        max_file_size=int(opts.get("max_file_size_kib", 200)) * 1024,
        profile_collection=profile_collection,
        force=bool(opts.get("force", False)),
        inputfilename=hostfile,
        cmd=spec.get("cmd"),
    )
    # Disable the interactive stdin key-listener (no TTY here).
    app.input_thread = lambda: None  # type: ignore[method-assign]

    stop = threading.Event()

    def progress_loop() -> None:
        while not stop.wait(3):
            _write_progress(scan_dir, app, "running")

    def on_term(*_):  # SIGTERM -> same path as Ctrl-C inside CrawlerApp.run()
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, on_term)

    threading.Thread(target=progress_loop, daemon=True).start()
    _write_progress(scan_dir, app, "starting")

    rc = 0
    try:
        app.run()  # blocks until all targets processed / threads killed
    except KeyboardInterrupt:
        rc = 143
    finally:
        stop.set()
        _write_progress(scan_dir, app, "finished" if rc == 0 else "canceled")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
