import os, hashlib, time, json
from pathlib import Path, PurePosixPath
import httpx
from .oauth import refresh_token, cipher


class AuthorizedDriveClient(httpx.Client):
    """Retry once after a token refresh; chunk bodies are replayable bytes."""

    def __init__(self, token_provider, **kwargs):
        self.token_provider = token_provider
        super().__init__(
            headers={"Authorization": "Bearer " + token_provider()}, **kwargs
        )

    def send(self, request, **kwargs):
        response = super().send(request, **kwargs)
        if response.status_code == 401:
            response.close()
            authorization = "Bearer " + self.token_provider()
            self.headers["Authorization"] = authorization
            request.headers["Authorization"] = authorization
            response = super().send(request, **kwargs)
        return response


class Drive:
    @property
    def configured(self):
        try:
            return bool(
                all(
                    os.getenv(k)
                    for k in [
                        "GOOGLE_CLIENT_ID",
                        "GOOGLE_CLIENT_SECRET",
                        "GOOGLE_DRIVE_FOLDER_ID",
                        "TOKEN_ENCRYPTION_KEY",
                    ]
                )
                and refresh_token()
            )
        except Exception:
            return False

    def connected(self):
        if not self.configured:
            return False
        try:
            with self.client() as c:
                r = c.get(
                    "https://www.googleapis.com/drive/v3/files/"
                    + os.environ["GOOGLE_DRIVE_FOLDER_ID"],
                    params={"fields": "id"},
                )
                return r.is_success
        except Exception:
            return False

    def access_token(self):
        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data=dict(
                client_id=os.environ["GOOGLE_CLIENT_ID"],
                client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
                refresh_token=refresh_token(),
                grant_type="refresh_token",
            ),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["access_token"]

    def client(self):
        return AuthorizedDriveClient(self.access_token, timeout=120)

    def folder(self, c, parent, name):
        q = (
            "'"
            + parent.replace("'", "\\'")
            + "' in parents and name = '"
            + name.replace("\\", "\\\\").replace("'", "\\'")
            + "' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        r = c.get(
            "https://www.googleapis.com/drive/v3/files",
            params={"q": q, "fields": "files(id)"},
        )
        r.raise_for_status()
        found = r.json()["files"]
        if found:
            return found[0]["id"]
        r = c.post(
            "https://www.googleapis.com/drive/v3/files",
            json={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent],
            },
        )
        r.raise_for_status()
        return r.json()["id"]

    def upload(self, path, relative, progress=None, namespace=""):
        def report(offset, total, stage):
            if not 0 <= offset <= total:
                raise RuntimeError("invalid_upload_offset")
            if progress:
                progress(offset, total, stage)

        size = path.stat().st_size
        hashed = 0
        report(0, size, "checking")
        digest = hashlib.md5()
        with path.open("rb") as f:
            while chunk := f.read(8 * 1024**2):
                digest.update(chunk)
                hashed += len(chunk)
                report(hashed, size, "checking")
        checksum = digest.hexdigest()
        size = path.stat().st_size
        identity = hashlib.sha256(
            (
                namespace
                + ":"
                + relative
                + ":"
                + checksum
                + ":"
                + os.environ["GOOGLE_DRIVE_FOLDER_ID"]
            ).encode()
        ).hexdigest()
        state_path = Path(os.getenv("DATA_DIR", "./data")) / (
            "upload-" + identity + ".enc"
        )

        def save(state):
            temp = state_path.with_suffix(".tmp")
            temp.write_bytes(cipher().encrypt(json.dumps(state).encode()))
            temp.chmod(0o600)
            temp.replace(state_path)

        state = (
            json.loads(cipher().decrypt(state_path.read_bytes()))
            if state_path.exists()
            else {}
        )
        with self.client() as c:
            parent = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
            for part in PurePosixPath(relative).parts[:-1]:
                parent = self.folder(c, parent, part)
            # Recover completed uploads even if the process died before saving the SQLite drive_id.
            q = (
                "trashed = false and appProperties has { key='cloudTorrentUpload' and value='"
                + identity
                + "' }"
            )
            r = c.get(
                "https://www.googleapis.com/drive/v3/files",
                params={"q": q, "fields": "files(id,size,md5Checksum)"},
            )
            r.raise_for_status()
            complete = [
                x
                for x in r.json()["files"]
                if int(x.get("size", -1)) == size and x.get("md5Checksum") == checksum
            ]
            if complete:
                report(size, size, "checking")
                return complete[0]
            session = state.get("session")
            offset = 0
            result = None
            if session:
                probe = c.put(
                    session,
                    headers={"Content-Range": f"bytes */{size}", "Content-Length": "0"},
                )
                if probe.status_code in (200, 201):
                    result = probe.json()
                    offset = size
                elif probe.status_code == 308:
                    offset = (
                        int(probe.headers["Range"].split("-")[-1]) + 1
                        if probe.headers.get("Range")
                        else 0
                    )
                else:
                    session = None
            if not session:
                r = c.post(
                    "https://www.googleapis.com/upload/drive/v3/files",
                    params={"uploadType": "resumable", "fields": "id,size,md5Checksum"},
                    json={
                        "name": path.name,
                        "parents": [parent],
                        "appProperties": {"cloudTorrentUpload": identity},
                    },
                    headers={"X-Upload-Content-Length": str(size)},
                )
                r.raise_for_status()
                session = r.headers["location"]
                save({"session": session, "size": size})
            report(offset, size, "uploading")
            with path.open("rb") as f:
                failures = 0
                while result is None:
                    report(offset, size, "uploading")
                    f.seek(offset)
                    chunk = f.read(min(8 * 1024**2, size - offset))
                    headers = (
                        {
                            "Content-Range": f"bytes {offset}-{offset + len(chunk) - 1}/{size}"
                        }
                        if size
                        else {"Content-Range": "bytes */0", "Content-Length": "0"}
                    )
                    try:
                        r = c.put(session, content=chunk, headers=headers)
                        if r.status_code in (200, 201):
                            result = r.json()
                            offset = size
                            report(offset, size, "uploading")
                            break
                        if r.status_code != 308:
                            r.raise_for_status()
                        offset = (
                            int(r.headers["Range"].split("-")[-1]) + 1
                            if r.headers.get("Range")
                            else 0
                        )
                        report(offset, size, "uploading")
                        failures = 0
                    except (httpx.TransportError, httpx.HTTPStatusError):
                        failures += 1
                        if failures > 5:
                            raise
                        time.sleep(min(2**failures, 32))
                        probe = c.put(
                            session,
                            headers={
                                "Content-Range": f"bytes */{size}",
                                "Content-Length": "0",
                            },
                        )
                        if probe.status_code in (200, 201):
                            result = probe.json()
                            break
                        if probe.status_code != 308:
                            probe.raise_for_status()
                        offset = (
                            int(probe.headers["Range"].split("-")[-1]) + 1
                            if probe.headers.get("Range")
                            else 0
                        )
            report(size, size, "checking")
            verify = c.get(
                "https://www.googleapis.com/drive/v3/files/" + result["id"],
                params={"fields": "id,size,md5Checksum"},
            )
            verify.raise_for_status()
            result = verify.json()
            if int(result["size"]) != size or result.get("md5Checksum") != checksum:
                raise RuntimeError("drive_verification_failed")
            save({"completed_id": result["id"], "size": size, "md5": checksum})
            return result
