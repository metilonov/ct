"""Capture the supplied v2 HTML itself, including all sheets, at Android content bounds."""
import asyncio, base64, json
from pathlib import Path
from playwright.async_api import async_playwright
R=Path(__file__).resolve().parents[1]
OUT=R/'artifacts/redesign';OUT.mkdir(exist_ok=True)
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  page=await browser.new_page(viewport={'width':430,'height':912},device_scale_factor=1)
  await page.evaluate('window.setInterval=()=>0')
  await page.set_content((R/'reference/Cloud_Torrent_Client.html').read_text())
  encoded=base64.b64encode((R/'reference/Roboto-Regular.ttf').read_bytes()).decode()
  await page.add_style_tag(content="@font-face{font-family:Roboto;src:url(data:font/ttf;base64,"+encoded+") format('truetype');font-weight:100 900;font-style:normal;}")
  await page.evaluate('document.fonts.ready')
  layouts={}
  async def snap(name):
   await page.wait_for_timeout(900)
   await page.screenshot(path=str(OUT/f'html-{name}.png'))
   layouts[name]=await page.evaluate('''()=>[...document.querySelectorAll('.app,.top,h1,nav,nav button,.view.on,.view.on .row-btn,.view.on .grp,.stats,.stat,.cloud-row,.sec,.add,.fsum,.fsearch,.chips,.modal.on .sheet,.modal.on .plan')].map(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {tag:e.tagName,id:e.id,cls:e.className,text:e.textContent.slice(0,100),x:r.x,y:r.y,width:r.width,height:r.height,font:s.fontSize,lineHeight:s.lineHeight,color:s.color,background:s.backgroundColor,padding:s.padding,gap:s.gap}})''')
  for tab in ['downloads','files','cloud','settings']:
   await page.evaluate('(t)=>tab(t)',tab);await snap(tab)
  await page.evaluate("tab('settings');openPlans(true)");await snap('plans')
  await page.evaluate("openPlans(false);tab('downloads');open(true)");await snap('add')
  await page.evaluate("step('link')");await snap('link')
  await page.evaluate("open(false);openGc(true)");await snap('connect')
  await page.evaluate("openGc(false);cur=0;renderDetail();tab('detail')");await snap('detail')
  await page.evaluate("tab('files');openFile(allFiles()[0])") if False else None
  # Compare native offline state with matching data; the reference file itself is untouched.
  await page.evaluate("tab('downloads');dls=[];fStatic=[];gc=false;render();renderFiles();setGc(true);document.querySelectorAll('.modal').forEach(e=>e.classList.remove('on'));document.querySelector('#gcRow .l').lastChild.textContent='BotHost';document.querySelector('.note').textContent='Укажите HTTPS-адрес BotHost';document.querySelector('#gcToggle span').firstChild.textContent='BotHost';document.querySelector('#gcApiSub').textContent='Не подключён';document.querySelector('#v-settings .grp:nth-of-type(2)').textContent='BotHost'")
  for tab in ['downloads','files','cloud','settings']:
   await page.evaluate('(t)=>tab(t)',tab)
   await snap('offline-'+tab)
  (OUT/'html-layouts.json').write_text(json.dumps(layouts,ensure_ascii=False,indent=2))
  inventory=await page.evaluate("""()=>[...document.querySelectorAll('*')].filter(e=>!(e.tagName==='STYLE'&&e.textContent.includes('data:font/ttf'))).map((e,i)=>({index:i,tag:e.tagName,id:e.id,cls:e.getAttribute('class'),parent:e.parentElement?.id||e.parentElement?.tagName,text:e.children.length?null:e.textContent}))""")
  (OUT/'full-dom-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2))
  await browser.close()
asyncio.run(main())
