"""B 角色自检 runner：起服务 -> 等健康 -> 跑 pytest -> 停服务。

一次 shell 调用内完成全流程（避免跨调用子进程被杀）。
用法（仓库根目录）：
    python tools/run_tests.py
退出码：0=全过，1=有失败。
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 选含 uvicorn 的 python
CANDIDATES = [
    os.environ.get("QBC_PYTHON", ""),
    r"C:\Users\26293\AppData\Local\Programs\Python\Python313\python.exe",
    r"C:\Users\26293\AppData\Local\Programs\Python\Python311\python.exe",
    "python",
]


def pick_python() -> str:
    for c in CANDIDATES:
        if not c:
            continue
        try:
            r = subprocess.run([c, "-c", "import uvicorn"],
                               capture_output=True, timeout=15)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return sys.executable


def wait_health(url: str, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main() -> int:
    py = pick_python()
    print(f"[runner] python = {py}", flush=True)

    procs = []
    try:
        s1 = subprocess.Popen([py, "-m", "uvicorn", "services.solver.main:app",
                               "--host", "127.0.0.1", "--port", "8081"],
                              cwd=REPO, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,
                              creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        s2 = subprocess.Popen([py, "-m", "uvicorn", "services.oracle.main:app",
                               "--host", "127.0.0.1", "--port", "8082"],
                              cwd=REPO, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,
                              creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        procs.extend([s1, s2])

        ok1 = wait_health("http://127.0.0.1:8081/health")
        ok2 = wait_health("http://127.0.0.1:8082/health")
        print(f"[runner] solver ready={ok1} oracle ready={ok2}", flush=True)
        if not (ok1 and ok2):
            print("[runner] ERROR: service not ready, abort", flush=True)
            return 1

        # 跑 pytest（用同一 python，保证依赖一致）
        r = subprocess.run([py, "-m", "pytest", "tests/", "-v"],
                           cwd=REPO, timeout=300)
        print(f"[runner] pytest exit={r.returncode}", flush=True)
        return 0 if r.returncode == 0 else 1
    finally:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        # 兜底杀端口
        time.sleep(1)
        for p in procs:
            try:
                if p.poll() is None:
                    p.kill()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
