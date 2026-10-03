"""验证对流项在 FTCS 里真实生效（10/7 交付项）。
自包含：起服务 -> 跑无对流 vs 有对流两次 -> 比对稳态分布 -> 停服务。
判据：v>0 时，峰应从 x=0.5 右移（下游），即 u(0.6,tEnd) > u(0.4,tEnd)。
"""
from __future__ import annotations
import os, subprocess, sys, time, urllib.request, json, urllib.parse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOLVER = "http://127.0.0.1:8081"
ORACLE = "http://127.0.0.1:8082"

def pick_python() -> str:
    cands = [os.environ.get("QBC_PYTHON", ""),
             r"C:\Users\26293\AppData\Local\Programs\Python\Python313\python.exe",
             r"C:\Users\26293\AppData\Local\Programs\Python\Python311\python.exe",
             "python"]
    for c in cands:
        if not c:
            continue
        try:
            r = subprocess.run([c, "-c", "import uvicorn"], capture_output=True, timeout=15)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return sys.executable

def wait_health(url, timeout=40.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False

def post(body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{SOLVER}/solve", data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())

def main():
    py = pick_python()
    print(f"[adv-verify] python = {py}", flush=True)
    procs = []
    try:
        s1 = subprocess.Popen([py, "-m", "uvicorn", "services.solver.main:app",
                                "--host", "127.0.0.1", "--port", "8081"],
                               cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        procs.append(s1)
        if not wait_health(f"{SOLVER}/health", 40):
            raise RuntimeError("solver not ready")

        # 公共参数：sin 初值峰值在 0.5
        common = {
            "alpha": 1.0, "nodes": 51, "tEnd": 0.5, "length": 1.0,
            "initial": {"kind": "sin", "amplitude": 1.0, "modes": 1},
            "boundary": {"left": {"kind": "dirichlet", "value": 0.0},
                         "right": {"kind": "dirichlet", "value": 0.0}},
            "probes": [0.3, 0.4, 0.5, 0.6, 0.7], "recordEvery": 1000,
        }
        # dt：保持 r=alpha*dt/dx^2 < 0.5（dx=1/50=0.02 -> dt=1.5e-4, r=0.375）
        common["dt"] = 1.5e-4

        # 无对流
        base = dict(common); base["scheme"] = "ftcs"
        base["advection"] = {"enabled": False, "velocity": 0.0}
        r0 = post(base)
        # 有对流 v=0.5（峰值向 +x 移动，下游 u 更大）
        adv = dict(common); adv["scheme"] = "ftcs"
        adv["advection"] = {"enabled": True, "velocity": 0.5}
        r1 = post(adv)

        def probe_u(resp, x):
            for p in resp["probes"]:
                if abs(p["x"] - x) < 1e-9:
                    return p["points"][-1]["u"]
            return None

        print("\n=== 无对流（纯扩散，tEnd=0.1 时峰大幅衰减）===", flush=True)
        for x in [0.3, 0.4, 0.5, 0.6, 0.7]:
            print(f"  u({x}) = {probe_u(r0, x):.6f}", flush=True)
        print("\n=== 有对流 v=0.5（峰向下游 +x 移动）===", flush=True)
        for x in [0.3, 0.4, 0.5, 0.6, 0.7]:
            print(f"  u({x}) = {probe_u(r1, x):.6f}", flush=True)

        # 判据：有对流时下游(0.6) > 上游(0.4)；无对流时 0.4 ≈ 0.6（对称）
        u4_adv, u6_adv = probe_u(r1, 0.4), probe_u(r1, 0.6)
        u4_base, u6_base = probe_u(r0, 0.4), probe_u(r0, 0.6)
        print(f"\n[判据] 有对流: u(0.4)={u4_adv:.4f} vs u(0.6)={u6_adv:.4f} -> "
              f"{'右移✓' if u6_adv > u4_adv else '未右移✗'}")
        print(f"[判据] 无对流: u(0.4)={u4_base:.4f} vs u(0.6)={u6_base:.4f} -> "
              f"{'对称✓' if abs(u4_base - u6_base) < 0.01 else '不对称✗'}")
        # peclet 应被返回
        print(f"\n[peclet] 有对流请求返回 peclet = {r1['numerics']['peclet']:.4f} (理论 v*dx/alpha = 0.5*0.02=0.01)")
        ok_adv = u6_adv > u4_adv
        print(f"\n[判据] 有对流: u(0.4)={u4_adv:.4f} vs u(0.6)={u6_adv:.4f} -> "
              f"{'右移 OK' if ok_adv else '未右移 NG'}", flush=True)
        sym = abs(u4_base - u6_base) < 0.01
        print(f"[判据] 无对流: u(0.4)={u4_base:.4f} vs u(0.6)={u6_base:.4f} -> "
              f"{'对称 OK' if sym else '不对称 NG'}", flush=True)
        print(f"\n[peclet] 有对流请求返回 peclet = {r1['numerics']['peclet']:.4f} "
              f"(理论 v*dx/alpha = 0.5*0.02 = 0.01)", flush=True)
        print(f"\n[结论] 对流项生效: {'YES' if ok_adv else 'NO'}", flush=True)
        if not ok_adv:
            sys.exit(1)
    finally:
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
    main()
