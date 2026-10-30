"""Losslessly recompress APK entries before alignment and signing with the same debug key.

No assets or DEX contents change. Keeps the attachment under the connector body limit.
The original Gradle APK stays in app/build/outputs/apk/debug/.
"""
from pathlib import Path
import os, subprocess, tempfile, zipfile, hashlib, json
R=Path(__file__).resolve().parents[1]
sdk=Path(os.environ.get('ANDROID_SDK_ROOT','/workspace/android-sdk'))
build_tools=sdk/'build-tools/36.0.0'
original=R/'android/app/build/outputs/apk/debug/app-debug.apk'
out=R/'artifacts/Cloud-Torrent-Client-debug.apk'
key=Path.home()/'.android/debug.keystore'
assert key.is_file(), 'No configured debug keystore; run Gradle first'
with tempfile.TemporaryDirectory() as tmp:
 tmp=Path(tmp)
 unsigned=tmp/'unsigned.apk'
 with zipfile.ZipFile(original) as src,zipfile.ZipFile(unsigned,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as dst:
  for entry in src.infolist():
   dst.writestr(entry,src.read(entry.filename),compress_type=entry.compress_type,compresslevel=9)
 subprocess.run([str(build_tools/'zipalign'),'-f','4',str(unsigned),str(tmp/'aligned.apk')],check=True)
 subprocess.run([str(build_tools/'apksigner'),'sign','--ks',str(key),'--v1-signing-enabled','false','--v4-signing-enabled','false','--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android','--out',str(out),str(tmp/'aligned.apk')],check=True)
 with zipfile.ZipFile(original) as before,zipfile.ZipFile(out) as after:
  assert set(before.namelist())==set(after.namelist())
  assert all(before.read(n)==after.read(n) for n in before.namelist())
 subprocess.run([str(build_tools/'apksigner'),'verify',str(out)],check=True)
 (R/'artifacts/redesign/apk-content-verification.json').write_text(json.dumps({'passed':True,'all_zip_entry_contents_unchanged':True,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bytes':out.stat().st_size},indent=2))
 print('Verified signed debug APK:',out.stat().st_size,'bytes')
