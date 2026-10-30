"""Real Android 14 checks. Never substitutes browser renders for Android screenshots."""

import subprocess, time, json, xml.etree.ElementTree as ET, re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
adb = "/workspace/android-sdk/platform-tools/adb"
serial = "emulator-5556"


def call(*args, timeout=15, binary=False):
    r = subprocess.run([adb, "-s", serial, *args], capture_output=True, timeout=timeout)
    return (
        r
        if binary
        else (
            r.returncode,
            r.stdout.decode(errors="replace") + r.stderr.decode(errors="replace"),
        )
    )


result = {"android_14_install": False, "launch": False, "screens": []}
try:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            code, out = call("shell", "getprop", "sys.boot_completed", timeout=15)
            if out.strip() == "1":
                break
        except subprocess.TimeoutExpired:
            pass
        time.sleep(2)
    else:
        raise RuntimeError("boot_not_complete_within_check_window")
    code, out = call(
        "install",
        "-r",
        str(root / "artifacts/Cloud-Torrent-Client-debug.apk"),
        timeout=180,
    )
    (root / "artifacts/android-install-final.log").write_text(out)
    if code or "Success" not in out:
        raise RuntimeError("install_failed")
    result["android_14_install"] = True
    call("shell", "input", "keyevent", "82")
    code, out = call(
        "shell",
        "am",
        "start",
        "-W",
        "-n",
        "com.cloudtorrent.client/.MainActivity",
        timeout=60,
    )
    (root / "artifacts/android-launch.log").write_text(out)
    if code:
        raise RuntimeError("launch_failed")
    time.sleep(3)
    code, out = call("shell", "pidof", "com.cloudtorrent.client")
    if code or not out.strip():
        raise RuntimeError("process_not_running")
    result["launch"] = True

    def screenshot(name):
        r = call("exec-out", "screencap", "-p", timeout=30, binary=True)
        if r.returncode or not r.stdout.startswith(b"\x89PNG"):
            raise RuntimeError("screenshot_failed")
        (root / f"artifacts/android-{name}.png").write_bytes(r.stdout)
        result["screens"].append(name)

    screenshot("downloads")
    for name, label in [
        ("files", "Файлы"),
        ("cloud", "Облако"),
        ("settings", "Настройки"),
    ]:
        call("shell", "uiautomator", "dump", "/sdcard/window.xml", timeout=40)
        code, xml = call("shell", "cat", "/sdcard/window.xml")
        tree = ET.fromstring(xml)
        nodes = [n for n in tree.iter() if n.attrib.get("text") == label]
        if not nodes:
            raise RuntimeError("navigation_node_missing_" + name)
        node = nodes[-1]
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.attrib["bounds"]))
        call("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
        time.sleep(1)
        screenshot(name)
except Exception as e:
    result["failure"] = str(e)
finally:
    (root / "artifacts/android-run.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
