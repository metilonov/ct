"""Scheduler E2E with real libtorrent and local receipt sink. This is not a Drive test."""

import tempfile, time, sqlite3, hashlib, json, shutil
from pathlib import Path
import libtorrent as lt
from backend.scheduler import Engine

root = Path(tempfile.mkdtemp())
seed = root / "seed"
(seed / "legal").mkdir(parents=True)
for i, size in enumerate([40000, 60000]):
    (seed / f"legal/file{i}.txt").write_bytes(bytes([65 + i]) * size)
fs = lt.file_storage()
fs.add_file("legal/file0.txt", 40000)
fs.add_file("legal/file1.txt", 60000)
t = lt.create_torrent(fs, 16384, flags=lt.create_torrent.v1_only)
lt.set_piece_hashes(t, str(seed))
raw = lt.bencode(t.generate())
ti = lt.torrent_info(raw)
db = sqlite3.connect(root / "test.db")
db.row_factory = sqlite3.Row
db.executescript(
    "CREATE TABLE tasks(id TEXT,name TEXT,state TEXT,total_bytes INTEGER,progress REAL,speed INTEGER,error TEXT,torrent BLOB,created REAL); CREATE TABLE files(id TEXT,task_id TEXT,file_index INTEGER,path TEXT,size INTEGER,state TEXT,drive_id TEXT);"
)
db.execute(
    "insert into tasks values(?,?,?,?,?,?,?,?,?)",
    ("task", "legal", "queued", 60000, 0, 0, None, raw, 0),
)
db.execute(
    "insert into files values(?,?,?,?,?,?,?)",
    ("file", "task", 1, "legal/file1.txt", 60000, "queued", None),
)
db.commit()


class LocalSink:
    configured = True

    def upload(self, path, relative, progress=None, namespace=""):
        target = root / "sink.txt"
        shutil.copyfile(path, target)
        assert (
            hashlib.sha256(target.read_bytes()).digest()
            == hashlib.sha256((seed / "legal/file1.txt").read_bytes()).digest()
        )
        return {"id": "local-verified-receipt"}


engine = Engine(root / "workspace", db, LocalSink())
engine.session.set_ip_filter(lt.ip_filter())  # Loopback permitted ONLY in this test.
settings = {
    "enable_dht": False,
    "enable_lsd": False,
    "enable_upnp": False,
    "enable_natpmp": False,
    "listen_interfaces": "127.0.0.1:0",
    "outgoing_interfaces": "127.0.0.1",
}
seeder = lt.session(settings)
p = lt.add_torrent_params()
p.ti = ti
p.save_path = str(seed)
p.flags &= ~lt.torrent_flags.paused
p.flags &= ~lt.torrent_flags.auto_managed
handle = seeder.add_torrent(p)
end = time.monotonic() + 45
while time.monotonic() < end:
    engine.tick()
    if engine.batch:
        engine.batch["handle"].connect_peer(("127.0.0.1", seeder.listen_port()))
    state = db.execute("select state from tasks").fetchone()[0]
    if state == "ready":
        break
    time.sleep(0.2)
if state != "ready":
    h = engine.batch["handle"]
    s = h.status()
    print(
        {
            "state": str(s.state),
            "peers": s.num_peers,
            "error": str(s.errc),
            "file_progress": h.file_progress(),
            "priorities": h.file_priorities(),
            "seed_state": str(handle.status().state),
            "seed_port": seeder.listen_port(),
            "seed_peers": handle.status().num_peers,
            "root": str(root),
        },
        flush=True,
    )
    for alert in engine.session.pop_alerts():
        print(str(alert), flush=True)
assert state == "ready", state
assert not (root / "workspace/task").exists()
assert (
    db.execute("select drive_id from files").fetchone()[0] == "local-verified-receipt"
)
result = {
    "passed": True,
    "torrent_state": state,
    "workspace_removed_after_receipt": True,
    "sink": "local verified copy, not Google Drive",
    "bytes": 60000,
}
Path("artifacts/scheduler-transfer.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
