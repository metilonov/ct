from PIL import Image
from pathlib import Path
import re, json

r = Path(__file__).resolve().parents[1]
res = r / "android/app/src/main/res"
im = Image.open(r / "reference/logo.jpg").convert("RGB")
for density, size in [
    ("mdpi", 48),
    ("hdpi", 72),
    ("xhdpi", 96),
    ("xxhdpi", 144),
    ("xxxhdpi", 192),
]:
    d = res / ("mipmap-" + density)
    d.mkdir(parents=True, exist_ok=True)
    im.resize((size, size), Image.Resampling.LANCZOS).save(d / "ic_launcher.png")
d = res / "drawable"
d.mkdir(exist_ok=True)
# Original opaque JPEG retained, scaled inside adaptive safe area; no artificial transparency.
canvas = Image.new("RGB", (432, 432), (7, 11, 19))
canvas.paste(im.resize((288, 288), Image.Resampling.LANCZOS), (72, 72))
canvas.save(d / "ic_foreground.png")
d = res / "mipmap-anydpi-v26"
d.mkdir(exist_ok=True)
(d / "ic_launcher.xml").write_text(
    '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android"><background android:drawable="@color/icon_background"/><foreground android:drawable="@drawable/ic_foreground"/></adaptive-icon>'
)
d = res / "values"
d.mkdir(exist_ok=True)
(d / "colors.xml").write_text(
    '<resources><color name="icon_background">#070b13</color></resources>'
)
src = (r / "reference/Cloud_Torrent_Client.html").read_text()
svgs = re.findall(r"<svg\b[^>]*>.*?</svg>", src, re.S)
assets = r / "android/app/src/main/assets"
assets.mkdir(exist_ok=True)
for i, s in enumerate(svgs):
    s = re.sub(' style="[^"]*"', "", s)
    s = s.replace(
        "<svg",
        '<svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="#6cb0ff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"',
        1,
    )
    (assets / f"icon{i}.svg").write_text(s)
(r / "docs/svg-inventory.json").write_text(
    json.dumps(dict(enumerate(svgs)), ensure_ascii=False, indent=2)
)
