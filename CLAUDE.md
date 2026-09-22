# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A web UI + REST API around [smbcrawler](https://github.com/SySS-Research/smbcrawler)
(a CLI tool that crawls SMB shares for interesting files/secrets): create scans,
watch them run, then browse/search/annotate the results. smbcrawler itself is
**unmodified** — this repo only wraps it.

The sibling directory `../smbcrawler` (a separate checkout) only matters when
**building** the api/worker image from source — the Docker build context for it
is the **parent** directory so it can `pip install` smbcrawler (see
`Dockerfile`, `docker-compose.build.yml: build.context: ..`). `hatch-vcs` needs
`../smbcrawler/.git` present to compute smbcrawler's version. By default
`docker-compose.yml` doesn't build anything — it pulls `api`/`worker`/`proxy`
from Docker Hub (`benedelux/smbcrawler-ui[-proxy]`, published by
`.github/workflows/docker-publish.yml`); the `proxy` image is self-contained
and never needs the smbcrawler checkout either way.

## Commands

```bash
# Full stack, pulling published images (no sibling checkout, no build)
docker compose up -d
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d          # + throwaway samba, seeded from testdata/share/

# Same, but building from source (needs ../smbcrawler; add --build after editing)
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.build.yml -f docker-compose.test.yml up -d --build

# Backend tests (run inside the built/pulled image; no network needed, uses a synthetic .crwl)
docker compose run --rm --no-deps api pytest -q
docker compose run --rm --no-deps api pytest -q tests/test_results_api.py::test_stats   # single test

# Backend dev server outside Docker (needs Postgres/SQLite URL + Redis reachable)
cd backend && pip install -e '.[dev]' && uvicorn app.main:app --reload

# Frontend dev server (proxies /api -> :8000, see vite.config.ts)
cd frontend && npm install && npm run dev
npm run typecheck   # tsc --noEmit; `npm run build` (vite build) does NOT type-check
```

There is no lint/format command configured for either side yet.
`docker-publish.yml` gates every push: it builds each image locally first,
runs the backend pytest suite / a proxy smoke test against it, and only pushes
to Docker Hub if that passes — see its steps for the exact commands it runs.

## Architecture

Five containers. `api`/`worker` share one image (`Dockerfile`, multi-stage:
builds the SPA with node, then a Python 3.12 image with smbcrawler + this
backend installed; the built SPA lands in `backend/app/static/` and is served
by FastAPI at `/`). `proxy` is a separate, self-contained nginx image
(`proxy/Dockerfile`).

```
db (Postgres)        app metadata: Scan, Credential, Annotation      (app/models.py)
redis                RQ queue + per-scan cancel flags                (app/queue.py)
api                  FastAPI: serves SPA at "/", REST at "/api/*"                    :8000 (plain HTTP)
worker               N x RQ worker processes (app/worker/run.py)
proxy                nginx: TLS termination in front of api, self-signed by default  :8443 (HTTPS)
scandata (volume)    /data/scans/<scan-id>/{output.crwl, output.crwl.d/, scan.log,
                       progress.json, search.db}
certs (volume)       /certs/{active,self-signed,custom}.{crt,key} -- shared by api + proxy
```

### Scan lifecycle (the core flow to understand before changing anything here)

1. `POST /api/scans` (`routers/scans.py`) creates a `Scan` + encrypted `Credential`
   row in Postgres and enqueues `worker.jobs.run_scan` on RQ.
2. `run_scan` (`worker/jobs.py`) writes `jobspec.json`, decrypts the credential,
   and spawns `python -m app.worker.crawl_entry <scan_dir>` as a **subprocess**
   with credentials passed via the `SMBUI_CRED_JSON` env var (never argv, never
   logged). It polls the subprocess, relays `progress.json` into `Scan.progress`
   every ~2s, watches a Redis cancel flag (`queue.cancel_requested`) and
   `terminate()`s the subprocess on cancel.
3. `worker/crawl_entry.py` builds `smbcrawler.app.CrawlerApp` directly (not the
   CLI) against `<scan_dir>/output.crwl`, disables its interactive stdin
   key-listener (`app.input_thread = lambda: None`, there is no TTY), and runs
   it. **Why a subprocess and not in-process in the worker**: importing
   `smbcrawler.app` globally monkey-patches impacket, `CrawlerApp.run()` blocks,
   and `init_db()` hard-exits if the target file isn't empty — isolating each
   crawl in its own process makes cancellation (SIGTERM -> the same
   `KeyboardInterrupt` -> `kill_threads()` path `Ctrl-C` would take) and crash
   containment trivial.
4. On completion, `run_scan` builds the FTS5 search index (`app/search.py`) and
   **deletes the `Credential` row** — nothing about the plaintext credential
   outlives the run.
5. Everything read-facing (`routers/results.py`) opens `output.crwl` **read-only**
   through `app/crawl_reader.py`.

### Reading smbcrawler's `.crwl` (the gotcha that matters most here)

`output.crwl` is a plain SQLite file smbcrawler writes via peewee. Two things
that aren't obvious from the schema and will break any new query if missed:

- **Foreign keys store the target/share *name string*, not a numeric id**
  (e.g. `path.share_id = "public"`, `path.target_id = "10.0.0.1:445"`). Every
  join in `crawl_reader.py` is `... ON p.target_id = t.name`, never `= t.id`.
- **There is no `is_directory` column.** `Path` rows are a self-referential tree
  holding both directories and files; a row is treated as a leaf/file if it has
  no children (`crawl_reader._FULLPATH_CTE` + `NOT EXISTS (child)`), with a
  further heuristic in `file_stats()` to exclude empty directories (no content
  hash, size 0, no extension in the name).
- smbcrawler bakes analytical SQL **views** into every `.crwl` at creation time
  (`smbcrawler.queries.ALL_QUERIES`, e.g. `secrets_with_paths`, `summary`) —
  `crawl_reader.py` reuses those directly for secrets/summary rather than
  re-deriving them, but writes its own recursive CTE (`_FULLPATH_CTE`) for
  path listings because the views don't expose row ids.
- Secrets are linked to files only by `content_hash` (no FK) — one secret hash
  can map to several paths (same file downloaded from multiple shares/targets).
- The `Secret` table does **not** record which detection rule matched. Nothing
  in this codebase persists that either; `app/sc.classify_secret()` re-matches
  a secret's `line` against the live `smbcrawler.profiles.collect_profiles()`
  rule set (last-defined rule wins, same convention as smbcrawler's own
  `find_matching_profile`) whenever "secrets by rule" stats are requested. This
  only sees the built-in/XDG profile rules, not a scan's one-off
  `extra_profile_yaml`.

### On-demand fetch (`app/ondemand.py`)

`POST /api/scans/{id}/paths/{path_id}/fetch` downloads a file smbcrawler
enumerated but didn't auto-download (no profile match, `download: false`, or
size cap): connects over SMB with caller-supplied credentials (a scan's own
credentials are already gone by then), writes the bytes into
`output.crwl.d/content/<sha256>`, **updates `output.crwl` in place** (sets
`path.content_hash`, inserts any new `Secret` rows found via
`smbcrawler.io.convert`/`find_secrets`), and rebuilds the search index. This is
the one place outside the crawl subprocess that writes to a `.crwl`.

### TLS (`app/tls.py`, `proxy/`)

`proxy` (nginx) is the only container exposed for HTTPS. It never talks to
Postgres/Redis/smbcrawler; its only job is terminating TLS and reverse-proxying
to `api:8000` (`proxy/nginx.conf`, upstream resolved lazily via Docker's
embedded DNS at `127.0.0.11` so nginx still starts even if `api` isn't up yet).
Both it and `api` mount the same `certs` volume, and coordinate purely through
the filesystem — there's no cross-container RPC:

- `proxy/entrypoint.sh` generates `self-signed.{crt,key}` on first boot if
  missing, and copies them to `active.{crt,key}` if THAT'S missing (first boot
  only — never overwrites an existing active cert). It then runs
  `inotifywait -m` on the `certs` **directory** (not the files directly — they
  get replaced via atomic rename, which a direct-file watch can miss) and
  `nginx -s reload`s whenever `active.crt`/`active.key` change.
- `POST/DELETE /api/tls/certificate` (`app/routers/tls.py` -> `app/tls.py`) is
  the only backend-side writer: it validates an uploaded PEM cert+key pair
  (parses both, checks the public keys match, checks expiry, via
  `cryptography`), writes `custom.{crt,key}`, then atomically replaces
  `active.{crt,key}` — which is what nginx's watch picks up, live, no restart.
  Resetting just re-points `active.*` back at the preserved `self-signed.*`.
- `POST /api/auth/login` sets the session cookie `Secure` only when the
  request carries `X-Forwarded-Proto: https` (`auth.is_https_request`) — set
  by `proxy`, absent when hitting `api`'s own plain-HTTP `:8000` directly. That
  plain port stays published for local/dev use; prefer the proxy's `:8443`
  otherwise.
- Nothing about this needs Postgres — `get_active()`/`install_custom()` just
  read/write files, so it works identically whether or not the rest of the
  stack is healthy.

### Frontend

React + Vite + Mantine + TanStack Query, no Redux — server state lives in React
Query caches keyed `["scan", scanId, <resource>, ...filters]`. Auth is a
session cookie (`app/auth.py`, `AuthProvider` in `frontend/src/auth.tsx`); there
is no token to attach manually, just `credentials: "include"` (`frontend/src/api.ts`).
`pages/ScanDetail.tsx` owns the tab routing (`overview / targets / shares /
files / stats / secrets / search / review / log`) as nested react-router
routes under `/scans/:scanId/*`; each tab is a sibling file under
`pages/scan/`. `pages/Settings.tsx` is the one top-level (non-scan) page,
routed at `/settings`, currently just the TLS certificate UI. Live status
(Overview's progress bar/log, the scans list) polls
via React Query `refetchInterval`, not the SSE endpoint the backend also
exposes (`GET /api/scans/{id}/events`) — the log tab and scans list poll plain
GETs instead.

## Notes

- No scan **resume**: smbcrawler's `init_db()` refuses a non-empty `.crwl`, so
  every scan (including on-demand fetch retries) writes into a fresh
  `scans/<uuid>/` directory.
- Backend app models use SQLAlchemy's dialect-agnostic `Uuid`/`JSON` column
  types (not Postgres-specific `UUID`/`JSONB`) so the test suite can run
  against SQLite without a real Postgres.
- There is no Alembic migration in use despite it being a dependency —
  `app/dbinit.py` just does `Base.metadata.create_all()`, tolerating the race
  where `api` and `worker` both try it on first boot (retries past a duplicate
  ENUM-type error on Postgres).
