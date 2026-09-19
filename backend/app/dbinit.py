"""Create database tables. Run once at container start: ``python -m app.dbinit``.

Kept deliberately simple (``create_all``); swap in Alembic when the schema starts
to evolve.
"""

from __future__ import annotations

import time

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from .db import Base, engine
from . import models  # noqa: F401  (register mappers)


def init_db(retries: int = 30, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except OperationalError:
            if attempt == retries:
                raise
            print(f"[dbinit] database not ready ({attempt}/{retries}), retrying…", flush=True)
            time.sleep(delay)

    # api and worker may both run this on first boot; a lost create_all race
    # (e.g. duplicate ENUM type) just means the winner already did the work.
    for attempt in range(3):
        try:
            Base.metadata.create_all(engine)
            break
        except (ProgrammingError, IntegrityError) as exc:
            print(f"[dbinit] create_all race ({attempt}): {exc}", flush=True)
            time.sleep(3)
    print("[dbinit] tables ready", flush=True)


if __name__ == "__main__":
    init_db()
