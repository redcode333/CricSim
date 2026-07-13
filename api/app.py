from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from engine.db import init_db
from api.routes import auth, teams, match, tournament, draft, saves, interactive

app = FastAPI(title="Cricket Sim API", version="1.0")


@app.on_event("startup")
def _startup():
    init_db()


app.include_router(auth.router,        prefix="/api/auth")
app.include_router(teams.router,       prefix="/api/teams")
app.include_router(match.router,       prefix="/api/match")
app.include_router(interactive.router, prefix="/api/match/interactive")
app.include_router(tournament.router,  prefix="/api/tournament")
app.include_router(draft.router,       prefix="/api/draft")
app.include_router(saves.router,       prefix="/api/saves")

# Built frontend (frontend/dist, produced by `npm run build`) — served
# directly by FastAPI so a single Render service can host both the API and
# the app with no separate static-site deploy.
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")


@app.get("/")
def index():
    return FileResponse(str(_DIST / "index.html"))


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    """Serve a static file straight out of frontend/dist if one exists at that
    path (e.g. /logo.png, /favicon.svg — Vite copies public/ assets to the
    dist root, not under /assets). Otherwise fall back to index.html for
    client-side routes (e.g. /tournament, /match) so a hard refresh doesn't
    404 — React Router handles the rest."""
    if full_path.startswith("api/"):
        raise HTTPException(404)
    candidate = (_DIST / full_path).resolve()
    if candidate.is_relative_to(_DIST) and candidate.is_file():
        return FileResponse(str(candidate))
    return FileResponse(str(_DIST / "index.html"))
