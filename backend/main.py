import hmac
import os, sqlite3, secrets, time, base64, asyncio, threading, json, hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Header, Request, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from .scheduler import Engine, safe_path, UploadDeferred
from .drive import Drive
from .url_import import fetch_torrent

ROOT = Path(os.getenv("DATA_DIR", "./data"))
ROOT.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect(ROOT / "client.db", check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS metadata(id TEXT PRIMARY KEY, torrent BLOB, description TEXT);
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,name TEXT,state TEXT,total_bytes INTEGER,progress REAL DEFAULT 0,speed INTEGER DEFAULT 0,error TEXT,torrent BLOB,created REAL);
CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,task_id TEXT,file_index INTEGER,path TEXT,size INTEGER,state TEXT,drive_id TEXT);
""")
scheduler_db = sqlite3.connect(ROOT / "client.db", check_same_thread=False)
scheduler_db.row_factory = sqlite3.Row
if (ROOT / "drive-folder.txt").exists():
    os.environ["GOOGLE_DRIVE_FOLDER_ID"] = (
        (ROOT / "drive-folder.txt").read_text().strip()
    )
drive = Drive()
engine = Engine(ROOT / "workspace", scheduler_db, drive)
lock = threading.RLock()
metadata_slot = threading.Semaphore(1)
stopping = False


# Admin-only deployment, one owner shared by Android and allowlisted Telegram user.
def auth(authorization: str = Header(default="")):
    token = os.getenv("ADMIN_API_TOKEN", "")
    if len(token) < 32:
        raise HTTPException(503, "admin_token_not_configured")
    if not secrets.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, "unauthorized")
    return "admin"


def task_error_code(error):
    import httpx, errno

    if isinstance(error, httpx.HTTPStatusError):
        return "drive_http_" + str(error.response.status_code)
    if isinstance(error, httpx.RequestError):
        return "drive_network_error"
    if isinstance(error, OSError):
        return (
            "workspace_disk_full"
            if error.errno == errno.ENOSPC
            else "local_storage_error"
        )
    safe = {
        "drive_verification_failed",
        "size_mismatch",
        "disk_flush_timeout",
        "handle_removal_timeout",
        "disk_safety_reserve",
        "workspace_capacity_changed",
        "batch_manifest_has_no_files",
        "invalid_upload_offset",
    }
    return (
        str(error)
        if isinstance(error, RuntimeError) and str(error) in safe
        else "torrent_engine_error"
    )


async def loop():
    while True:
        try:
            await asyncio.to_thread(tick)
        except UploadDeferred:
            pass
        except Exception as e:
            with lock:
                if engine.batch:
                    db.execute(
                        "update tasks set error=?,speed=0,state=case when state in ('paused','cancel_requested') then state else 'error' end where id=?",
                        (task_error_code(e), engine.batch["id"]),
                    )
                    db.commit()
        await asyncio.sleep(2)


def tick():
    engine.tick()


@asynccontextmanager
async def lifespan(app):
    job = asyncio.create_task(loop())
    yield
    job.cancel()


class TrackedFileResponse(FileResponse):
    async def __call__(self, scope, receive, send):
        # Pin the opened Linux inode: cleanup may unlink the original pathname.
        with engine.read_payload(self.path) as source:
            self.path = f"/proc/self/fd/{source.fileno()}"
            scope = {
                **scope,
                "extensions": {
                    k: v
                    for k, v in scope.get("extensions", {}).items()
                    if k != "http.response.pathsend"
                },
            }
            await super().__call__(scope, receive, send)


app = FastAPI(title="Cloud Torrent Client", version="0.1.0", lifespan=lifespan)
requests = {}
MAX_METADATA_CACHE_BYTES = 64 * 1024 * 1024


def reserve_control_write(size):
    import shutil
    from .scheduler import SAFETY_BYTES

    if shutil.disk_usage(ROOT).free < SAFETY_BYTES + size * 2:
        raise HTTPException(507, "insufficient_control_storage")


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    try:
        declared = int(request.headers.get("content-length", "0"))
    except ValueError:
        return JSONResponse({"error": {"code": "invalid_content_length"}}, 400)
    if declared > 8 * 1024 * 1024:
        return JSONResponse({"error": {"code": "request_too_large"}}, 413)
    auth_header = request.headers.get("authorization", "")
    configured = os.getenv("ADMIN_API_TOKEN", "")
    valid = len(configured) >= 32 and secrets.compare_digest(
        auth_header.encode(), ("Bearer " + configured).encode()
    )
    key = (
        hashlib.sha256(auth_header.encode()).hexdigest()
        if valid
        else "unauthorized:" + str(request.client.host if request.client else "unknown")
    )
    now = time.monotonic()
    bucket = [t for t in requests.get(key, []) if t > now - 60]
    if len(bucket) >= 120:
        return JSONResponse(
            {"error": {"code": "rate_limited"}}, 429, headers={"Retry-After": "60"}
        )
    requests[key] = bucket + [now]
    if len(requests) > 1000:
        requests.clear()
    if request.method in ("POST", "PUT", "PATCH"):
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 8 * 1024 * 1024:
                return JSONResponse({"error": {"code": "request_too_large"}}, 413)
            body.extend(chunk)
        request._body = bytes(body)
    return await call_next(request)


@app.exception_handler(HTTPException)
async def error(request, e):
    return JSONResponse({"error": {"code": str(e.detail)}}, status_code=e.status_code)


@app.get("/health")
def health():
    return {"status": "ok", "backend": "BotHost", "version": "0.1.0"}


@app.get("/server/status", dependencies=[Depends(auth)])
def status():
    return {
        "connected": True,
        "backend": "BotHost",
        "drive_connected": drive.connected(),
        "large_single_file_streaming": False,
        "scheduler_parallelism": 1,
    }


@app.get("/server/storage", dependencies=[Depends(auth)])
def storage():
    with lock:
        return engine.storage()


class MetadataInput(BaseModel):
    source: str | None = Field(default=None, max_length=8192)
    torrent_base64: str | None = Field(default=None, max_length=6 * 1024 * 1024)


@app.post("/torrents/metadata", dependencies=[Depends(auth)])
def metadata(body: MetadataInput):
    if not body.torrent_base64 and not (body.source or "").startswith(
        ("magnet:?", "https://")
    ):
        raise HTTPException(422, "use_magnet_or_https")
    try:
        raw = (
            base64.b64decode(body.torrent_base64, validate=True)
            if body.torrent_base64
            else None
        )
        if raw is None and (body.source or "").startswith("https://"):
            raw = fetch_torrent(body.source)
        # Metadata can block for 60s, but never blocks API event loop.
        if not metadata_slot.acquire(blocking=False):
            raise HTTPException(429, "metadata_busy")
        try:
            description, raw = engine.metadata(body.source, raw)
        finally:
            metadata_slot.release()
    except HTTPException:
        raise
    except TimeoutError:
        raise HTTPException(504, "metadata_timeout")
    except Exception:
        raise HTTPException(422, "invalid_or_unsafe_torrent")
    mid = secrets.token_hex(16)
    with lock:
        reserve_control_write(len(raw))
        while (
            db.execute(
                "select coalesce(sum(length(torrent)),0) from metadata"
            ).fetchone()[0]
            + len(raw)
            > MAX_METADATA_CACHE_BYTES
            or db.execute("select count(*) from metadata").fetchone()[0] >= 32
        ):
            db.execute(
                "delete from metadata where rowid=(select min(rowid) from metadata)"
            )
        db.execute(
            "insert into metadata values(?,?,?)", (mid, raw, json.dumps(description))
        )
        db.commit()
    return {"id": mid, **description}


class CreateInput(BaseModel):
    start: bool = True
    metadata_id: str
    selected: list[int] = Field(min_length=1, max_length=10000)


@app.post("/torrents", dependencies=[Depends(auth)])
def create(body: CreateInput):
    with lock:
        row = db.execute(
            "select * from metadata where id=?", (body.metadata_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "metadata_not_found")
        desc = json.loads(row["description"])
        files = [f for f in desc["files"] if f["index"] in set(body.selected)]
        if len(files) != len(set(body.selected)):
            raise HTTPException(422, "invalid_selection")
        total = sum(f["size"] for f in files)
        limit = limits()
        if total > limit["selected_bytes"]:
            raise HTTPException(403, "quota_exceeded")
        if (
            db.execute(
                "select count(*) from tasks where state not in ('ready','error')"
            ).fetchone()[0]
            >= limit["tasks"]
        ):
            raise HTTPException(409, "task_limit")
        reserve_control_write(len(row["torrent"]))
        tid = secrets.token_hex(16)
        db.execute(
            "insert into tasks(id,name,state,total_bytes,torrent,created) values(?,?,?,?,?,?)",
            (
                tid,
                desc["name"],
                "queued" if body.start else "paused",
                total,
                row["torrent"],
                time.time(),
            ),
        )
        for f in files:
            db.execute(
                "insert into files values(?,?,?,?,?,?,?)",
                (
                    secrets.token_hex(16),
                    tid,
                    f["index"],
                    f["path"],
                    f["size"],
                    "queued",
                    None,
                ),
            )
        db.commit()
        return task(tid)


def clean(row):
    result = {k: row[k] for k in row.keys() if k != "torrent"}
    phase = getattr(engine, "phase", None)
    if phase and phase["task_id"] == row["id"]:
        result.update({k: v for k, v in phase.items() if k != "task_id"})
    if row["state"] in ("paused", "error"):
        result["eta_seconds"] = None
    return result


@app.get("/torrents", dependencies=[Depends(auth)])
def tasks():
    with lock:
        return [
            clean(r) for r in db.execute("select * from tasks order by created desc")
        ]


@app.get("/torrents/{tid}", dependencies=[Depends(auth)])
def task(tid: str):
    with lock:
        r = db.execute("select * from tasks where id=?", (tid,)).fetchone()
    if not r:
        raise HTTPException(404, "task_not_found")
    return clean(r)


@app.get("/torrents/{tid}/files", dependencies=[Depends(auth)])
def taskfiles(tid: str):
    task(tid)
    with lock:
        return [
            dict(r) for r in db.execute("select * from files where task_id=?", (tid,))
        ]


@app.post("/torrents/{tid}/pause", dependencies=[Depends(auth)])
def pause(tid: str):
    return change(tid, "paused")


@app.post("/torrents/{tid}/resume", dependencies=[Depends(auth)])
def resume(tid: str):
    return change(tid, "queued")


def change(tid, state):
    task(tid)
    with lock:
        db.execute(
            "update tasks set state=?,error=null,speed=0 where id=?", (state, tid)
        )
        db.commit()
    return task(tid)


@app.delete("/torrents/{tid}", dependencies=[Depends(auth)])
def delete_task(tid: str):
    task(tid)
    with lock:
        if engine.batch and engine.batch["id"] == tid:
            db.execute("update tasks set state='cancel_requested' where id=?", (tid,))
            db.commit()
            return {"deleted": False, "pending": True}
        import shutil

        engine.discard_cache(tid)
        engine.ledger.drop(tid)
        db.execute("delete from files where task_id=? and drive_id is null", (tid,))
        db.execute("delete from tasks where id=?", (tid,))
        db.commit()
    return {"deleted": True}


@app.get("/files", dependencies=[Depends(auth)])
def files():
    with lock:
        return [
            file_view(r)
            for r in db.execute(
                "select files.*,coalesce(tasks.created,0) as created from files left join tasks on tasks.id=files.task_id order by created desc"
            )
        ]


@app.get("/files/{fid}", dependencies=[Depends(auth)])
def file(fid: str):
    with lock:
        r = db.execute(
            "select files.*,coalesce(tasks.created,0) as created from files left join tasks on tasks.id=files.task_id where files.id=?",
            (fid,),
        ).fetchone()
    if not r:
        raise HTTPException(404, "file_not_found")
    return file_view(r)


def file_view(row):
    result = dict(row)
    path = ROOT / "workspace" / result["task_id"] / safe_path(result["path"])
    result["server_present"] = path.is_file()
    return result


def download_auth(
    fid: str,
    authorization: str = Header(default=""),
    expires: int = 0,
    signature: str = "",
):
    if signature:
        if len(os.getenv("ADMIN_API_TOKEN", "")) < 32:
            raise HTTPException(503, "admin_token_not_configured")
        payload = f"{fid}:{expires}"
        expected = hmac.new(
            os.getenv("ADMIN_API_TOKEN", "").encode(), payload.encode(), "sha256"
        ).hexdigest()
        if (
            expires < time.time()
            or expires > time.time() + 301
            or not secrets.compare_digest(expected, signature)
        ):
            raise HTTPException(401, "expired_or_invalid_link")
    else:
        auth(authorization)


@app.post("/files/{fid}/link", dependencies=[Depends(auth)])
def temporary_link(fid: str):
    file(fid)
    expires = int(time.time()) + 300
    sig = hmac.new(
        os.environ["ADMIN_API_TOKEN"].encode(), f"{fid}:{expires}".encode(), "sha256"
    ).hexdigest()
    return {
        "path": f"/files/{fid}/download?expires={expires}&signature={sig}",
        "expires": expires,
    }


@app.get("/files/{fid}/download", dependencies=[Depends(download_auth)])
def download(
    fid: str,
    range: str | None = Header(default=None),
    if_range: str | None = Header(default=None),
):
    f = file(fid)
    if not f["drive_id"]:
        path = ROOT / "workspace" / f["task_id"] / safe_path(f["path"])
        if (
            f["state"] == "uploading"
            and path.is_file()
            and path.stat().st_size == f["size"]
        ):
            return TrackedFileResponse(
                path,
                filename=Path(f["path"]).name,
                media_type="application/octet-stream",
            )
        raise HTTPException(409, "file_not_ready")
    c = drive.client()
    req = c.build_request(
        "GET",
        "https://www.googleapis.com/drive/v3/files/" + f["drive_id"],
        params={"alt": "media"},
        headers={
            **({"Range": range} if range else {}),
            **({"If-Range": if_range} if if_range and range else {}),
        },
    )
    r = c.send(req, stream=True)
    if r.status_code not in (200, 206):
        code = 416 if r.status_code == 416 else 502
        r.close()
        c.close()
        raise HTTPException(code, "drive_download_failed")

    def stream():
        try:
            yield from r.iter_bytes(1024 * 1024)
        finally:
            r.close()
            c.close()

    headers = {
        k: v
        for k, v in r.headers.items()
        if k.lower()
        in ["content-length", "content-range", "accept-ranges", "etag", "last-modified"]
    }
    return StreamingResponse(
        stream(),
        status_code=r.status_code,
        headers=headers,
        media_type="application/octet-stream",
    )


@app.delete("/files/{fid}", dependencies=[Depends(auth)])
def delete_file(fid: str):
    f = file(fid)
    if (engine.batch and engine.batch["id"] == f["task_id"]) or engine.ledger.load(
        f["task_id"]
    ):
        raise HTTPException(409, "active_batch_wait_or_cancel_task")
    if not f["drive_id"]:
        raise HTTPException(409, "file_not_ready")
    with drive.client() as c:
        r = c.delete("https://www.googleapis.com/drive/v3/files/" + f["drive_id"])
        r.raise_for_status()
    with lock:
        db.execute("delete from files where id=?", (fid,))
        db.commit()
    return {"deleted": True}


@app.get("/account", dependencies=[Depends(auth)])
def account():
    return {
        "id": "admin",
        "mode": "administrator_only",
        "plan": os.getenv("ACCOUNT_PLAN", "free"),
    }


@app.get("/account/limits", dependencies=[Depends(auth)])
def limits():
    return {
        "tasks": 5 if os.getenv("ACCOUNT_PLAN") == "premium" else 1,
        "selected_bytes": (500 if os.getenv("ACCOUNT_PLAN") == "premium" else 20)
        * 1000**3,
        "workspace_bytes": 10 * 1024**3,
        "phone_downloads": os.getenv("ACCOUNT_PLAN") == "premium",
    }


@app.get("/account/subscription", dependencies=[Depends(auth)])
def subscription():
    return {
        "plan": account()["plan"],
        "premium_monthly_usd": "4.99",
        "billing_enabled": False,
    }


@app.post("/drive/authorize", dependencies=[Depends(auth)])
def drive_authorize():
    from .oauth import begin

    try:
        return {"url": begin()}
    except Exception:
        raise HTTPException(503, "google_oauth_not_configured")


@app.get("/drive/callback")
def drive_callback(code: str, state: str):
    from .oauth import finish

    try:
        finish(code, state)
        return {"connected": True, "message": "Вернитесь в приложение"}
    except Exception:
        raise HTTPException(400, "oauth_exchange_failed")


@app.delete("/drive", dependencies=[Depends(auth)])
def drive_disconnect():
    from .oauth import token_path, refresh_token

    with lock:
        db.execute(
            "update tasks set state='paused',speed=0 where state in ('downloading','uploading','checking')"
        )
        db.commit()

    token = refresh_token()
    if token:
        import httpx

        r = httpx.post(
            "https://oauth2.googleapis.com/revoke", data={"token": token}, timeout=30
        )
        if r.status_code not in (200, 400):
            raise HTTPException(502, "oauth_revoke_failed")
    token_path().unlink(missing_ok=True)
    os.environ.pop("GOOGLE_REFRESH_TOKEN", None)
    return {"disconnected": True}


@app.get("/drive/folders", dependencies=[Depends(auth)])
def drive_folders():
    with drive.client() as c:
        r = c.get(
            "https://www.googleapis.com/drive/v3/files",
            params={
                "q": "mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                "fields": "files(id,name),nextPageToken",
                "pageSize": 100,
            },
        )
        r.raise_for_status()
        return r.json()


class FolderInput(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$", max_length=200)


@app.put("/drive/folder", dependencies=[Depends(auth)])
def drive_folder(body: FolderInput):
    with drive.client() as c:
        r = c.get(
            "https://www.googleapis.com/drive/v3/files/" + body.id,
            params={"fields": "id,mimeType"},
        )
        r.raise_for_status()
        if r.json()["mimeType"] != "application/vnd.google-apps.folder":
            raise HTTPException(422, "not_a_folder")
    os.environ["GOOGLE_DRIVE_FOLDER_ID"] = body.id
    (ROOT / "drive-folder.txt").write_text(body.id)
    return {"id": body.id}


@app.get("/server/settings", dependencies=[Depends(auth)])
def server_settings():
    path = ROOT / "server-settings.json"
    return (
        json.loads(path.read_text())
        if path.exists()
        else {"auto_drive": True, "auto_delete": True, "parallelism": 1}
    )


class ServerSettings(BaseModel):
    auto_drive: bool = True
    auto_delete: bool = True
    parallelism: int = Field(default=1, ge=1, le=1)


@app.put("/server/settings", dependencies=[Depends(auth)])
def set_server_settings(body: ServerSettings):
    temp = ROOT / "server-settings.tmp"
    temp.write_text(json.dumps(body.model_dump()))
    temp.replace(ROOT / "server-settings.json")
    return body


@app.post("/server/cleanup", dependencies=[Depends(auth)])
def cleanup():
    import shutil

    deleted = 0
    with lock:
        for folder in (ROOT / "workspace").iterdir():
            if not folder.is_dir() or folder.name == "metadata":
                continue
            if engine.batch and engine.batch["id"] == folder.name:
                continue
            if engine.ledger.load(folder.name):
                continue
            pending = sum(
                1
                for f in db.execute(
                    "select path from files where task_id=? and drive_id is null",
                    (folder.name,),
                )
                if (folder / safe_path(f["path"])).is_file()
            )
            if (
                pending == 0
                and db.execute(
                    "select count(*) from files where task_id=?", (folder.name,)
                ).fetchone()[0]
                > 0
            ):
                engine.discard_cache(folder.name)
                engine.ledger.drop(folder.name)
                deleted += 1
    return {"deleted_batches": deleted}


class NewFolderInput(BaseModel):
    name: str = Field(default="Cloud Torrent Client", min_length=1, max_length=200)


@app.post("/drive/folders", dependencies=[Depends(auth)])
def create_drive_folder(body: NewFolderInput):
    with drive.client() as c:
        r = c.post(
            "https://www.googleapis.com/drive/v3/files",
            json={"name": body.name, "mimeType": "application/vnd.google-apps.folder"},
        )
        r.raise_for_status()
        fid = r.json()["id"]
    os.environ["GOOGLE_DRIVE_FOLDER_ID"] = fid
    (ROOT / "drive-folder.txt").write_text(fid)
    return {"id": fid, "name": body.name}


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    # Never echo upstream URLs, headers, OAuth codes, tokens, or arbitrary exception messages.
    return JSONResponse({"error": {"code": "backend_error"}}, status_code=500)
