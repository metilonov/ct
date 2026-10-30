import os, secrets, time, json
from pathlib import Path
from urllib.parse import urlencode
import httpx
from cryptography.fernet import Fernet

pending = {}


def token_path():
    return Path(os.getenv("DATA_DIR", "./data")) / "drive.enc"


def cipher():
    return Fernet(os.environ["TOKEN_ENCRYPTION_KEY"].encode())


def refresh_token():
    if os.getenv("GOOGLE_REFRESH_TOKEN"):
        return os.environ["GOOGLE_REFRESH_TOKEN"]
    p = token_path()
    return (
        json.loads(cipher().decrypt(p.read_bytes()))["refresh_token"]
        if p.exists()
        else None
    )


def begin():
    redirect = os.environ["GOOGLE_REDIRECT_URI"]
    if not redirect.startswith("https://"):
        raise ValueError("https_redirect_required")
    cipher()
    state = secrets.token_urlsafe(32)
    now = time.time()
    for k in list(pending):
        if pending[k] < now:
            del pending[k]
    pending[state] = now + 600
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/drive.file",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )


def finish(code, state):
    expires = pending.pop(state, 0)
    if expires < time.time():
        raise ValueError("invalid_oauth_state")
    r = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": os.environ["GOOGLE_REDIRECT_URI"],
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    r.raise_for_status()
    token = r.json().get("refresh_token")
    if not token:
        raise ValueError("refresh_token_missing")
    p = token_path()
    temp = p.with_suffix(".tmp")
    temp.write_bytes(cipher().encrypt(json.dumps({"refresh_token": token}).encode()))
    temp.chmod(0o600)
    temp.replace(p)
