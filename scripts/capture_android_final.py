import subprocess, time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
adb = ["/workspace/android-sdk/platform-tools/adb", "-s", "emulator-5556"]
for name, x in [("files", 170), ("cloud", 260), ("settings", 345)]:
    r = subprocess.run(
        adb + ["shell", "input", "tap", str(x), "900"], capture_output=True, timeout=15
    )
    time.sleep(10)
    r = subprocess.run(
        adb + ["exec-out", "screencap", "-p"], capture_output=True, timeout=40
    )
    if r.stdout.startswith(b"\x89PNG"):
        (root / f"artifacts/android-{name}-final-attempt.png").write_bytes(r.stdout)
        print(name, flush=True)
