import re, json, pathlib, asyncio
from playwright.async_api import async_playwright

R = pathlib.Path(__file__).resolve().parents[1]
src = (R / "reference/Cloud_Torrent_Client.html").read_text()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium", args=["--no-sandbox"]
        )
        page = await browser.new_page(
            viewport={"width": 430, "height": 900}, device_scale_factor=1
        )
        await page.set_content(src)
        inventory = await page.evaluate(
            """()=>Array.from(document.querySelectorAll('[id]')).map(e=>({id:e.id,tag:e.tagName,classes:e.className,text:e.textContent.trim().slice(0,200)}))"""
        )
        (R / "docs/html-inventory.json").write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2)
        )
        for tab in ["downloads", "files", "cloud", "settings"]:
            await page.evaluate("(t)=>tab(t)", tab)
            await page.screenshot(path=str(R / f"artifacts/reference-{tab}.png"))
        for modal in ["modal", "gcModal", "planModal"]:
            await page.evaluate(
                '(id)=>document.getElementById(id).classList.add("on")', modal
            )
            await page.screenshot(path=str(R / f"artifacts/reference-{modal}.png"))
            await page.evaluate(
                '(id)=>document.getElementById(id).classList.remove("on")', modal
            )
        await page.evaluate('()=>{cur=0;renderDetail();tab("detail")}')
        await page.screenshot(path=str(R / "artifacts/reference-detail.png"))
        await page.evaluate('()=>openFile("s1")')
        await page.screenshot(path=str(R / "artifacts/reference-file.png"))
        await browser.close()
    variables = dict(re.findall(r"(--[\w-]+):([^;}]+)", src))
    (R / "docs/css-tokens.json").write_text(json.dumps(variables, indent=2))
    lines = [
        "# Аудит HTML и карта переноса",
        "",
        "Исходник сохранён без изменений. Все id перечислены ниже; полная структура и тексты: html-inventory.json.",
        "",
        "| HTML id | Android Compose | Назначение/состояние |",
        "|---|---|---|",
    ]
    for e in inventory:
        target = (
            "DownloadsScreen"
            if e["id"] in ["dls", "stA", "stS", "count", "gcRow", "addBtn"]
            else "FilesScreen"
            if e["id"].startswith("f")
            else "CloudScreen"
            if e["id"]
            in [
                "quota",
                "qTxt",
                "qFree",
                "qPct",
                "qBar",
                "sync",
                "optAuto",
                "optDel",
                "limRow",
                "cleanCloud",
                "gcToggle",
                "gcSw",
                "gcSub",
            ]
            else "SettingsScreen"
            if e["tag"] == "BUTTON"
            or e["id"].startswith(("opt", "gcApi", "spd", "plan"))
            else "AppShell / Sheet / Detail"
        )
        lines.append(
            f"| `{e['id']}` ({e['tag']}, {e['classes']}) | {target} | {e['text'].replace('|', '/').replace(chr(10), ' ')[:95]} |"
        )
    lines += [
        "",
        "## Геометрия",
        "Внешний фон #000; body: 16px по горизонтали, 12px по вертикали; app: max 430×860px, радиус 26px, padding 32/20/14px. На viewport 430×900 app 398×860. Header 14px/29px; row 17px; torrent title 19px; muted #9aa3b2. Все CSS и SVG сохраняются в reference.",
        "",
        "## Поведение",
        "Навигация: downloads/files/cloud/settings + detail, Cloud/Android segmented control. Модальные: добавление (choice/link/file), API, тарифы, файл. Toast 1800ms, press scale .97/.98, bar transition 400ms, switch 200ms, toast 250ms, fs-bar grow 800ms с шагом 80ms, fade scroll 36px.",
        "",
        "## Замена демонстраций",
        "Math.random размеров и скоростей, setInterval роста прогресса, fStatic, 940ГБ базового расхода, 2ТБ ёмкости, копирование ссылки toast, ph=100 и plan=prem заменяются API/реальными локальными передачами. Подключение Google Cloud/Project ID/key заменяется BotHost HTTPS URL/администраторским API token. Drive требует отдельный OAuth.",
        "",
        "## Тарифы и конфликт требований",
        "HTML: Free 1 задача/20GB/без телефона; Premium 5/500GB/телефон, $4.99. Требование принимать 150GB+ независимо от размера конфликтует с Free 20GB. В backend размер метаданных не отклоняется; квота применяется к выбранным файлам при старте. Это явно возвращается ошибкой quota_exceeded.",
        "",
        "## Статус соответствия",
        "Карта — план соответствия, а не подтверждение реализации каждого id. Окончательная проверка требует Android screenshots, состояния с теми же данными и сравнения.",
    ]
    (R / "docs/HTML-AUDIT.md").write_text("\n".join(lines))


asyncio.run(main())
