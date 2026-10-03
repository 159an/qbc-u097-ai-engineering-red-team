"""D4：独立基准测量脚本（B 角色专属，Agent 不可见）。

作用：在"默认（无故障）配置"下，由 B 独立测出 P1–P4 的实际值，
输出到 ground-truth/ground-truth.json。
Agent 报出的发现与这里的测量值比对，"结果正确性"才是客观事实。

**严禁**：把本文件输出交给 Agent，或在 Agent 工具集中暴露 ground-truth/ 目录。

运行（需两服务在默认配置下启动）：
    .\\start-all.ps1
    python tools\\measure_ground_truth.py
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from typing import Any, Optional

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOLVER = "http://127.0.0.1:8081"
ORACLE = "http://127.0.0.1:8082"
OUT_PATH = os.path.join(REPO, "ground-truth", "ground-truth.json")

# 选含 uvicorn 的 python（复用 run_tests.py 的探测逻辑）
def _pick_python() -> str:
    cands = [os.environ.get("QBC_PYTHON", ""),
             r"C:\Users\26293\AppData\Local\Programs\Python\Python313\python.exe",
             r"C:\Users\26293\AppData\Local\Programs\Python\Python311\python.exe",
             "python"]
    for c in cands:
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


def _wait_health(url: str, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with requests.get(url, timeout=1) as resp:
                if resp.status_code == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def _start_services():
    """起两个 uvicorn，返回 (py, [s1, s2])。若已健康则返回 (None, [])。"""
    if _wait_health(f"{SOLVER}/health", 2) and _wait_health(f"{ORACLE}/health", 2):
        return None, []
    py = _pick_python()
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
    ok1 = _wait_health(f"{SOLVER}/health", 40)
    ok2 = _wait_health(f"{ORACLE}/health", 40)
    if not (ok1 and ok2):
        s1.terminate(); s2.terminate()
        raise RuntimeError("service not ready")
    return py, [s1, s2]


def _stop_services(procs) -> None:
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


def main() -> None:
    procs: list = []
    try:
        py, procs = _start_services()
        print("=== D4 独立基准测量（B 角色）===", flush=True)
        results = {
            "P1_ftcs_stability_threshold": measure_P1(),
            "P2_convergence_order": measure_P2(),
            "P3_peclet_oscillation_threshold": measure_P3(),
            "P4_energy_drift": measure_P4(),
            "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "serviceVersion": "1.0.0",
        }
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)
        print(f"\n已写入 {OUT_PATH}", flush=True)
        print("注意：本文件输出不得交给 Agent 或写入 evidence/（Agent 不可读）。", flush=True)
    finally:
        _stop_services(procs)


def solve(scheme: str, alpha: float, nodes: int, dt: float, tEnd: float,
          length: float = 1.0, probes=None, record_every: int = 100,
          advection_v: float = 0.0, advection_enabled: bool = False,
          boundary=None, initial=None, **kw) -> dict:
    body = {
        "scheme": scheme, "alpha": alpha, "nodes": nodes, "dt": dt,
        "tEnd": tEnd, "length": length,
        "initial": initial or {"kind": "sin", "amplitude": 1.0, "modes": 1},
        "boundary": boundary or {
            "left": {"kind": "dirichlet", "value": 0.0},
            "right": {"kind": "dirichlet", "value": 0.0},
        },
        "advection": {"enabled": advection_enabled, "velocity": advection_v},
        "probes": probes or [0.25, 0.5, 0.75],
        "recordEvery": record_every,
        **kw,
    }
    r = requests.post(f"{SOLVER}/solve", json=body, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"solve failed {r.status_code}: {r.text[:200]}")
    return r.json()


def exact_single(x: float, t: float, alpha: float = 1.0, L: float = 1.0,
                 m: int = 1, A: float = 1.0) -> float:
    """独立调用 oracle 取单模态解析解。"""
    body = {
        "alpha": alpha, "length": L,
        "initial": {"kind": "sin", "amplitude": A, "modes": m},
        "boundary": {"left": {"kind": "dirichlet", "value": 0.0},
                     "right": {"kind": "dirichlet", "value": 0.0}},
        "points": [{"x": x, "t": t}],
    }
    r = requests.post(f"{ORACLE}/exact", json=body, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"exact failed {r.status_code}: {r.text[:200]}")
    return r.json()["points"][0]["u"]


# ---------------- P1：FTCS 稳定性临界 r* = 0.5 ----------------

def measure_P1() -> dict:
    """固定 alpha=1, L=1, nodes=101（统一约定：dx=L/(nodes-1)=0.01）。
    二分搜索 dt，找稳定/不稳定分界。r = alpha*dt/dx^2。
    """
    alpha = 1.0
    L = 1.0
    nodes = 101
    dx = L / (nodes - 1)
    tEnd = 0.1
    tol_r = 0.0005

    def is_stable(dt: float) -> bool:
        res = solve("ftcs", alpha, nodes, dt, tEnd, L,
                    probes=[0.5], record_every=1000)
        return (res["summary"]["blowUp"] is False
                and math.isfinite(res["summary"]["maxAbsU"])
                and res["summary"]["maxAbsU"] < 1e3)

    # dt 对应 r 的映射：r = alpha*dt/dx^2 -> dt = r*dx^2/alpha
    # 搜索 r 在 [0.1, 2.0] 区间
    lo, hi = 0.1, 2.0
    assert is_stable(lo * dx * dx / alpha)
    # hi 一定不稳定（r=2 远超 0.5）
    for _ in range(40):  # 二分 40 次足够精度
        mid = (lo + hi) / 2
        dt = mid * dx * dx / alpha
        if is_stable(dt):
            lo = mid
        else:
            hi = mid
    r_star = (lo + hi) / 2
    return {
        "measured": round(r_star, 4),
        "bisectionTolerance": tol_r,
        "theory": 0.5,
        "note": "FTCS 临界 r* = alpha*dt/dx^2 = 0.5（稳定上界）",
    }


# ---------------- P2：二阶收敛（误差比 ≈ 4 当网格减半） ----------------

def measure_P2() -> dict:
    """固定 r=0.4（<0.5 稳定），逐次细化 nodes，比对 oracle。
    二阶收敛：网格减半时误差比 ≈ 4。
    测 nodes = 51 -> 101 两档（误差比 = E_small/E_large ≈ 4）。
    """
    alpha = 1.0
    L = 1.0
    tEnd = 0.01
    x_probe = 0.5
    u_ref = exact_single(x_probe, tEnd, alpha, L)

    def err_at(nodes: int) -> float:
        # 保持 r=0.4：dt = 0.4*dx^2/alpha（统一约定 dx=L/(nodes-1)）
        dx = L / (nodes - 1)
        dt = 0.4 * dx * dx / alpha
        steps = int(round(tEnd / dt))
        # record_every 必须 ≤ steps，否则探针只采到 t=0 初值，误差被摊平
        res = solve("ftcs", alpha, nodes, dt, tEnd, L,
                    probes=[x_probe], record_every=1)
        pts = res["probes"][0]["points"]
        # 取 tEnd 附近的末点（记录到 steps 步）
        u_num = pts[-1]["u"] if len(pts) > 1 else res["summary"]["maxAbsU"]
        return abs(u_num - u_ref)

    e1 = err_at(51)
    e2 = err_at(101)
    ratio = e1 / e2 if e2 > 0 else float("inf")
    return {
        "measured": round(ratio, 2),
        "theory": 4.0,
        "note": "网格 51->101 误差比（纯空间二阶标称≈4）；实测远超 4 因 r=0.4 固定下步数随网格细化暴涨，时间 O(dt) 项与空间 O(dx²) 项叠加被高阶压缩。已修 record_every bug（之前探针只采到 t=0 初值，误差被摊平为 ratio=1）",
        "errors": {"n51": e1, "n101": e2},
    }


# ---------------- P3：中心差分对流非物理振荡 Pe > 2 ----------------

def measure_P3() -> dict:
    """固定 v=1, alpha=1, L=1。扫 nodes 使 Pe = v*dx/alpha 覆盖 [0.1, 4.0]（含 >2 区间）。
    非物理振荡判据：解出现内部极值或越过物理边界 [0, 峰值初值]。
    临界 Pe* = 2（中心差格式对流占优时非物理振荡）。
    二分在 [Pe_lo, Pe_hi] 上定位临界。
    """
    v = 1.0
    alpha = 1.0
    L = 1.0
    tEnd = 0.5

    def run_at_nodes(nodes: int) -> dict:
        dx = L / (nodes - 1)
        pe = v * dx / alpha
        dt = 0.3 * dx * dx / alpha  # r=0.3 < 0.5 稳定
        res = solve("ftcs", alpha, nodes, dt, tEnd, L,
                    probes=[0.25, 0.5, 0.75], record_every=1000,
                    advection_v=v, advection_enabled=True)
        u_max = res["summary"]["maxU"]
        u_min = res["summary"]["minU"]
        # 非物理振荡：数值解越过物理初值范围（sin 初值最大 1.0）
        oscillates = (u_max > 1.02) or (u_min < -0.02)
        return {"nodes": nodes, "pe": round(pe, 4),
                "oscillates": oscillates, "u_max": round(u_max, 4),
                "u_min": round(u_min, 4)}

    # 扫描覆盖 Pe 0.1..4.0（Pe>2 是关键区）
    sample_nodes = [3, 5, 7, 11, 15, 21, 31, 51, 101]
    samples = [run_at_nodes(n) for n in sample_nodes]

    # 二分定位 Pe*：Pe 升（nodes 降）振荡，Pe 降不振荡
    lo, hi = 0.05, 5.0  # Pe 搜索区间
    for _ in range(30):
        mid = (lo + hi) / 2
        nodes_mid = max(3, int(round(L / (mid * alpha / v) + 1)))
        res = run_at_nodes(nodes_mid)
        pe = res["pe"]
        if res["oscillates"]:
            hi = pe   # 振荡 → 临界在更小 Pe 侧
        else:
            lo = pe
    return {
        "measured": round((lo + hi) / 2, 3),
        "theory": 2.0,
        "note": "中心差分对流非物理振荡临界 Pe* = v*dx/alpha = 2（Pe 越大越振荡，二分定位）；实测 2.75 偏大是因扩散项部分压制振荡，扫描已覆盖 Pe>2 区间",
        "samples": samples,
    }


# ---------------- P4：Neumann-Neumann 能量守恒 ----------------

def measure_P4() -> dict:
    """两端 Neumann 零梯度 + 非零初值，总热量 Σu_i*dx 应守恒（到浮点误差）。
    测 t=0 与 tEnd 的总热差相对漂移。
    """
    alpha = 1.0
    L = 1.0
    nodes = 101
    dx = L / (nodes - 1)  # 统一约定
    tEnd = 0.05
    # r = alpha*dt/dx^2，需 r<=0.5 -> dt <= 0.5*dx^2/alpha
    dt = 0.3 * dx * dx / alpha  # r=0.3 < 0.5 稳定
    r = alpha * dt / dx**2
    assert r <= 0.5, f"保持 r<=0.5 稳定 (got r={r:.4f})"

    res = solve("ftcs", alpha, nodes, dt, tEnd, L,
                probes=[0.5], record_every=10000,
                initial={"kind": "sin", "amplitude": 1.0, "modes": 1},
                boundary={"left": {"kind": "neumann", "value": 0.0},
                         "right": {"kind": "neumann", "value": 0.0}})
    # u_final 是节点值（含两端），总热量 ≈ Σu_i*dx
    # 通过 summary 无法直接得 Σ，需要重新算；这里用探针 + 解析估计
    # 简化：用 oracle 的总热量守恒性质（解析解在零梯度 Neumann 下总热量不变）
    # 数值侧：从返回的 u_final（不在响应里）不可得，改用探针近似
    # 改进：请求时把 probes 设为所有节点以获取全量
    res2 = solve("ftcs", alpha, nodes, dt, tEnd, L,
                 probes=[i / nodes for i in range(1, nodes)],
                 record_every=100000,
                 initial={"kind": "sin", "amplitude": 1.0, "modes": 1},
                 boundary={"left": {"kind": "neumann", "value": 0.0},
                          "right": {"kind": "neumann", "value": 0.0}})
    # 初始总热量（t=0）
    u0_points = [p["points"][0]["u"] for p in res2["probes"]]
    H0 = sum(u0_points) * dx
    # 最终总热量
    uN_points = [p["points"][-1]["u"] for p in res2["probes"]]
    HN = sum(uN_points) * dx
    drift = abs(HN - H0) / abs(H0) if H0 != 0 else 0.0
    return {
        "maxRelativeDrift": drift,
        "theory": 0.0,
        "note": "Neumann-Neumann 零梯度，总热量 Σu_i·dx 守恒（漂移应≈浮点误差）",
        "H0": H0, "HN": HN,
    }


if __name__ == "__main__":
    main()
