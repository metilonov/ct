"""Capture real device frames only. Never substitutes HTML for a native screenshot."""
import subprocess,time,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];out=R/'artifacts/redesign'
adb=['/workspace/android-sdk/platform-tools/adb','-s','emulator-5556']
def call(*args,timeout=30):
 return subprocess.run(adb+list(args),capture_output=True,timeout=timeout)
def tap(x,y):
 call('shell','input','tap',str(x),str(y));time.sleep(5)
def shot(name):
 r=call('exec-out','screencap','-p',timeout=60)
 if not r.stdout.startswith(b'\x89PNG'):raise RuntimeError('No native PNG: '+name)
 (out/f'android-{name}.png').write_bytes(r.stdout)
 print('Captured '+name,flush=True)
end=time.monotonic()+600
while time.monotonic()<end:
 try:
  r=call('shell','getprop','sys.boot_completed',timeout=8)
  if r.stdout.strip()==b'1':break
 except subprocess.TimeoutExpired:pass
 time.sleep(5)
else:raise RuntimeError('Android boot did not complete')
for args in [('shell','settings','put','global','bluetooth_on','0'),('shell','svc','bluetooth','disable'),('shell','settings','put','global','hide_error_dialogs','1')]:
 try:call(*args,timeout=12)
 except subprocess.TimeoutExpired:pass
r=call('install','-r',str(R/'android/app/build/outputs/apk/debug/app-debug.apk'),timeout=180)
(out/'install.log').write_text(r.stdout.decode(errors='replace')+r.stderr.decode(errors='replace'))
assert r.returncode==0,'Install failed'
call('shell','input','keyevent','82')
r=call('shell','am','start','-W','-n','com.cloudtorrent.client/.MainActivity',timeout=120)
(out/'launch.log').write_text(r.stdout.decode(errors='replace')+r.stderr.decode(errors='replace'))
time.sleep(20)
shot('downloads')
for name,x in [('files',165),('cloud',265),('settings',360)]:
 tap(x,900);shot(name)
tap(200,180);shot('plans')
# Dismiss the plan sheet by tapping above it, then go back to downloads.
tap(200,400);tap(70,900);tap(200,810);shot('add')
# In the add sheet: its two choices are centered at 715 and 805 on this device.
tap(200,800);shot('link')
call('shell','input','keyevent','4');time.sleep(2)
tap(200,400);tap(360,900)
call('shell','input','swipe','200','790','200','300','500');time.sleep(3);shot('settings-bottom')
(out/'android-capture.json').write_text(json.dumps({'install':True,'screens':[p.stem for p in out.glob('android-*.png')],'scope':'Real Android 14 software emulator frames; every frame must be inspected before acceptance'},indent=2))
