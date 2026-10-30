"""Start the actual Uvicorn process locally; no external service is claimed."""

import subprocess, os, secrets, tempfile, time, json
from pathlib import Path
import httpx

root = Path(__file__).resolve().parents[1]
token = secrets.token_urlsafe(48)
env = {**os.environ, "DATA_DIR": tempfile.mkdtemp(), "ADMIN_API_TOKEN": token}
log = (root / "artifacts/api-smoke-server.log").open("w")
p = subprocess.Popen(
    [
        "python",
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "19080",
        "--no-access-log",
    ],
    cwd=root,
    env=env,
    stdout=log,
    stderr=log,
)
try:
    with httpx.Client(
        base_url="http://127.0.0.1:19080", trust_env=False, timeout=5
    ) as c:
        end = time.monotonic() + 15
        while True:
            try:
                r = c.get("/health")
                break
            except httpx.ConnectError:
                if time.monotonic() > end:
                    raise
                time.sleep(0.2)
        assert r.json()["status"] == "ok"
        assert c.get("/torrents").status_code == 401
        h = {"Authorization": "Bearer " + token}
        status = c.get("/server/status", headers=h)
        status.raise_for_status()
        assert status.json()["drive_connected"] is False
        storage = c.get("/server/storage", headers=h)
        storage.raise_for_status()
        assert storage.json()["capacity_bytes"] <= 10 * 1024**3
        assert c.get("/torrents", headers=h).json() == []
        result = {
            "passed": True,
            "transport": "real localhost HTTP/Uvicorn",
            "health": r.json(),
            "unauthorized_status": 401,
            "status": status.json(),
            "capacity_bytes": storage.json()["capacity_bytes"],
            "external_bothost_test": False,
        }
        (root / "artifacts/api-smoke.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
finally:
    p.terminate()
    p.wait(timeout=10)
    log.close()
