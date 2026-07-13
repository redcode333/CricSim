import os
import urllib.parse
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from engine.auth import login, register, display_name, get_or_create_google_user

router = APIRouter()

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
FRONTEND_URL         = os.getenv("FRONTEND_URL", "http://localhost:5174")


class Creds(BaseModel):
    username: str
    password: str


@router.post("/login")
def do_login(body: Creds):
    ok, result = login(body.username, body.password)
    if not ok:
        raise HTTPException(400, result)
    return {"username": result, "display": display_name(result)}


@router.post("/register")
def do_register(body: Creds):
    ok, result = register(body.username, body.password)
    if not ok:
        raise HTTPException(400, result)
    return {"username": result, "display": display_name(result)}


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google")
def google_login():
    """Redirect browser to Google OAuth consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google OAuth not configured (set GOOGLE_CLIENT_ID env var)")
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "online",
        "prompt":        "select_account",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(code: str = "", error: str = ""):
    """Google redirects here with ?code=... after user consents."""
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_denied")
    if not GOOGLE_CLIENT_ID:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=not_configured")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  GOOGLE_REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
        )
        if token_res.status_code != 200:
            return RedirectResponse(f"{FRONTEND_URL}/login?error=token_exchange_failed")

        access_token = token_res.json().get("access_token")
        user_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_res.status_code != 200:
            return RedirectResponse(f"{FRONTEND_URL}/login?error=userinfo_failed")

    info     = user_res.json()
    email    = info.get("email", "")
    name     = info.get("name", email.split("@")[0])
    google_id = info.get("id", "")

    key = get_or_create_google_user(google_id, email, name)

    # Redirect to frontend with username in query param (frontend stores in localStorage)
    safe_name = urllib.parse.quote(display_name(key))
    return RedirectResponse(f"{FRONTEND_URL}/login?google_user={key}&display={safe_name}")
