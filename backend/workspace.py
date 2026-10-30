"""Durable reservations and batch membership; no torrent payload is deleted here."""

import json, os, re
from pathlib import Path


def allocated(path):
    path = Path(path)
    total = 0
    for p in [path, *path.rglob("*")]:
        try:
            total += p.stat().st_blocks * 512
        except FileNotFoundError:
            pass
    return total


class BatchLedger:
    def __init__(self, workspace):
        self.workspace = Path(workspace)
        self.root = self.workspace.parent / "batches"
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, tid):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", tid):
            raise ValueError("invalid_task_id")
        return self.root / (tid + ".json")

    def load(self, tid):
        p = self.path(tid)
        return json.loads(p.read_text()) if p.exists() else None

    def save(self, tid, indices, reserved, baseline):
        p = self.path(tid)
        temp = p.with_suffix(".tmp")
        payload = json.dumps(
            {
                "task_id": tid,
                "indices": indices,
                "reserved": reserved,
                "baseline": baseline,
            }
        ).encode()
        with temp.open("wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        temp.chmod(0o600)
        temp.replace(p)
        fd = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def drop(self, tid):
        self.path(tid).unlink(missing_ok=True)

    def remaining(self):
        result = 0
        for p in self.root.glob("*.json"):
            data = json.loads(p.read_text())
            used = max(
                0, allocated(self.workspace / data["task_id"]) - data["baseline"]
            )
            result += max(0, data["reserved"] - used)
        return result
