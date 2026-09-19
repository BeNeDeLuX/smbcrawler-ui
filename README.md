# smbcrawler UI

A web UI + REST API around [smbcrawler](https://github.com/SySS-Research/smbcrawler):
create SMB share scans, watch them run, then browse / search / annotate the files
and secrets they find. Everything runs in Docker.

```
┌────────┐   ┌──────────┐   ┌────────────────────────────┐
│  db    │   │  redis   │   │  scandata  (named volume)  │
│ (PG)   │   │ (queue)  │   │  /data/scans/<id>/…        │
└───┬────┘   └────┬─────┘   └─────────┬──────────────────┘
    │             │                   │
┌───┴─────────────┴───────────────────┴───┐   ┌──────────────────────────┐
│  api   FastAPI + built React SPA        │   │  worker  RQ × N          │
│  :8000  /api/*  +  /                     │   │  runs `smbcrawler crawl` │
└─────────────────────────────────────────┘   │  as a subprocess/scan    │
                                              └──────────────────────────┘
```

* **api** – FastAPI. Serves the SPA at `/` and the REST API at `/api/*`. Session
  auth via a single shared password (`APP_PASSWORD`).
* **worker** – `SCAN_CONCURRENCY` RQ workers. Each scan runs as an isolated
  `smbcrawler` subprocess writing a `.crwl` SQLite DB + downloaded files under
  `/data/scans/<id>/`. A per-scan SQLite FTS5 index (`search.db`) is built when the
  crawl finishes.
* **db** – Postgres: scans/jobs, credentials (Fernet-encrypted, deleted after the
  run), annotations.
* smbcrawler itself is **unmodified**; it is `pip install`ed from the sibling
  `../smbcrawler` checkout during the image build (`hatch-vcs` needs its `.git`).

## Quick start

```bash
cd smbcrawler-ui
cp .env.example .env
# edit .env: set APP_PASSWORD, and generate SECRET_KEY + FERNET_KEY
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up -d --build
# open http://localhost:8000  and log in with APP_PASSWORD
```

The build context is the parent directory (it needs both `smbcrawler/` and
`smbcrawler-ui/`); `../.dockerignore` keeps the rest of the home dir out.

### Networking

SMB scans need outbound **tcp/445** from the `worker` container to your targets.
The default bridge network reaches anything routable from the Docker host. To scan
hosts on the Docker host's own L2 networks, uncomment `network_mode: host` on the
`worker` service in `docker-compose.yml`.

## End-to-end test with a throwaway Samba server

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --build
```

Adds a `samba` service (seeded from `testdata/share/`, with files that trip
smbcrawler's default secret rules). In the UI:

1. **New scan** → target `samba`, user `user1`, password `password1`, depth `-1`,
   check-write on. Watch progress + live log on the Overview tab.
2. **Shares / Files / Secrets** tabs populate. Preview `config/default.ini`,
   `gpo/groups.xml`; the Secrets tab lists `iloveyou`, the GPP `cpassword`, etc.
3. Mark a secret **false positive** → reload → it stays.
4. **Search** for `iloveyou` → snippet hit → opens the file.
5. **Export** → HTML report downloads as one self-contained file.
6. **Import**: from a shell,
   `docker compose exec -T worker sh -c 'cd /data/scans/<id> && tar -C output.crwl.d -cf - content' > content.tar`
   and `docker compose exec -T worker cat /data/scans/<id>/output.crwl > out.crwl`,
   delete the scan, then re-import both via *Import .crwl* (only the `content/`
   subtree of `<crawl>.d` is needed — the `tree/` symlink mirror is ignored).

## API

Interactive docs (auto-generated, OpenAPI 3): **Swagger UI at `/docs`**, ReDoc at
`/redoc`, raw schema at `/openapi.json`. The UI header has an **API** link.
`/docs` is same-origin, so running *Try it out* on `POST /api/auth/login` stores
the session cookie and authenticates every subsequent call.

### Endpoint sketch

| Method & path | Purpose |
|---|---|
| `POST /api/auth/login` `{password}` | set session cookie |
| `GET  /api/scans` · `POST /api/scans` | list / create+enqueue |
| `POST /api/scans/dry-run` | effective profiles + parsed targets, no crawl |
| `GET  /api/scans/{id}` · `/summary` · `/log` · `/events` (SSE) | status & progress |
| `POST /api/scans/{id}/cancel` · `DELETE /api/scans/{id}` | control |
| `GET  /api/scans/{id}/targets` · `/shares` · `/tree` · `/paths` | browse results |
| `GET  /api/scans/{id}/secrets` | secrets (+ annotation overlay) |
| `GET  /api/scans/{id}/files/{hash}` · `/files/{hash}/preview` | raw / converted text |
| `GET  /api/scans/{id}/search?q=` | FTS5 over converted file text |
| `GET  /api/scans/{id}/report?format=html\|json\|csv&section=…` | smbcrawler reports |
| `GET/PUT /api/scans/{id}/annotations` | review status + notes |
| `POST /api/imports` (multipart) | import an existing `.crwl` |
| `GET  /api/profiles/default` | built-in profile collection |

## Development

* Backend: `backend/` – `pip install -e '.[dev]'`, needs a `smbcrawler` install,
  a Postgres/SQLite URL, Redis. `uvicorn app.main:app --reload`.
* Frontend: `frontend/` – `npm install && npm run dev` (proxies `/api` to
  `:8000`). `npm run typecheck` for the full `tsc` pass.
* Tests: `docker compose run --rm api pytest` (uses a synthetic `.crwl`, no
  network).

### Notes

* No scan **resume** – smbcrawler refuses a non-empty `.crwl`; each scan is a
  fresh directory.
* The crawl subprocess logs one harmless `termios` traceback at start (its
  interactive key-listener has no TTY) – ignore it.
* Credentials transit Redis inside the job payload **Fernet-encrypted** and are
  deleted from Postgres once the crawl ends. Passwords are passed to the
  subprocess via env, never argv.
