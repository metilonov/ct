import asyncio, json, re, hashlib
from pathlib import Path
from playwright.async_api import async_playwright

r = Path(__file__).resolve().parents[1]
source = (r / "reference/Cloud_Torrent_Client.html").read_text()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium", args=["--no-sandbox"]
        )
        page = await browser.new_page(viewport={"width": 430, "height": 900})
        await page.set_content(source)
        inventory = await page.evaluate(
            """()=>Array.from(document.querySelectorAll('.app *')).map((e,i)=>({index:i,tag:e.tagName,id:e.id,classes:e.getAttribute('class'),attributes:Array.from(e.attributes).reduce((a,x)=>(a[x.name]=x.value,a),{}),text:e.childElementCount?null:e.textContent}))"""
        )
        (r / "docs/full-dom-inventory.json").write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2)
        )
        layouts = {}
        for tab in ["downloads", "files", "cloud", "settings"]:
            await page.evaluate("(t)=>tab(t)", tab)
            layouts[tab] = await page.evaluate(
                """()=>Array.from(document.querySelectorAll('.app, .top, h1, nav, .view.on, .view.on *')).map(e=>{let s=getComputedStyle(e),b=e.getBoundingClientRect();return {tag:e.tagName,id:e.id,classes:e.className,box:{x:b.x,y:b.y,width:b.width,height:b.height},style:Object.fromEntries(['color','backgroundColor','borderRadius','fontFamily','fontSize','fontWeight','lineHeight','padding','margin','gap','display'].map(k=>[k,s[k]]))}})"""
            )
        (r / "docs/reference-layouts.json").write_text(
            json.dumps(layouts, ensure_ascii=False, indent=2)
        )
        await browser.close()
    handlers = re.findall(
        r".{0,60}(?:\.onclick|\.onchange|addEventListener|setInterval|setTimeout|MutationObserver).{0,160}",
        source,
    )
    functions = re.findall(r"function\s+(\w+)\s*\(", source)
    (r / "docs/javascript-inventory.json").write_text(
        json.dumps(
            {
                "functions": functions,
                "bindings": handlers,
                "sha256": hashlib.sha256(source.encode()).hexdigest(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


asyncio.run(main())
