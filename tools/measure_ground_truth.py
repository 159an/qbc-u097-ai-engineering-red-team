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
import time
from typing import Any, Optional

import requests

SOLVER = "http://127.0.0.1:8081"
ORACLE = "http://127.0.0.1:8082"
OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "ground-truth", "ground-truth.json")


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
    """固定 alpha=1, L=1, nodes=101 (dx=0.01)。二分搜索 dt，
    找稳定/不稳定的分界。r = alpha*dt/dx^2。
    稳定判据：tEnd 较大时解不发散（blowUp=False 且 maxAbsU 有界）。
    """
    alpha = 1.0
    L = 1.0
    nodes = 101
    dx = L / nodes
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
        # 保持 r=0.4：dt = 0.4*dx^2/alpha
        dx = L / nodes
        dt = 0.4 * dx * dx / alpha
        steps = int(round(tEnd / dt))
        res = solve("ftcs", alpha, nodes, dt, tEnd, L,
                    probes=[x_probe], record_every=10000)
        # 取最后一个探针值
        pts = res["probes"][0]["points"]
        u_num = pts[-1]["u"] if pts else res["summary"]["maxAbsU"]
        return abs(u_num - u_ref)

    e1 = err_at(51)
    e2 = err_at(101)
    ratio = e1 / e2 if e2 > 0 else float("inf")
    return {
        "measured": round(ratio, 2),
        "theory": 4.0,
        "note": "网格 51->101 误差比（二阶应≈4）",
        "errors": {"n51": e1, "n101": e2},
    }


# ---------------- P3：中心差分对流非物理振荡 Pe > 2 ----------------

def measure_P3() -> dict:
    """固定 v, alpha，增大 nodes 减小 dx 使 Pe 下降；或减小 nodes 增大 dx。
    这里固定 v=1, alpha=1，扫 nodes，找 Pe 越 2 时解越过边界出现非物理极值。
    判据：稳态（或长时间）后 |maxU - 1| 或出现内部极值。
    """
    v = 1.0
    alpha = 1.0
    L = 1.0
    tEnd = 0.5
    x_probe = 0.5

    # 扫 nodes 从 11 到 101，记录 Pe = v*dx/alpha
    samples = []
    for nodes in [11, 15, 21, 31, 51, 101]:
        dx = L / nodes
        Pe = v * dx / alpha
        # 保持 r < 0.5：dt = 0.3*dx^2/alpha
        dt = 0.3 * dx * dx / alpha
        res = solve("ftcs", alpha, nodes, dt, tEnd, L,
                    probes=[0.25, 0.5, 0.75], record_every=1000,
                    advection_v=v, advection_enabled=True)
        u_max = res["summary"]["maxU"]
        u_min = res["summary"]["minU"]
        # 非物理振荡：解越过 [0,1] 边界（最大值>1 或 最小值<0）
        oscillates = (u_max > 1.01) or (u_min < -0.01)
        samples.append({"nodes": nodes, "pe": round(Pe, 3),
                       "oscillates": oscillates, "u_max": round(u_max, 4)})

    # 找最小说振荡的 Pe 阈值
    pe_vals = [s["pe"] for s in samples]
    osc_flags = [s["oscillates"] for s in samples]
    # 二分找 Pe 临界（Pe>2 振荡，Pe<2 不振荡）
    lo, hi = min(pe_vals), max(pe_vals)
    for _ in range(20):
        mid = (lo + hi) / 2
        nodes_mid = round(L / (mid * alpha / v))
        nodes_mid = max(5, nodes_mid)
        dx = L / nodes_mid
        Pe = v * dx / alpha
        dt = 0.3 * dx * dx / alpha
        res = solve("ftcs", alpha, nodes_mid, dt, tEnd, L,
                    probes=[0.5], record_every=1000,
                    advection_v=v, advection_enabled=True)
        osc = (res["summary"]["maxU"] > 1.01) or (res["summary"]["minU"] < -0.01)
        if osc:
            hi = Pe
        else:
            lo = Pe
    return {
        "measured": round((lo + hi) / 2, 2),
        "theory": 2.0,
        "note": "中心差分对流非物理振荡临界 Pe = v*dx/alpha = 2",
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
    dx = L / nodes
    tEnd = 0.05
    dt = 0.0001
    r = alpha * dt / dx**2
    assert r <= 0.5, "保持 r<=0.5 稳定"

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


def main() -> None:
    print("=== D4 独立基准测量（B 角色）===")
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
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n已写入 {OUT_PATH}")
    print("注意：本文件输出不得交给 Agent 或写入 evidence/（Agent 不可读）。")


if __name__ == "__main__":
    main()
