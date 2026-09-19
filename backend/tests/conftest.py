"""Test fixtures.

Environment is configured at import time (before any ``app.*`` import) to point
at a throwaway directory + SQLite app DB. Each test builds a tiny but realistic
`.crwl` via smbcrawler's own ``init_db`` (no network, no impacket crawl), drops a
couple of content files next to it, registers it as an imported Scan, and gets a
logged-in TestClient back.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="smbui_tests_"))
os.environ["SECRET_KEY"] = "test-secret"
os.environ["APP_PASSWORD"] = "test-pass"
os.environ["FERNET_KEY"] = ""
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["DATA_DIR"] = str(_TMP / "data")
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_TMP / 'app.db'}"
(_TMP / "data" / "scans").mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    from app.db import Base, engine
    from app import models  # noqa: F401

    Base.metadata.create_all(engine)
    yield


def _write_content(content_dir: Path, text: str) -> str:
    h = hashlib.sha256(text.encode()).hexdigest()
    (content_dir / h).write_text(text)
    (content_dir / f"{h}.txt").write_text(text)
    return h


@pytest.fixture()
def sample_scan():
    import uuid

    from smbcrawler.sql import init_db

    from app.db import SessionLocal
    from app.models import Scan, ScanSource, ScanStatus
    from app.search import build as build_index

    sid = uuid.uuid4()
    sdir = Path(os.environ["DATA_DIR"]) / "scans" / str(sid)
    content_dir = sdir / "output.crwl.d" / "content"
    content_dir.mkdir(parents=True)
    crawl_file = sdir / "output.crwl"

    db = init_db(str(crawl_file), cmd="smbcrawler -C output.crwl crawl -u user1 -p *** samba")
    M = db.models
    M["Target"].create(name="samba:445", port_open=True,
                       listable_authenticated=True, listable_unauthenticated=False)
    M["Share"].create(target="samba:445", name="public", remark="", high_value=False,
                      auth_access=True, guest_access=False, write_access=False,
                      read_level=3, maxed_out=False)
    ini = "[database]\nserver=db01\npassword=iloveyou\n"
    h = _write_content(content_dir, ini)
    d1 = M["Path"].create(name="config", parent=None, share="public", target="samba:445",
                          size=0, content_hash=None, high_value=False)
    M["Path"].create(name="default.ini", parent=d1, share="public", target="samba:445",
                     size=len(ini), content_hash=h, high_value=True)
    M["Path"].create(name="hello.txt", parent=None, share="public", target="samba:445",
                     size=11, content_hash=_write_content(content_dir, "Hello world"),
                     high_value=False)
    # enumerated but NOT downloaded (no content hash) -- for the on-demand fetch path
    M["Path"].create(name="notes.txt", parent=None, share="public", target="samba:445",
                     size=999, content_hash=None, high_value=False)
    M["Secret"].create(content_hash=h, line="password=iloveyou", line_number=3, secret="iloveyou")

    with SessionLocal() as session:
        session.add(Scan(id=sid, name="sample", source=ScanSource.import_,
                         status=ScanStatus.imported, dir=str(sdir), params={}, progress={}))
        session.commit()

    build_index(sdir, crawl_file)
    return {"id": str(sid), "dir": sdir, "crawl_file": crawl_file, "content_hash": h}


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    assert c.post("/api/auth/login", json={"password": "test-pass"}).status_code == 200
    return c
