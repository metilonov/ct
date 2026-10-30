"""Real libtorrent loopback transfer of self-created legal content; no external trackers."""

import libtorrent as lt, time, hashlib, tempfile, json
from pathlib import Path

root = Path(tempfile.mkdtemp())
seed = root / "seed"
dest = root / "dest"
(seed / "legal").mkdir(parents=True)
dest.mkdir()
for i, size in enumerate([40000, 60000, 80000]):
    (seed / f"legal/file{i}.txt").write_bytes(bytes([65 + i]) * size)
fs = lt.file_storage()
for i in range(3):
    fs.add_file(f"legal/file{i}.txt", (seed / f"legal/file{i}.txt").stat().st_size)
t = lt.create_torrent(fs, 16384, flags=lt.create_torrent.v1_only)
lt.set_piece_hashes(t, str(seed))
raw = lt.bencode(t.generate())
ti = lt.torrent_info(raw)
settings = {
    "alert_mask": int(lt.alert.category_t.storage_notification),
    "enable_dht": False,
    "enable_lsd": False,
    "enable_upnp": False,
    "enable_natpmp": False,
    "listen_interfaces": "127.0.0.1:0",
    "outgoing_interfaces": "127.0.0.1",
    "allow_multiple_connections_per_ip": True,
}
a = lt.session(settings)
b = lt.session(settings)
p = lt.add_torrent_params()
p.ti = ti
p.save_path = str(seed)
p.flags &= ~lt.torrent_flags.paused
p.flags &= ~lt.torrent_flags.auto_managed
sh = a.add_torrent(p)
p = lt.add_torrent_params()
p.ti = ti
p.save_path = str(dest)
p.file_priorities = [0, 4, 0]
p.flags &= ~lt.torrent_flags.paused
p.flags &= ~lt.torrent_flags.auto_managed
dh = b.add_torrent(p)
end = time.monotonic() + 45
while time.monotonic() < end:
    dh.connect_peer(("127.0.0.1", a.listen_port()))
    if dh.file_progress()[1] >= 60000:
        break
    time.sleep(0.25)
assert dh.file_progress()[1] >= 60000, str(dh.status().state)
dh.pause()
dh.flush_cache()
end = time.monotonic() + 10
while time.monotonic() < end:
    b.wait_for_alert(200)
    if any(isinstance(a, lt.cache_flushed_alert) for a in b.pop_alerts()):
        break
assert (dest / "legal/file1.txt").read_bytes() == (
    seed / "legal/file1.txt"
).read_bytes()
result = {
    "selected_file_bytes": 60000,
    "sha256": hashlib.sha256((dest / "legal/file1.txt").read_bytes()).hexdigest(),
    "file_progress": dh.file_progress(),
    "passed": True,
    "fixture": "self-created legal text",
    "scope": "loopback selective download, not BotHost or Google Drive",
}
print(json.dumps(result, indent=2))
Path("artifacts/libtorrent-transfer.json").write_text(json.dumps(result, indent=2))
