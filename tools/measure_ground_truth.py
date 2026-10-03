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
        # 避免 Windows 控制台 GBK 编码报错：写文件已保证 UTF-8，控制台用 ascii-safe repr
        import io, sys as _sys
        try:
            _sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(json.dumps(results, ensure_ascii=True, indent=2), flush=True)
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


# ---------------- P2：二阶收敛（时间对齐测法） ----------------

def measure_P2() -> dict:
    """FTCS 二阶空间收敛：nodes 51 -> 101 两档，误差随网格细化按 4 倍下降（order≈2）。

    关键：测误差必须时间对齐。旧实现两档取同一 tEnd=0.01，但 r=0.4 固定时
    dt=0.4*dx²/alpha 随网格细化骤减，steps=tEnd/dt 暴涨，实际推进终态时刻
    t_actual = steps*dt 在两档上不同，且时间 O(dt) 误差与空间 O(dx²) 误差
    互相纠缠，误差比被扭曲成 65（非 4）。
    改法：取一个公共 dt，使两档 steps 都是整数（tEnd=0.008 取 dt=0.008 对两档都是 1 步，
    即 t_actual 一致），且与各自实际终态时刻的解析值比较，隔离纯空间误差。
    二阶：E(51)/E(101) ≈ (100/50)² = 4。"""
    alpha = 1.0
    L = 1.0
    # 时间对齐：两档公共终点 t=0.008，且 t 是两档 dt 的整数倍
    # nodes=51: dx=0.02, r=0.4 -> dt=0.4*dx²/alpha=8e-4 -> steps=0.008/8e-4=10（整数）
    # nodes=101: dx=0.01, r=0.4 -> dt=0.4*dx²/alpha=4e-4 -> steps=0.008/4e-4=20（整数）
    tAlign = 0.008
    x_probe = 0.5
    u_ref = exact_single(x_probe, tAlign, alpha, L)

    def err_at(nodes: int) -> float:
        dx = L / (nodes - 1)
        dt = 0.4 * dx * dx / alpha  # r=0.4 固定
        # 时间对齐：以 tAlign 为公共终点，steps=tAlign/dt 必为整数（构造保证）
        steps = int(round(tAlign / dt))
        t_actual = steps * dt  # 实际终态时刻（与 tAlign 一致到构造精度）
        assert abs(t_actual - tAlign) < 1e-12, f"时间未对齐: t_actual={t_actual} != {tAlign}"
        res = solve("ftcs", alpha, nodes, dt, t_actual, L,
                    probes=[x_probe], record_every=1)
        u_num = res["probes"][0]["points"][-1]["u"]
        # 与「各自实际终态时刻」的解析值比较（隔离纯空间二阶误差）
        u_ref_t = exact_single(x_probe, t_actual, alpha, L)
        return abs(u_num - u_ref_t)

    e1 = err_at(51)
    e2 = err_at(101)
    ratio = e1 / e2 if e2 > 0 else float("inf")
    # 收敛阶 order = log(ratio)/log(100/50)=log(ratio)/log(2)（51->101 间隔 100/50=2 倍）
    order = math.log(ratio, 2.0)
    return {
        "measured": round(order, 2),
        "theory": 2.0,
        "errorRatio": ratio,
        "note": f"时间对齐测法（公共 t={tAlign}，两档 steps 均为整数，与各自实际终态解析值比）：nodes 51->101 间隔 2 倍，空间二阶 order=log2(E51/E101)。旧 65.52 因两档同取 tEnd=0.01 时间错位（steps 13/2 非整除、r 不变下时间 O(dt) 项与空间 O(dx²) 项纠缠）被修掉",
        "errors": {"n51": e1, "n101": e2},
        "aligned_t": tAlign,
    }


# ---------------- P3：中心差分对流非物理振荡 Pe_cell > 2 ----------------

def measure_P3() -> dict:
    """中心差分对流非物理振荡阈值（任务书：固定 v, alpha，增大 dx 越过 Pe_cell=2，
    检查解是否离开边界值域出现非物理极值）。

    判据（只用一条，不换指标）：解是否越过边界值域 [0,1]
        oscillates = (u_min < -eps) or (u_max > 1 + eps),  eps = 1e-9

    参数设计（按任务书选 A：固定 nodes，把 v 当自变量）：
        nodes = 11, L = 1, alpha = 1  =>  dx = L/(nodes-1) = 0.1
        Pe_cell = v*dx/alpha = 0.1*v  （v 是线性自变量，Pe_cell 与 v 一一对应）
        v 在 [0, 40] 上扫 => Pe_cell 在 [0, 4] 上扫，越过理论阈值 2。
        临界 Pe_cell* = 2.0 对应 v* = 20。以 v 为自变量做二分（v∈[20,22] 区间，
        在 v*=20 判据首次越界）。

    旧实现的错误：以 nodes 为自变量且 alpha=1 时 Pe_cell=dx=L/(nodes-1)≤1，
    怎么扫都到不了 2；且 nodes 变化同时改了 dt 与 steps，判据混淆。改为
    固定 nodes（v 唯一自变量，Pe_cell=0.1*v），即可干净地定位 Pe_cell*=2。"""
    nodes = 11
    L = 1.0
    alpha = 1.0
    dx = L / (nodes - 1)          # = 0.1
    # 用 BTCS（无条件稳定）到稳态，彻底绕过 FTCS 的 CFL（r>0.5 会爆）：
    # dt=0.01 -> r=alpha*dt/dx²=1.0 对 BTCS 合法（对 FTCS 会爆）；tEnd=50 -> 5000 步足够到稳态
    dt = 0.01
    tEnd = 50.0
    scheme = "btcs"
    eps = 1e-9

    def run_at_v(v: float) -> dict:
        pe = v * dx / alpha        # Pe_cell = 0.1*v
        res = solve(scheme, alpha, nodes, dt, tEnd, L,
                    probes=[round(i / (nodes - 1), 6) for i in range(1, nodes - 1)],
                    record_every=10**6,
                    advection_v=v, advection_enabled=True,
                    boundary={"left": {"kind": "dirichlet", "value": 0.0},
                              "right": {"kind": "dirichlet", "value": 1.0}})
        u_max = res["summary"]["maxU"]
        u_min = res["summary"]["minU"]
        oscillates = (u_min < -eps) or (u_max > 1.0 + eps)
        return {"v": v, "pe": round(pe, 4),
                "oscillates": oscillates, "u_max": round(u_max, 6),
                "u_min": round(u_min, 6)}

    # 扫描覆盖 Pe_cell 0..4（v 0..40，跨 2 的关键区，含 >2 区间）
    sample_v = [0.0, 2.0, 4.0, 8.0, 10.0, 14.0, 18.0, 20.0, 22.0, 24.0, 26.0, 30.0, 40.0]
    samples = [run_at_v(vv) for vv in sample_v]

    # 二分定位 v*（Pe_cell* = 0.1*v*）：Pe_cell 升（v 升）振荡，Pe_cell 降不振荡。
    # 不变式：lo_v 侧不振荡、hi_v 侧振荡；mid 振荡则 hi=mid，否则 lo=mid。
    lo_v, hi_v = 20.0, 22.0  # Pe_cell 2.0 / 2.2 两端
    assert not run_at_v(lo_v)["oscillates"], "lo_v=20 应不振荡（Pe_cell=2.0 临界下界）"
    assert run_at_v(hi_v)["oscillates"], "hi_v=22 应振荡（Pe_cell=2.2>2）"
    for _ in range(30):
        mid = (lo_v + hi_v) / 2
        if abs(hi_v - lo_v) < 1e-6:
            break
        res = run_at_v(mid)
        if res["oscillates"]:
            hi_v = mid   # 振荡 → 临界在更小 v（更小 Pe）侧
        else:
            lo_v = mid   # 不振荡 → 临界在更大 v（更大 Pe）侧
    pe_star = ((lo_v + hi_v) / 2) * dx / alpha
    return {
        "measured": round(pe_star, 3),
        "theory": 2.0,
        "detector": "(u_min < -1e-9) or (u_max > 1 + 1e-9)",
        "params": {"nodes": nodes, "L": L, "alpha": alpha, "dx": dx,
                   "scheme": scheme, "dt": dt, "tEnd": tEnd,
                   "v_axis": "v in [0,40] -> Pe_cell = 0.1*v in [0,4]",
                   "note": "BTCS 无条件稳定，到稳态绕过 FTCS CFL；固定 nodes=11（dx=0.1），以 v 为自变量扫 Pe_cell=v*dx/alpha=0.1*v 越过 2"},
        "note": "中心差分对流非物理振荡临界 Pe_cell* = v*dx/alpha = 2。判据=解越过边界值域 [0,1]（u_min<-eps 或 u_max>1+eps）。"
               "BTCS 到稳态：v=20（Pe_cell=2.0）不越界、v=22（Pe_cell=2.2）u_min 首次变负越界，二分收敛 Pe*≈2.0（落入 2±0.1）",
        "bisection": {"lo_v": round(lo_v, 4), "hi_v": round(hi_v, 4),
                       "pe_range": [round(lo_v * dx / alpha, 4), round(hi_v * dx / alpha, 4)]},
        "samples": samples,
    }


# ---------------- P4：Neumann-Neumann 能量守恒（有限体积端点半权 H_fvm） ----------------

def measure_P4() -> dict:
    """两端 Neumann 零梯度 + 非零 sin 初值，能量守恒（到浮点误差 ~1e-16）。

    根因修正（对照实测：n=101 uniform 漂移 8.44e-3 / fvm 漂移 1.11e-16）：
      (a) probes 覆盖全部 nodes 个节点（含 Neumann 端点 i=0 / i=N），每个节点一条 probe。
      (b) 守恒量口径 = 有限体积端点半权 H_fvm = dx*(0.5*u[0] + u[1:-1].sum() + 0.5*u[-1])；
          均匀的 u.sum()*dx 本身有 O(dx) 系统漂移，只作对照打印，不作判据。
    maxRelativeDrift 记 H_fvm 的相对漂移（应 ~1e-16）。
    """
    alpha = 1.0
    L = 1.0
    nodes = 101
    dx = L / (nodes - 1)
    tEnd = 0.05
    dt = 0.3 * dx * dx / alpha
    r = alpha * dt / dx**2
    assert r <= 0.5, f"保持 r<=0.5 稳定 (got r={r:.4f})"

    # 全节点探针（含两端 Neumann 端点 i=0 / i=N，每个节点一条 probe）
    probes = [i / (nodes - 1) for i in range(nodes)]
    res = solve("ftcs", alpha, nodes, dt, tEnd, L,
                probes=probes, record_every=100000,
                initial={"kind": "sin", "amplitude": 1.0, "modes": 1},
                boundary={"left": {"kind": "neumann", "value": 0.0},
                          "right": {"kind": "neumann", "value": 0.0}})
    assert len(res["probes"]) == nodes, f"P4 探针须覆盖全部 nodes 节点（got {len(res['probes'])}）"

    u0 = [p["points"][0]["u"] for p in res["probes"]]
    uN = [p["points"][-1]["u"] for p in res["probes"]]

    # 守恒量口径：有限体积端点半权 H_fvm = dx*(0.5*u[0] + u[1:-1].sum() + 0.5*u[-1])
    H_fvm_0 = dx * (0.5 * u0[0] + sum(u0[1:-1]) + 0.5 * u0[-1])
    H_fvm_N = dx * (0.5 * uN[0] + sum(uN[1:-1]) + 0.5 * uN[-1])
    fvm_drift = abs(H_fvm_N - H_fvm_0) / abs(H_fvm_0) if H_fvm_0 != 0 else 0.0

    # 对照口径：均匀 Σu_i*dx（有 O(dx) 系统漂移，仅作参考，不作判据）
    H_uniform_0 = sum(u0) * dx
    H_uniform_N = sum(uN) * dx
    uniform_drift = abs(H_uniform_N - H_uniform_0) / abs(H_uniform_0) if H_uniform_0 != 0 else 0.0

    print(f"P4 H_fvm    : {H_fvm_0:.6e} -> {H_fvm_N:.6e}, drift = {fvm_drift:.3e}", flush=True)
    print(f"P4 H_uniform: {H_uniform_0:.6e} -> {H_uniform_N:.6e}, drift = {uniform_drift:.3e} (O(dx) 系统漂移，非判据)", flush=True)

    return {
        "maxRelativeDrift": fvm_drift,
        "theory": 0.0,
        "note": ("Neumann 零梯度；有限体积端点半权 dx/2。"
                 "H_fvm=dx*(0.5*u[0]+sum(u[1:-1])+0.5*u[-1]) 守恒，漂移~浮点误差；"
                 "H_uniform=sum(u)*dx 因 O(dx) 系统漂移不可作判据，仅作对照"),
        "H_fvm_0": H_fvm_0,
        "H_fvm_N": H_fvm_N,
        "H_fvm_drift": fvm_drift,
        "H_uniform_0": H_uniform_0,
        "H_uniform_N": H_uniform_N,
        "H_uniform_drift": uniform_drift,
        "nodes": nodes,
        "dx": dx,
        "initial_kind": "sin",
    }


if __name__ == "__main__":
    main()
