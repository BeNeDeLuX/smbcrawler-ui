"""Worker entrypoint: run ``SCAN_CONCURRENCY`` RQ workers in parallel.

Each RQ worker processes one job (one crawl) at a time; N worker processes give
N concurrent scans. Run as ``python -m app.worker.run``.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import signal
import sys

from ..config import settings
from ..queue import QUEUE_NAME


def _work() -> None:
    # Fresh Redis connection per child process.
    from redis import Redis
    from rq import Queue, Worker

    conn = Redis.from_url(settings.redis_url)
    worker = Worker([Queue(QUEUE_NAME, connection=conn)], connection=conn)
    worker.work(with_scheduler=True)


def main() -> int:
    n = max(1, int(settings.scan_concurrency))
    mp.set_start_method("spawn", force=True)
    procs = [mp.Process(target=_work, name=f"rq-worker-{i}", daemon=False) for i in range(n)]
    for p in procs:
        p.start()
    print(f"[worker] started {n} RQ worker process(es) on queue '{QUEUE_NAME}'", flush=True)

    def _term(*_):
        for p in procs:
            if p.pid:
                os.kill(p.pid, signal.SIGTERM)

    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)

    exit_code = 0
    for p in procs:
        p.join()
        exit_code |= p.exitcode or 0
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
