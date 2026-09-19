# smbcrawler-ui backend

FastAPI + RQ service that wraps [smbcrawler](../../smbcrawler) with a REST API:
create scans, drive them as isolated subprocesses, and browse / annotate the
results stored in each scan's `.crwl` SQLite database.

See the repository root `README.md` for the full picture and `docker compose` usage.
