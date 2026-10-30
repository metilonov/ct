import subprocess, time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
adb = ["/workspace/android-sdk/platform-tools/adb", "-s", "emulator-5556"]


def call(*args):
    return subprocess.run(adb + list(args), capture_output=True, timeout=40)


for name, x in [("files", 170), ("cloud", 260), ("settings", 345)]:
    call("shell", "input", "tap", str(x), "880")
    time.sleep(3)
    r = call("exec-out", "screencap", "-p")
    if r.stdout.startswith(b"\x89PNG"):
        (root / f"artifacts/android-{name}.png").write_bytes(r.stdout)
        print(name, flush=True)
call("shell", "input", "tap", "80", "880")
time.sleep(3)
r = call("exec-out", "screencap", "-p")
if r.stdout.startswith(b"\x89PNG"):
    (root / "artifacts/android-downloads.png").write_bytes(r.stdout)
