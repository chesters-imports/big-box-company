# -*- coding: utf-8 -*-
import pathlib, shutil, time, re, subprocess, urllib.request, os, sys

root = pathlib.Path(r"C:/ALICE_BOX/my-pocket-things/pocket-go")
sp = root / "prod" / "www_sys" / "server.py"
ts = time.strftime("%Y%m%d-%H%M%S")
shutil.copy2(sp, sp.with_name("server.py.bak-cachebust-" + ts))
t = sp.read_text(encoding="utf-8")
new_v = "20260915135300"
t2, n_js = re.subn(r"(librarian\.js\?v=)\d+", r"\g<1>" + new_v, t)
t2, n_css = re.subn(r"(librarian\.css\?v=)\d+", r"\g<1>" + new_v, t2)
sp.write_text(t2, encoding="utf-8")
print("bumped js", n_js, "css", n_css, "to", new_v)

ps = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'server.py' } | ForEach-Object { $_.ProcessId.ToString() }"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
)
pids = [x.strip() for x in (ps.stdout or "").splitlines() if x.strip().isdigit()]
print("pids", pids)
for pid in pids:
    subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
    print("killed", pid)
time.sleep(1.2)

env = os.environ.copy()
env["GO_HOST"] = "0.0.0.0"
env["PYTHONIOENCODING"] = "utf-8"
log = root / "prod" / "www_sys" / ("_bounce-" + ts + ".log")
cmd = [sys.executable, str(root / "prod" / "www_sys" / "server.py")]
with open(log, "w", encoding="utf-8") as lf:
    proc = subprocess.Popen(
        cmd,
        cwd=str(root / "prod" / "www_sys"),
        stdout=lf,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )
print("started", proc.pid, "log", log)
time.sleep(2.5)
try:
    page = urllib.request.urlopen("http://127.0.0.1:43210/", timeout=6).read().decode("utf-8", "replace")
    print("home ok", "librarian.js?v=" + new_v in page)
    j = urllib.request.urlopen("http://127.0.0.1:43210/librarian.js?v=" + new_v, timeout=6).read().decode("utf-8", "replace")
    print("seal in js", "librarian-seal" in j)
except Exception as e:
    print("smoke", e)
    print(log.read_text(encoding="utf-8", errors="replace")[-1200:])
print("DONE")
