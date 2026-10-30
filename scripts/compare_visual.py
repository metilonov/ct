"""Compare genuine Android screenshots with HTML using matching disconnected empty data."""

import asyncio, json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from playwright.async_api import async_playwright

root = Path(__file__).resolve().parents[1]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium", args=["--no-sandbox"]
        )
        page = await browser.new_page(viewport={"width": 430, "height": 900})
        await page.set_content(
            (root / "reference/Cloud_Torrent_Client.html").read_text()
        )
        import base64

        font = root / "reference/Roboto-Regular.ttf"
        if font.exists():
            encoded = base64.b64encode(font.read_bytes()).decode()
            await page.add_style_tag(
                content="@font-face{font-family:Roboto;src:url(data:font/ttf;base64,"
                + encoded
                + ") format('truetype');font-weight:100 900;font-style:normal;}"
            )
            await page.evaluate("document.fonts.ready")
        await page.evaluate(
            """()=>{dls=[];fStatic=[];gc=false;render();document.querySelector('.note').textContent='Укажите HTTPS-адрес BotHost';document.querySelector('#gcRow .l').lastChild.textContent='BotHost';document.querySelector('#gcApiSub').textContent='Не подключён';}"""
        )
        results = {}
        for tab in ["downloads", "files", "cloud", "settings"]:
            await page.evaluate("(t)=>tab(t)", tab)
            await page.screenshot(
                path=str(root / f"artifacts/reference-empty-{tab}.png")
            )
            target = root / f"artifacts/android-{tab}.png"
            if not target.exists():
                continue
            android = Image.open(target).convert("RGB")
            ref = Image.open(root / f"artifacts/reference-empty-{tab}.png").convert(
                "RGB"
            )

            # Both app shells are centered, capped at 860px. Remove only extra device height, never warp.
            def app_bounds(im):
                pixels = im.load()
                points = [
                    (x, y)
                    for y in range(im.height)
                    for x in range(im.width)
                    if pixels[x, y] == (16, 20, 27)
                ]
                return (
                    min(x for x, y in points),
                    min(y for x, y in points),
                    max(x for x, y in points) + 1,
                    max(y for x, y in points) + 1,
                )

            ab = app_bounds(android)
            rb = app_bounds(ref)
            normalized = android.crop(ab)
            reference = ref.crop(rb)
            if normalized.size != reference.size:
                continue
            delta = ImageChops.difference(normalized, reference)
            canvas = Image.new(
                "RGB", (normalized.width * 3, normalized.height), "white"
            )
            canvas.paste(reference, (0, 0))
            canvas.paste(normalized, (normalized.width, 0))
            canvas.paste(delta, (normalized.width * 2, 0))
            canvas.save(root / f"artifacts/compare-{tab}.png")
            top = ab[1]
            stat = ImageStat.Stat(delta)
            results[tab] = {
                "mean_absolute_rgb_error": sum(stat.mean) / 3,
                "interpretation": "Includes intentional live-data and BotHost label differences; not a 1:1 acceptance metric",
                "android_crop_top": top,
            }
        (root / "artifacts/visual-comparison.json").write_text(
            json.dumps(results, indent=2)
        )
        await browser.close()


asyncio.run(main())
