from pathlib import Path
import zipfile, hashlib, json

root = Path(__file__).resolve().parents[1]
target = root / "artifacts/Cloud-Torrent-Client-project.zip"
ignore = {
    ".gradle",
    "build",
    "data",
    ".pytest_cache",
    "__pycache__",
    ".git",
    "{assets,",
}
# Include source and verification artifacts; APK is also provided separately.
with zipfile.ZipFile(
    target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
) as z:
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or any(part in ignore for part in rel.parts):
            continue
        if (
            path == target
            or path.suffix in {".zip", ".jks", ".keystore"}
            or path.name in {"local.properties", ".env", "SHA256SUMS"}
        ):
            continue
        z.write(path, Path("Cloud-Torrent-Client") / rel)
files = [root / "artifacts/Cloud-Torrent-Client-debug.apk", target]
(root / "artifacts/SHA256SUMS").write_text(
    "\n".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name for p in files)
    + "\n"
)
print(json.dumps({p.name: p.stat().st_size for p in files}, indent=2))
