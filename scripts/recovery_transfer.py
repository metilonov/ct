"""Kill a real libtorrent worker after cache flush, then recover without the seeder."""

import os, sys, sqlite3, time, tempfile, subprocess, json, hashlib
from pathlib import Path
import libtorrent as lt
from backend.scheduler import Engine


def connect_db(root):
    db = sqlite3.connect(root / "state.db")
    db.row_factory = sqlite3.Row
    return db


if len(sys.argv) > 1 and sys.argv[1] == "child":
    root = Path(sys.argv[2])
    db = connect_db(root)

    class CrashSink:
        configured = True

        def upload(self, *args):
            (root / "crashed-after-flush").write_text("ready")
            os._exit(44)

    engine = Engine(root / "workspace", db, CrashSink())
    engine.session.set_ip_filter(lt.ip_filter())
    end = time.monotonic() + 40
    while time.monotonic() < end:
        engine.tick()
        if engine.batch:
            engine.batch["handle"].connect_peer(("127.0.0.1", int(sys.argv[3])))
        time.sleep(0.1)
    raise RuntimeError("child_transfer_timeout")

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
db = connect_db(root)
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
seeder = lt.session(
    {
        "enable_dht": False,
        "enable_lsd": False,
        "enable_upnp": False,
        "enable_natpmp": False,
        "listen_interfaces": "127.0.0.1:0",
        "outgoing_interfaces": "127.0.0.1",
    }
)
p = lt.add_torrent_params()
p.ti = ti
p.save_path = str(seed)
p.flags &= ~lt.torrent_flags.paused
p.flags &= ~lt.torrent_flags.auto_managed
h = seeder.add_torrent(p)
while not seeder.listen_port():
    time.sleep(0.05)
child = subprocess.run(
    [
        sys.executable,
        "-m",
        "scripts.recovery_transfer",
        "child",
        str(root),
        str(seeder.listen_port()),
    ],
    timeout=50,
)
assert child.returncode == 44, child.returncode
source = root / "workspace/task/legal/file1.txt"
assert source.read_bytes() == (seed / "legal/file1.txt").read_bytes()
assert (root / "batches/task.json").exists()
seeder.remove_torrent(h)


class VerifiedSink:
    configured = True

    def upload(self, path, relative, progress=None, namespace=""):
        assert path.read_bytes() == (seed / "legal/file1.txt").read_bytes()
        return {"id": "recovered-local-receipt"}


engine = Engine(root / "workspace", db, VerifiedSink())
assert source.exists(), "restart must not delete unconfirmed local data"
end = time.monotonic() + 30
while time.monotonic() < end:
    engine.tick()
    state = db.execute("select state from tasks").fetchone()[0]
    if state == "ready":
        break
    time.sleep(0.1)
assert state == "ready", state
assert (
    not (root / "workspace/task").exists() and not (root / "batches/task.json").exists()
)
result = {
    "passed": True,
    "crash_exit_code": 44,
    "unconfirmed_data_retained": True,
    "recovered_without_seeder": True,
    "final_state": state,
    "cleanup_after_verified_receipt": True,
    "scope": "real libtorrent, local verified sink; not Google Drive",
}
Path("artifacts/recovery-transfer.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
