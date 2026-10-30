import os

os.environ["ADMIN_API_TOKEN"] = "a" * 40
os.environ["DATA_DIR"] = "/tmp/cloud-torrent-test"
from fastapi.testclient import TestClient
from backend.main import app, db
from backend.scheduler import choose_batch, safe_path
import libtorrent as lt, base64

client = TestClient(app)
H = {"Authorization": "Bearer " + "a" * 40}


def torrent():
    fs = lt.file_storage()
    fs.add_file("legal/test.txt", 1024)
    t = lt.create_torrent(fs, 16384, flags=lt.create_torrent.v1_only)
    t.set_hash(0, __import__("hashlib").sha1(b"a" * 1024).digest())
    return lt.bencode(t.generate())


def test_auth():
    assert client.get("/health").status_code == 200
    assert client.get("/torrents").status_code == 401
    assert client.get("/torrents", headers=H).status_code == 200


def test_scheduler_boundary_and_max_count():
    files = [{"index": i, "size": n} for i, n in enumerate([8, 4, 4, 2])]
    batch, res = choose_batch(files, 1, 16)
    assert [f["size"] for f in batch] == [2, 4, 4]
    assert res == 16
    assert choose_batch([{"index": 0, "size": 20}], 1, 10) == ([], 0)


def test_paths():
    import pytest

    for p in ["/etc/passwd", "../x", "a/../../x", "a\\b"]:
        with pytest.raises(ValueError):
            safe_path(p)


def test_metadata_and_shared_state():
    r = client.post(
        "/torrents/metadata",
        headers=H,
        json={"torrent_base64": base64.b64encode(torrent()).decode()},
    )
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["total_bytes"] == 1024 and m["files"][0]["path"] == "legal/test.txt"
    db.execute("delete from tasks")
    db.execute("delete from files")
    db.commit()
    r = client.post(
        "/torrents", headers=H, json={"metadata_id": m["id"], "selected": [0]}
    )
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    assert client.post(f"/torrents/{tid}/pause", headers=H).json()["state"] == "paused"
    assert client.post(f"/torrents/{tid}/resume", headers=H).json()["state"] == "queued"
    assert len(client.get(f"/torrents/{tid}/files", headers=H).json()) == 1
    assert client.get("/files", headers=H).json()[0]["task_id"] == tid
    assert client.delete(f"/torrents/{tid}", headers=H).status_code == 200


def test_ssrf_closed():
    for source in [
        "http://127.0.0.1/a",
        "https://169.254.169.254/",
        "file:///etc/passwd",
    ]:
        assert (
            client.post(
                "/torrents/metadata", headers=H, json={"source": source}
            ).status_code
            == 422
        )


def test_offline_drive_truth():
    assert client.get("/server/status", headers=H).json()["drive_connected"] is False
    assert (
        client.get("/server/status", headers=H).json()["large_single_file_streaming"]
        is False
    )
    assert (
        client.get("/account/subscription", headers=H).json()["billing_enabled"]
        is False
    )


def test_temporary_link_requires_valid_auth_and_expiry():
    import hmac, time
    from backend.main import download_auth
    from fastapi import HTTPException
    import pytest

    expiry = int(time.time()) + 100
    sig = hmac.new(("a" * 40).encode(), f"x:{expiry}".encode(), "sha256").hexdigest()
    download_auth("x", "", expiry, sig)
    with pytest.raises(HTTPException):
        download_auth("other", "", expiry, sig)
    with pytest.raises(HTTPException):
        download_auth("x", "", int(time.time()) - 1, sig)


def test_drive_failure_does_not_delete_completed_batch(tmp_path):
    from backend.scheduler import Engine

    class FailedDrive:
        configured = True

        def upload(self, *args):
            raise IOError("network")

    class Handle:
        def is_valid(self):
            return True

        def pause(self):
            pass

        def resume(self):
            pass

        def flush_cache(self):
            pass

        def status(self):
            class S:
                download_rate = 0

                class errc:
                    @staticmethod
                    def value():
                        return 0

            return S()

        def file_progress(self):
            return [1024]

    class Alert:
        def __init__(self, h):
            self.handle = h

    class Session:
        def wait_for_alert(self, x):
            pass

        def pop_alerts(self):
            return [Alert(h)]

    from unittest.mock import patch

    engine = Engine(tmp_path / "workspace", db, FailedDrive())
    h = Handle()
    folder = tmp_path / "workspace/batch"
    (folder / "legal").mkdir(parents=True)
    path = folder / "legal/test.txt"
    path.write_bytes(b"a" * 1024)
    db.execute(
        "insert or replace into tasks(id,name,state,total_bytes,created) values('batch','legal','downloading',1024,0)"
    )
    db.execute(
        "insert or replace into files values('test-file','batch',0,'legal/test.txt',1024,'downloading',NULL)"
    )
    db.commit()
    engine.batch = {
        "id": "batch",
        "handle": h,
        "dir": folder,
        "files": [{"index": 0, "path": "legal/test.txt", "size": 1024}],
        "reserved": 33792,
    }
    engine.session = Session()
    import pytest

    with patch("backend.scheduler.lt.cache_flushed_alert", Alert):
        with pytest.raises(IOError):
            engine.tick()
    assert path.read_bytes() == b"a" * 1024
    assert (
        db.execute("select drive_id from files where id='test-file'").fetchone()[0]
        is None
    )
    db.execute("delete from files where id='test-file'")
    db.execute("delete from tasks where id='batch'")
    db.commit()


def test_drive_resumable_upload_verifies_checksum_and_saves_session(
    tmp_path, monkeypatch
):
    import hashlib, httpx, json
    from cryptography.fernet import Fernet
    from backend.drive import Drive

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "folder")
    path = tmp_path / "file.txt"
    data = b"a" * (9 * 1024 * 1024)
    path.write_bytes(data)
    md5 = hashlib.md5(data).hexdigest()
    calls = []

    def handler(request):
        calls.append(
            (request.method, str(request.url), request.headers.get("content-range"))
        )
        if request.method == "GET" and request.url.path.endswith("/files"):
            return httpx.Response(200, json={"files": []})
        if request.method == "POST":
            return httpx.Response(
                200, headers={"Location": "https://www.googleapis.com/upload/session"}
            )
        if request.method == "PUT":
            if request.headers["content-range"].startswith("bytes 0-"):
                return httpx.Response(308, headers={"Range": "bytes=0-8388607"})
            return httpx.Response(200, json={"id": "uploaded"})
        return httpx.Response(
            200, json={"id": "uploaded", "size": str(len(data)), "md5Checksum": md5}
        )

    drive = Drive()
    monkeypatch.setattr(
        drive, "client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert drive.upload(path, "file.txt")["id"] == "uploaded"
    assert len([x for x in calls if x[0] == "PUT"]) == 2
    states = list(tmp_path.glob("upload-*.enc"))
    assert len(states) == 1
    state = json.loads(
        Fernet(os.environ["TOKEN_ENCRYPTION_KEY"]).decrypt(states[0].read_bytes())
    )
    assert state["completed_id"] == "uploaded"


def test_large_metadata_is_not_rejected_by_free_workspace_limit():
    fs = lt.file_storage()
    fs.add_file("legal/large.bin", 150 * 1000**3)
    fs.add_file("legal/small.txt", 1024)
    t = lt.create_torrent(fs, 16 * 1024**2, flags=lt.create_torrent.v1_only)
    for i in range(t.num_pieces()):
        t.set_hash(i, b"x" * 20)
    raw = lt.bencode(t.generate())
    r = client.post(
        "/torrents/metadata",
        headers=H,
        json={"torrent_base64": base64.b64encode(raw).decode()},
    )
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    assert r.json()["total_bytes"] > 150 * 1000**3
    assert (
        client.post(
            "/torrents", headers=H, json={"metadata_id": mid, "selected": [0, 1]}
        ).status_code
        == 403
    )


def test_server_automation_persists_and_cleanup_requires_auth():
    r = client.put(
        "/server/settings",
        headers=H,
        json={"auto_drive": False, "auto_delete": False, "parallelism": 1},
    )
    assert r.status_code == 200
    assert client.get("/server/settings", headers=H).json()["auto_drive"] is False
    assert client.post("/server/cleanup").status_code == 401
    assert (
        client.put("/server/settings", headers=H, json={"parallelism": 5}).status_code
        == 422
    )
    client.put(
        "/server/settings",
        headers=H,
        json={"auto_drive": True, "auto_delete": True, "parallelism": 1},
    )


def test_verified_local_download_supports_range_and_presence():
    from backend.main import ROOT
    import time

    folder = ROOT / "workspace" / "local-range"
    folder.mkdir(exist_ok=True)
    path = folder / "legal.txt"
    path.write_bytes(b"abcdef")
    db.execute(
        "insert or replace into tasks(id,name,state,total_bytes,created) values('local-range','legal','uploading',6,?)",
        (time.time(),),
    )
    db.execute(
        "insert or replace into files values('local-range-file','local-range',0,'legal.txt',6,'uploading',NULL)"
    )
    db.commit()
    try:
        data = client.get("/files/local-range-file", headers=H).json()
        assert data["server_present"] is True and data["created"] > 0
        assert client.get("/files/local-range-file/download").status_code == 401
        r = client.get(
            "/files/local-range-file/download", headers={**H, "Range": "bytes=1-3"}
        )
        assert r.status_code == 206, r.text
        assert r.content == b"bcd" and r.headers["content-range"] == "bytes 1-3/6"
    finally:
        path.unlink()
        folder.rmdir()
        db.execute("delete from files where id='local-range-file'")
        db.execute("delete from tasks where id='local-range'")
        db.commit()


def test_chunked_body_cannot_bypass_request_limit():
    r = client.post(
        "/torrents/metadata",
        headers=H,
        content=(b"x" * (1024 * 1024) for _ in range(9)),
    )
    assert r.status_code == 413 and r.json()["error"]["code"] == "request_too_large"


def test_metadata_cache_is_bounded(monkeypatch):
    import backend.main as main

    monkeypatch.setattr(main, "MAX_METADATA_CACHE_BYTES", 2 * 1024 * 1024)
    for i in range(3):
        db.execute(
            "insert or replace into metadata values(?,?,?)",
            (f"cache-test-{i}", b"x" * (1024 * 1024), "{}"),
        )
    db.commit()
    r = client.post(
        "/torrents/metadata",
        headers=H,
        json={"torrent_base64": base64.b64encode(torrent()).decode()},
    )
    assert r.status_code == 200, r.text
    assert (
        db.execute("select sum(length(torrent)) from metadata").fetchone()[0]
        <= 2 * 1024 * 1024
    )


def test_expired_access_token_replays_chunk_after_refresh():
    import httpx
    from backend.drive import AuthorizedDriveClient

    issued = []
    seen = []

    def token():
        issued.append(1)
        return "test-token-" + str(len(issued))

    def handler(request):
        seen.append((request.headers["Authorization"], request.content))
        return httpx.Response(401 if len(seen) == 1 else 200, json={"id": "ok"})

    with AuthorizedDriveClient(token, transport=httpx.MockTransport(handler)) as c:
        r = c.put("https://www.googleapis.com/upload/session", content=b"chunk")
    assert r.status_code == 200 and len(issued) == 2
    assert seen[0][1] == seen[1][1] == b"chunk" and seen[0][0] != seen[1][0]


def test_startup_preserves_unconfirmed_payload_and_lease(tmp_path):
    from backend.scheduler import Engine
    import pytest

    folder = tmp_path / "workspace/task"
    folder.mkdir(parents=True)
    path = folder / "partial.bin"
    path.write_bytes(b"keep")

    class Offline:
        configured = False

    instance = Engine(tmp_path / "workspace", db, Offline())
    assert path.read_bytes() == b"keep"
    with pytest.raises(RuntimeError, match="only_one_scheduler"):
        Engine(tmp_path / "workspace", db, Offline())
    instance.ledger.save("task", [0], 1024 * 1024, 0)
    assert instance.ledger.load("task")["indices"] == [0]
    assert 0 < instance.ledger.remaining() <= 1024 * 1024


def test_open_download_is_counted_after_cache_unlink(tmp_path):
    from backend.scheduler import Engine

    class Offline:
        configured = False

    instance = Engine(tmp_path / "workspace", db, Offline())
    folder = tmp_path / "workspace/task"
    folder.mkdir()
    path = folder / "file.bin"
    path.write_bytes(b"x" * 32768)
    with instance.read_payload(path) as source:
        instance.discard_cache("task")
        used = instance.storage()["used_bytes"]
        assert not path.exists() and used >= 32768
        assert source.read() == b"x" * 32768
    assert instance.storage()["used_bytes"] < used


def test_local_response_survives_cleanup_unlink(tmp_path, monkeypatch):
    import asyncio
    from contextlib import contextmanager
    from backend.main import TrackedFileResponse, engine

    path = tmp_path / "legal.txt"
    path.write_bytes(b"legal test data")

    @contextmanager
    def pin(original):
        with open(original, "rb") as source:
            path.unlink()
            yield source

    monkeypatch.setattr(engine, "read_payload", pin)
    messages = []

    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.request"}

    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"range", b"bytes=6-9")],
        "extensions": {"http.response.pathsend": {}},
    }
    asyncio.run(TrackedFileResponse(path)(scope, receive, send))
    assert messages[0]["status"] == 206
    assert b"".join(m.get("body", b"") for m in messages) == b"test"
