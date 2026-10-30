"""Single-process, fail-closed, batch scheduler. One shared engine for every client."""

import os, shutil, time, json, hashlib
from pathlib import Path
import libtorrent as lt
import fcntl
import threading
from contextlib import contextmanager
from .workspace import BatchLedger, allocated

MAX_WORKSPACE_BYTES = int(os.getenv("MAX_WORKSPACE_BYTES", 10 * 1024**3))
SAFETY_BYTES = int(os.getenv("SAFETY_BYTES", 256 * 1024**2))


def choose_batch(files, piece_length, budget, block_size=1, overhead_bytes=0):
    def cost(f):
        rounded = ((f["size"] + block_size - 1) // block_size) * block_size
        directories = (
            (len(Path(f["path"]).parents) + 2) * block_size
            if "path" in f and block_size > 1
            else 0
        )
        return rounded + 2 * piece_length + directories

    out = []
    used = overhead_bytes
    for f in sorted(files, key=lambda f: (cost(f), f["index"])):
        value = cost(f)
        if value <= budget - used:
            out.append(f)
            used += value
    return out, used if out else 0


def safe_path(name):
    p = Path(name)
    if p.is_absolute() or ".." in p.parts or "\\" in name or "\x00" in name:
        raise ValueError("unsafe_torrent_path")
    if (
        len(p.parts) > 32
        or len(name.encode()) > 1024
        or any(len(part.encode()) > 255 for part in p.parts)
    ):
        raise ValueError("torrent_path_resource_limit")
    return p


class UploadDeferred(Exception):
    pass


class Engine:
    def __init__(self, root, db, drive):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = db
        self.drive = drive
        self.io_lock = threading.RLock()
        self.readers = {}
        self.ledger = BatchLedger(self.root)
        self._lease = (self.root.parent / "scheduler.lock").open("a+b")
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("only_one_scheduler_per_data_directory")
        self.session = lt.session(
            {
                "listen_interfaces": "0.0.0.0:6881",
                "enable_dht": True,
                "enable_upnp": False,
                "enable_natpmp": False,
                "enable_lsd": False,
                "connections_limit": 80,
                "active_downloads": 1,
                "alert_mask": int(
                    lt.alert.category_t.storage_notification
                    | lt.alert.category_t.error_notification
                ),
            }
        )
        self.handles = {}
        self.batch = None
        self.phase = None
        # Preserve incomplete payloads and their batch journal across process restarts.
        # Libtorrent rechecks existing files when the same batch is attached again.
        filt = lt.ip_filter()
        for first, last in [
            ("0.0.0.0", "0.255.255.255"),
            ("10.0.0.0", "10.255.255.255"),
            ("100.64.0.0", "100.127.255.255"),
            ("127.0.0.0", "127.255.255.255"),
            ("169.254.0.0", "169.254.255.255"),
            ("172.16.0.0", "172.31.255.255"),
            ("192.168.0.0", "192.168.255.255"),
            ("224.0.0.0", "255.255.255.255"),
            ("::", "::ffff:ffff:ffff"),
            ("fc00::", "fdff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"),
            ("fe80::", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"),
        ]:
            filt.add_rule(first, last, 1)
        self.session.set_ip_filter(filt)

    @contextmanager
    def read_payload(self, path):
        path = Path(path)
        with self.io_lock:
            source = path.open("rb")
            stat = os.fstat(source.fileno())
            key = (stat.st_dev, stat.st_ino)
            entry = self.readers.setdefault(
                key, {"count": 0, "path": path, "bytes": stat.st_blocks * 512}
            )
            entry["count"] += 1
        try:
            yield source
        finally:
            source.close()
            with self.io_lock:
                self.readers[key]["count"] -= 1
                if not self.readers[key]["count"]:
                    del self.readers[key]

    def discard_cache(self, tid):
        self.ledger.path(tid)
        with self.io_lock:
            directory = self.root / tid
            if directory.exists():
                shutil.rmtree(directory)

    def metadata(self, source=None, raw=None):
        if raw:
            ti = lt.torrent_info(raw)
            return self.describe(ti), raw
        params = lt.parse_magnet_uri(source)
        # Do not allow user-supplied tracker/webseed endpoints to cause SSRF.
        params.trackers = []
        params.url_seeds = []
        params.http_seeds = []
        params.save_path = str(self.root / "metadata")
        params.flags |= (
            lt.torrent_flags.upload_mode
            | lt.torrent_flags.override_trackers
            | lt.torrent_flags.override_web_seeds
        )
        handle = self.session.add_torrent(params)
        try:
            until = time.monotonic() + 60
            while time.monotonic() < until:
                if handle.has_metadata():
                    ti = handle.torrent_file()
                    raw = lt.bencode(lt.create_torrent(ti).generate())
                    return self.describe(ti), raw
                time.sleep(0.25)
            raise TimeoutError("metadata_timeout")
        finally:
            self.session.remove_torrent(handle)

    def describe(self, ti):
        fs = ti.files()
        files = []
        if (
            fs.num_files() > 10000
            or ti.piece_length() > 16 * 1024**2
            or ti.num_pieces() > 1_000_000
        ):
            raise ValueError("metadata_resource_limit")
        for i in range(fs.num_files()):
            if fs.file_flags(i) & lt.file_storage.flag_pad_file:
                continue
            name = fs.file_path(i)
            safe_path(name)
            if fs.file_flags(i) & lt.file_storage.flag_symlink:
                raise ValueError("symlink_not_allowed")
            files.append({"index": i, "path": name, "size": fs.file_size(i)})
        return {
            "name": ti.name(),
            "total_bytes": sum(f["size"] for f in files),
            "piece_length": ti.piece_length(),
            "files": files,
        }

    def storage(self):
        disk = shutil.disk_usage(self.root)
        used = allocated(self.root)
        with self.io_lock:
            for key, entry in self.readers.items():
                try:
                    stat = entry["path"].stat()
                    same = (stat.st_dev, stat.st_ino) == key
                except FileNotFoundError:
                    same = False
                if not same:
                    used += entry["bytes"]
        reserved = self.ledger.remaining()
        cap = min(MAX_WORKSPACE_BYTES, max(0, disk.free + used - SAFETY_BYTES))
        return dict(
            capacity_bytes=cap,
            used_bytes=used,
            free_bytes=max(0, min(cap - used, disk.free - SAFETY_BYTES) - reserved),
            reserved_bytes=reserved,
            disk_free_bytes=disk.free,
        )

    def tick(self):
        config_path = self.root.parent / "server-settings.json"
        config = (
            json.loads(config_path.read_text())
            if config_path.exists()
            else {"auto_drive": True, "auto_delete": True}
        )
        if self.batch:
            b = self.batch
            h = b["handle"]
            row = self.db.execute(
                "select state from tasks where id=?", (b["id"],)
            ).fetchone()
            if row and row["state"] == "cancel_requested":
                if h.is_valid():
                    h.pause()
                    self.session.remove_torrent(h)
                deadline = time.monotonic() + 10
                while h.is_valid() and time.monotonic() < deadline:
                    time.sleep(0.05)
                if h.is_valid():
                    raise RuntimeError("handle_removal_timeout")
                self.discard_cache(b["id"])
                self.db.execute(
                    "delete from files where task_id=? and drive_id is null", (b["id"],)
                )
                self.db.execute("delete from tasks where id=?", (b["id"],))
                self.db.commit()
                self.ledger.drop(b["id"])
                self.batch = None
                return
            if not row or row["state"] in ("paused", "error"):
                if h.is_valid():
                    h.pause()
                return
            if not h.is_valid():
                self.batch = None
                self.phase = None
                return
            if shutil.disk_usage(self.root).free < SAFETY_BYTES // 2:
                h.pause()
                raise RuntimeError("disk_safety_reserve")
            if row["state"] == "queued" and hasattr(h, "clear_error"):
                h.clear_error()
            h.resume()
            s = h.status()
            progress = h.file_progress()
            done_all = sum(progress[f["index"]] for f in b["files"])
            committed = {
                r[0]
                for r in self.db.execute(
                    "select file_index from files where task_id=? and drive_id is not null",
                    (b["id"],),
                )
            }
            done = sum(
                progress[f["index"]] for f in b["files"] if f["index"] not in committed
            )
            uploaded = self.db.execute(
                "select coalesce(sum(size),0) from files where task_id=? and drive_id is not null",
                (b["id"],),
            ).fetchone()[0]
            total = self.db.execute(
                "select total_bytes from tasks where id=?", (b["id"],)
            ).fetchone()[0]
            self.phase = {
                "task_id": b["id"],
                "phase_progress": None,
                "eta_seconds": int(
                    max(0, sum(f["size"] for f in b["files"]) - done_all)
                    / s.download_rate
                )
                if s.download_rate
                else None,
            }
            self.db.execute(
                "update tasks set speed=?,progress=? where id=?",
                (s.download_rate, min(1, (uploaded + done) / max(1, total)), b["id"]),
            )
            self.db.commit()
            if s.errc.value():
                raise RuntimeError(s.errc.message())
            if not all(progress[f["index"]] >= f["size"] for f in b["files"]):
                return
            h.pause()
            h.flush_cache()
            deadline = time.monotonic() + 30
            flushed = False
            while time.monotonic() < deadline:
                self.session.wait_for_alert(200)
                if any(
                    isinstance(a, lt.cache_flushed_alert) and a.handle == h
                    for a in self.session.pop_alerts()
                ):
                    flushed = True
                    break
            if not flushed:
                raise RuntimeError("disk_flush_timeout")
            self.db.execute(
                "update tasks set state='uploading',speed=0 where id=? and state not in ('paused','cancel_requested','error')",
                (b["id"],),
            )
            for f in b["files"]:
                self.db.execute(
                    "update files set state='uploading' where task_id=? and file_index=? and drive_id is null",
                    (b["id"], f["index"]),
                )
            self.db.commit()
            for f in b["files"]:
                rec = self.db.execute(
                    "select * from files where task_id=? and file_index=?",
                    (b["id"], f["index"]),
                ).fetchone()
                if rec["drive_id"]:
                    continue
                path = b["dir"] / safe_path(f["path"])
                if path.stat().st_size != f["size"]:
                    raise RuntimeError("size_mismatch")
                baseline = [None, None, None]

                def on_progress(offset, total, stage):
                    current = self.db.execute(
                        "select state from tasks where id=?", (b["id"],)
                    ).fetchone()
                    if not current or current["state"] in (
                        "paused",
                        "cancel_requested",
                        "error",
                    ):
                        raise UploadDeferred()
                    now = time.monotonic()
                    if baseline[0] != stage:
                        baseline[:] = [stage, offset, now]
                    speed = (
                        int(
                            max(0, offset - baseline[1]) / max(0.001, now - baseline[2])
                        )
                        if stage == "uploading"
                        else 0
                    )
                    eta = int(max(0, total - offset) / speed) if speed else None
                    self.phase = {
                        "task_id": b["id"],
                        "phase_progress": offset / max(1, total),
                        "phase_completed_bytes": offset,
                        "phase_total_bytes": total,
                        "phase_file": f["path"],
                        "eta_seconds": eta,
                    }
                    self.db.execute(
                        "update tasks set state=?,speed=? where id=?",
                        (stage, speed, b["id"]),
                    )
                    self.db.commit()

                result = self.drive.upload(
                    path, f["path"], on_progress, b["id"] + ":" + str(f["index"])
                )
                self.db.execute(
                    "update files set drive_id=?,state='ready' where id=?",
                    (result["id"], rec["id"]),
                )
                self.db.commit()
            # handle removal must finish before deleting shared pieces or partfile.
            self.session.remove_torrent(h)
            until = time.monotonic() + 10
            while h.is_valid() and time.monotonic() < until:
                time.sleep(0.05)
            if h.is_valid():
                raise RuntimeError("handle_removal_timeout")
            current = self.db.execute(
                "select state from tasks where id=?", (b["id"],)
            ).fetchone()
            cancelled = current and current["state"] == "cancel_requested"
            if config.get("auto_delete", True) or cancelled:
                self.discard_cache(b["id"])
            self.ledger.drop(b["id"])
            self.batch = None
            self.phase = None
            if cancelled:
                self.db.execute(
                    "delete from files where task_id=? and drive_id is null", (b["id"],)
                )
                self.db.execute("delete from tasks where id=?", (b["id"],))
                self.db.commit()
                return
            self.db.execute(
                "update tasks set state=case when state='paused' then 'paused' else 'queued' end,speed=0 where id=?",
                (b["id"],),
            )
            self.db.commit()
            return
        if not self.drive.configured or not config.get("auto_drive", True):
            return
        row = self.db.execute(
            "select * from tasks where state in ('queued','downloading','uploading','checking') order by created limit 1"
        ).fetchone()
        if not row:
            return
        pending = [
            dict(f)
            for f in self.db.execute(
                'select file_index as "index",path,size from files where task_id=? and drive_id is null',
                (row["id"],),
            )
        ]
        if not pending:
            if config.get("auto_delete", True):
                self.discard_cache(row["id"])
            self.ledger.drop(row["id"])
            self.db.execute(
                "update tasks set state='ready',progress=1,speed=0 where id=?",
                (row["id"],),
            )
            self.db.commit()
            return
        ti = lt.torrent_info(bytes(row["torrent"]))
        directory = self.root / row["id"]
        record = self.ledger.load(row["id"])
        if record:
            all_files = [
                dict(f)
                for f in self.db.execute(
                    'select file_index as "index",path,size,drive_id from files where task_id=?',
                    (row["id"],),
                )
            ]
            batch = [f for f in all_files if f["index"] in record["indices"]]
            if batch and all(f["drive_id"] for f in batch):
                if config.get("auto_delete", True):
                    self.discard_cache(row["id"])
                self.ledger.drop(row["id"])
                return
            reserved = record["reserved"]
        else:
            # Legacy caches are retained too; reuse only files already present, never credit
            # confirmed files toward a new, larger batch that would oversubscribe storage.
            cached = [
                f for f in pending if (directory / safe_path(f["path"])).is_file()
            ]
            candidates = cached or pending
            credit = sum(allocated(directory / safe_path(f["path"])) for f in cached)
            batch, reserved = choose_batch(
                candidates,
                ti.piece_length(),
                max(0, self.storage()["free_bytes"] - 1024**2) + credit,
                block_size=os.statvfs(self.root).f_frsize or 4096,
                overhead_bytes=8 * 1024**2,
            )
            if not batch:
                if any(
                    f["size"] + 2 * ti.piece_length() > self.storage()["capacity_bytes"]
                    for f in pending
                ):
                    self.db.execute(
                        "update tasks set state='error',error='workspace_or_single_file_limit',speed=0 where id=?",
                        (row["id"],),
                    )
                    self.db.commit()
                return
            baseline = (
                max(0, allocated(directory) - credit) if directory.exists() else 0
            )
            self.ledger.save(row["id"], [f["index"] for f in batch], reserved, baseline)
        if not batch:
            raise RuntimeError("batch_manifest_has_no_files")
        budget = self.storage()
        if budget["used_bytes"] + budget["reserved_bytes"] > budget["capacity_bytes"]:
            self.db.execute(
                "update tasks set state='error',error='workspace_capacity_changed',speed=0 where id=?",
                (row["id"],),
            )
            self.db.commit()
            return
        directory.mkdir(exist_ok=True)
        p = lt.add_torrent_params()
        p.ti = ti
        p.save_path = str(directory)
        p.trackers = []
        p.url_seeds = []
        p.http_seeds = []
        priorities = [0] * ti.num_files()
        for f in batch:
            priorities[f["index"]] = 4
        p.file_priorities = priorities
        p.flags &= ~lt.torrent_flags.auto_managed
        p.flags |= (
            lt.torrent_flags.override_trackers | lt.torrent_flags.override_web_seeds
        )
        h = self.session.add_torrent(p)
        h.resume()
        self.phase = None
        self.batch = dict(
            id=row["id"], handle=h, files=batch, reserved=reserved, dir=directory
        )
        self.db.execute(
            "update tasks set state='downloading',error=null where id=?", (row["id"],)
        )
        for f in batch:
            self.db.execute(
                "update files set state='downloading' where task_id=? and file_index=?",
                (row["id"], f["index"]),
            )
        self.db.commit()
