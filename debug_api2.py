import subprocess, time, requests, sys, os

# 启动 uvicorn（无 reload）
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8002", "--no-access-log"],
    cwd=r"D:\PrismaMate专用文件夹\prismamate-backend",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
)

try:
    time.sleep(3)
    # login
    r = requests.post("http://127.0.0.1:8002/api/v1/auth/login", json={"username":"admin","password":"admin123"})
    print("login:", r.status_code)
    token = r.json().get("access_token", "")
    
    # get reports
    r2 = requests.get("http://127.0.0.1:8002/api/v1/reports?skip=0&limit=50", headers={"Authorization":"Bearer "+token})
    print("reports:", r2.status_code)
    print(r2.text[:500])
    
    # get me
    r3 = requests.get("http://127.0.0.1:8002/api/v1/auth/me", headers={"Authorization":"Bearer "+token})
    print("me:", r3.status_code)
    print(r3.text[:300])
    
finally:
    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=5)
        print("\n--- SERVER OUTPUT ---")
        print(out[-3000:] if len(out) > 3000 else out)
    except:
        proc.kill()
