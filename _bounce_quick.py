import pathlib, re, subprocess, time, os, sys, urllib.request
root = pathlib.Path(r"C:/ALICE_BOX/my-pocket-things/pocket-go")
ps = subprocess.run(["powershell","-NoProfile","-Command","Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'server.py' } | ForEach-Object { $_.ProcessId.ToString() }"], capture_output=True, text=True, encoding="utf-8", errors="replace")
pids=[x.strip() for x in (ps.stdout or "").splitlines() if x.strip().isdigit()]
for pid in pids:
  subprocess.run(["taskkill","/PID",pid,"/F"], capture_output=True)
  print("killed", pid)
time.sleep(1)
env=os.environ.copy(); env["GO_HOST"]="0.0.0.0"; env["PYTHONIOENCODING"]="utf-8"
log=root/"prod"/"www_sys"/"_bounce-seal-zoom.log"
with open(log,"w",encoding="utf-8") as lf:
  subprocess.Popen([sys.executable, str(root/"prod"/"www_sys"/"server.py")], cwd=str(root/"prod"/"www_sys"), stdout=lf, stderr=subprocess.STDOUT, env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS)
time.sleep(2)
page=urllib.request.urlopen("http://127.0.0.1:43210/",timeout=6).read().decode("utf-8","replace")
print("css v", "librarian.css?v=20260915140100" in page)
css=urllib.request.urlopen("http://127.0.0.1:43210/librarian.css?v=20260915140100",timeout=6).read().decode("utf-8","replace")
print("cover", "object-fit: cover" in css)
print("DONE")
