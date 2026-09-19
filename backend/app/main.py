from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import require_auth
from .config import settings
from .routers import annotations, auth, imports, profiles, results, scans

DESCRIPTION = """
REST API for the smbcrawler UI: create SMB share scans, drive them, and browse /
search / annotate the results.

### Authentication

All `/api/*` endpoints except `/api/auth/*` and `/api/health` require a session
cookie. Get one by calling **POST `/api/auth/login`** with the shared password
(`APP_PASSWORD`). This Swagger page is served from the same origin, so once you
run *Try it out* on the login call the cookie is stored by the browser and every
other *Try it out* call is authenticated automatically.

The raw schema is at [`/openapi.json`](/openapi.json); ReDoc is at [`/redoc`](/redoc).
"""

TAGS = [
    {"name": "auth", "description": "Login / logout (shared-password session cookie)."},
    {"name": "scans", "description": "Create, list, control and delete scans."},
    {"name": "results", "description": "Browse a scan's targets, shares, files, secrets, stats; full-text search; smbcrawler reports."},
    {"name": "annotations", "description": "Review status + notes on paths, files and secrets."},
    {"name": "imports", "description": "Import an existing `.crwl` database."},
    {"name": "profiles", "description": "The built-in smbcrawler profile collection."},
    {"name": "meta", "description": "Health check."},
]

app = FastAPI(
    title="smbcrawler UI API",
    version="0.1.0",
    description=DESCRIPTION,
    openapi_tags=TAGS,
    contact={"name": "smbcrawler UI"},
    license_info={"name": "MIT"},
)

# Dev convenience: the Vite dev server runs on :5173 and proxies /api, but allow
# direct cross-origin calls too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    return {"ok": True}


# Public
app.include_router(auth.router)

# Protected by the shared-password session cookie
_guard = [Depends(require_auth)]
app.include_router(scans.router, dependencies=_guard)
app.include_router(results.router, dependencies=_guard)
app.include_router(annotations.router, dependencies=_guard)
app.include_router(imports.router, dependencies=_guard)
app.include_router(profiles.router, dependencies=_guard)


# ---- Serve the built SPA (if present) ------------------------------------- #
_STATIC = Path(__file__).parent / "static"
if (_STATIC / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=_STATIC / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = _STATIC / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_STATIC / "index.html")
