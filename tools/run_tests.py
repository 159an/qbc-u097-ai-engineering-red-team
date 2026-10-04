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

# 选含 uvicorn 的 python（不含任何写死的本机用户名/绝对路径；优先级：
#   1) 环境变量 QBC_PYTHON  2) PATH 上的 python/python3  3) 当前解释器 sys.executable
#   4) %LOCALAPPDATA%\Programs\Python\Python3*\python.exe 通配（本机常见默认安装位置）
# 保持与旧版一致的「按优先级 + 兜底」行为与输出格式（print(f"[runner] python = {py}")）。
import glob as _glob
import shutil as _shutil


def _candidate_pythons() -> list[str]:
    cands: list[str] = []
    qbc = os.environ.get("QBC_PYTHON", "")
    if qbc:
        cands.append(qbc)
    for name in ("python", "python3"):
        found = _shutil.which(name)
        if found:
            cands.append(found)
    cands.append(sys.executable)
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        pattern = os.path.join(localappdata, "Programs", "Python", "Python3*", "python.exe")
        cands.extend(sorted(_glob.glob(pattern), reverse=True))  # 版本高的优先
    seen: set[str] = set()
    out: list[str] = []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def pick_python() -> str:
    for c in _candidate_pythons():
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


def port_alive(host: str, port: int, timeout: float = 0.5) -> bool:
    """探测目标端口是否已有服务监听。避免反复起服务造成 EADDRINUSE / 空转。"""
    import socket
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def main() -> int:
    py = pick_python()
    print(f"[runner] python = {py}", flush=True)

    procs = []
    reused = []  # 记录复用了哪些端口（不自己起的）
    try:
        # 先探测端口是否已被占用（人类终端用 start-all.ps1 已起服务的情况）
        solver_alive = port_alive("127.0.0.1", 8081)
        oracle_alive = port_alive("127.0.0.1", 8082)
        print(f"[runner] port probe: solver(8081)={solver_alive} oracle(8082)={oracle_alive}", flush=True)

        if solver_alive and oracle_alive:
            print("[runner] both ports already alive -> reuse, skip spawn", flush=True)
        else:
            if not solver_alive:
                s1 = subprocess.Popen([py, "-m", "uvicorn", "services.solver.main:app",
                                       "--host", "127.0.0.1", "--port", "8081"],
                                      cwd=REPO, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL,
                                      creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
                procs.append(s1)
                reused.append("solver-spawned")
            else:
                reused.append("solver-reused")
            if not oracle_alive:
                s2 = subprocess.Popen([py, "-m", "uvicorn", "services.oracle.main:app",
                                       "--host", "127.0.0.1", "--port", "8082"],
                                      cwd=REPO, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL,
                                      creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
                procs.append(s2)
                reused.append("oracle-spawned")
            else:
                reused.append("oracle-reused")

        ok1 = wait_health("http://127.0.0.1:8081/health")
        ok2 = wait_health("http://127.0.0.1:8082/health")
        print(f"[runner] solver ready={ok1} oracle ready={ok2} ({','.join(reused)})", flush=True)
        if not (ok1 and ok2):
            print("[runner] ERROR: service not ready, abort", flush=True)
            return 1

        # 跑 pytest（用同一 python，保证依赖一致）
        r = subprocess.run([py, "-m", "pytest", "tests/", "-v"],
                           cwd=REPO, timeout=300)
        print(f"[runner] pytest exit={r.returncode}", flush=True)
        return 0 if r.returncode == 0 else 1
    finally:
        # 只 terminate 自己起的进程；复用的（人类终端常驻）不杀
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        time.sleep(1)
        for p in procs:
            try:
                if p.poll() is None:
                    p.kill()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
