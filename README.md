# smbcrawler UI

[![Docker Hub](https://img.shields.io/docker/v/benedelux/smbcrawler-ui?sort=semver&label=Docker%20Hub)](https://hub.docker.com/r/benedelux/smbcrawler-ui)
[![Image size](https://img.shields.io/docker/image-size/benedelux/smbcrawler-ui/latest)](https://hub.docker.com/r/benedelux/smbcrawler-ui)

A web UI + REST API around [smbcrawler](https://github.com/SySS-Research/smbcrawler):
create SMB share scans, watch them run, then browse / search / annotate the files
and secrets they find. Everything runs in Docker.

**Features:** live scan progress + full log · target reachability / share-listing
outcome (incl. "reachable but no login worked") · share permissions · file tree
with text preview · **on-demand SMB download** of files smbcrawler didn't
auto-fetch · full-text search over converted file content · charts on file
types/sizes/shares and secrets per share/rule · review workflow (false-positive
/ important / notes) · HTML/JSON/CSV export via smbcrawler's own reports ·
import of externally-produced `.crwl` files · interactive API docs at `/docs`.

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

## Installation from Docker Hub

The published image ([`benedelux/smbcrawler-ui`](https://hub.docker.com/r/benedelux/smbcrawler-ui))
is self-contained — it already has smbcrawler installed and the SPA built in,
so you don't need this repo's source or a sibling `smbcrawler` checkout to run
it. You only need `docker-compose.yml` and `.env.example`, which you can pull
down on their own instead of cloning the whole repo:

```bash
mkdir smbcrawler-ui && cd smbcrawler-ui
curl -fsSLO https://raw.githubusercontent.com/BeNeDeLuX/smbcrawler-ui/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/BeNeDeLuX/smbcrawler-ui/main/.env.example
cp .env.example .env
# edit .env: set APP_PASSWORD, and generate SECRET_KEY + FERNET_KEY
#   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
#   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up -d       # pulls db, redis and benedelux/smbcrawler-ui from Docker Hub
# open http://localhost:8000  and log in with APP_PASSWORD
```

Pin a specific version instead of always tracking `latest` by setting
`SMBCRAWLER_UI_IMAGE=benedelux/smbcrawler-ui:1.0.0` in `.env` (see the
[Releases](https://github.com/BeNeDeLuX/smbcrawler-ui/releases) /
[tags on Docker Hub](https://hub.docker.com/r/benedelux/smbcrawler-ui/tags)
for available versions).

Cloning the full repo works the same way — `git clone` it, `cd smbcrawler-ui`,
then the same `cp .env.example .env` + `docker compose up -d` — and additionally
gets you `docker-compose.test.yml`/`testdata/` for the end-to-end demo below.

### Building locally instead

To run against your own smbcrawler/backend/frontend changes, build the image
from source with the `docker-compose.build.yml` overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml build
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d
```

This needs a sibling `../smbcrawler` checkout — the build context is the
**parent** directory (it needs both `smbcrawler/` and `smbcrawler-ui/`);
`../.dockerignore` keeps the rest of the home dir out.

### Networking

SMB scans need outbound **tcp/445** from the `worker` container to your targets.
The default bridge network reaches anything routable from the Docker host. To scan
hosts on the Docker host's own L2 networks, uncomment `network_mode: host` on the
`worker` service in `docker-compose.yml`.

## End-to-end test with a throwaway Samba server

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml up -d
# testing local changes instead: add -f docker-compose.build.yml and --build
```

Adds a `samba` service (seeded from `testdata/share/`, with files that trip
smbcrawler's default secret rules). In the UI:

1. **New scan** → target `samba`, user `user1`, password `password1`, depth `-1`,
   check-write on. Watch progress + live log on the **Overview** tab (full log
   also under the **Log** tab).
2. **Targets** tab: `samba:445` shows port open + listable; tick "only reachable
   servers where share listing failed" to see hosts worth retrying with other
   creds. **Shares / Files / Secrets** tabs populate. Preview
   `config/default.ini`; the Secrets tab lists `iloveyou`, `secretpassword`, etc.
3. **Files** tab → untick "downloaded only" → pick `gpo/groups.xml` (enumerated
   but not auto-downloaded) → **Fetch from SMB** with the same creds → it now
   previews and its GPP `cpassword` shows up under Secrets.
4. **Stats** tab: file types / sizes / files per share, secrets per share and
   per detection rule, as charts.
5. Mark a secret **false positive** on the Secrets tab → reload → it stays
   (see it listed under **Review**).
6. **Search** for `iloveyou` → snippet hit → opens the file.
7. **Export** → HTML report downloads as one self-contained file.
8. **Import**: from a shell,
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
| `GET  /api/scans/{id}/targets?no_access=` · `/shares` · `/tree` · `/paths` | browse results |
| `GET  /api/scans/{id}/secrets` | secrets (+ annotation overlay) |
| `GET  /api/scans/{id}/stats` | file/secret stats: types, sizes, per share, per rule |
| `GET  /api/scans/{id}/files/{hash}` · `/files/{hash}/preview` | raw / converted text |
| `POST /api/scans/{id}/paths/{path_id}/fetch` | on-demand SMB download of a not-yet-fetched file |
| `GET  /api/scans/{id}/search?q=` | FTS5 over converted file text |
| `GET  /api/scans/{id}/report?format=html\|json\|csv&section=…` | smbcrawler reports |
| `GET/PUT /api/scans/{id}/annotations` | review status + notes |
| `POST /api/imports` (multipart) | import an existing `.crwl` |
| `GET  /api/profiles/default` | built-in profile collection |

## CI/CD

`.github/workflows/docker-publish.yml` builds this exact image (checking out
`SySS-Research/smbcrawler` as the sibling directory the `Dockerfile` expects)
and pushes it to Docker Hub on every push to `main` and on `v*.*.*` tags, or
manually via *Run workflow* (optionally pinning a different smbcrawler ref).

One-time setup — add these as **repo secrets** (Settings → Secrets and
variables → Actions):

| Secret | Value |
|---|---|
| `DOCKERHUB_USERNAME` | your Docker Hub username |
| `DOCKERHUB_TOKEN` | a Docker Hub **access token** (Account Settings → Security → *New Access Token*), not your password |

Resulting tags on `<dockerhub-user>/smbcrawler-ui`: `latest` + branch name on
every push to `main`, `sha-<short-sha>` always, and semver tags (`1.2.0`,
`1.2`) when you push a `v1.2.0`-style git tag. `docker-compose.yml` already
pulls `latest` by default (see Quick start); point it at a fork's image or a
pinned tag via the `SMBCRAWLER_UI_IMAGE` variable in `.env`.

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
  subprocess via env, never argv. Because of this, an on-demand file fetch
  (`.../paths/{id}/fetch`) asks for credentials again.
* "Secrets by rule" is computed on the fly by re-matching each secret's source
  line against the live default profile — smbcrawler doesn't persist which
  rule matched. A scan's own `extra_profile_yaml` rules aren't considered here.

See [`CLAUDE.md`](CLAUDE.md) for the architecture notes (scan lifecycle, the
`.crwl` schema gotchas, frontend structure) aimed at anyone — human or
Claude Code — extending this repo.
