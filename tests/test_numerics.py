"""D1 三格式数值正确性回归测试（无需起服务，直接调 main.solve_direct）。

验收标准：
  alpha=1, L=1, nodes=101, tEnd=0.01, 初值 A·sin(πx/L), A=1, 两端 Dirichlet=0
  解析解 u(0.5, 0.01) = exp(-π²·0.01) ≈ 0.9060180558

  各格式与解析解偏差（ground-truth/ground-truth.json 记录容差，统一约定 nodes=101 dx=0.01）：
    FTCS (r=0.25, dt=2.5e-5,  400步): 误差 ≈ 3.7e-06   → 容差 5e-4
    BTCS (r=5.0,  dt=5e-4,     20步): 误差 ≈ 3.4e-04   → 容差 5e-4
    CN   (r=5.0,  dt=5e-4,     20步): 误差 ≈ 4.3e-05   → 容差 1e-4

  三种格式在同一算例下都返回 t=tEnd 的探针值（steps > 0, blowUp=False）。

运行：
    python -m pytest tests/test_numerics.py -v
"""
from __future__ import annotations

import math
import sys
import os

# 确保仓库根在 sys.path（services 包可导入）
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from services.solver.main import solve_direct
from fastapi.responses import JSONResponse

# 算例参数
ALPHA = 1.0
L = 1.0
NODES = 101
TEND = 0.01
EXACT = math.exp(-math.pi ** 2 * TEND)  # ≈ 0.9060180558

# 各格式 dt 选择（统一约定：nodes=网格点数, dx=L/(nodes-1)=0.01, 所有数组长=nodes）
SCHEME_PARAMS = {
    # FTCS: r = alpha*dt/dx² = 0.25 → dt = 0.25*0.01² = 2.5e-5, 400步
    "ftcs": {"dt": 2.5e-5, "tol": 5e-4},
    # BTCS: 无条件稳定，一阶时间精度 O(dt)，dt=5e-4 → r=5.0, 20步
    "btcs": {"dt": 5e-4, "tol": 5e-4},
    # CN:   无条件稳定，二阶时间精度 O(dt²)，dt=5e-4 → r=5.0, 20步（与 BTCS 同参数便于对比）
    "cn":   {"dt": 5e-4, "tol": 1e-4},
}


def _payload(scheme: str, dt: float) -> dict:
    return {
        "scheme": scheme,
        "alpha": ALPHA,
        "nodes": NODES,  # 网格点数（含两端，统一约定 dx=L/(nodes-1)）
        "dt": dt,
        "tEnd": TEND,
        "length": L,
        "initial": {"kind": "sin", "amplitude": 1.0, "modes": 1},
        "boundary": {
            "left":  {"kind": "dirichlet", "value": 0.0},
            "right": {"kind": "dirichlet", "value": 0.0},
        },
        "advection": {"enabled": False, "velocity": 0.0},
        "probes": [0.5],
        "recordEvery": 1,
    }


def _probe_u_at_tend(resp: dict) -> float:
    """取 t=tEnd 的探针值（最后一个点）。"""
    probes = resp["probes"]
    assert len(probes) == 1, f"expected 1 probe, got {len(probes)}"
    pts = probes[0]["points"]
    assert len(pts) >= 2, f"expected at least 2 points (t=0 and t=tEnd), got {len(pts)}"
    return pts[-1]["u"]


# ---- 三种格式都能返回探针值 ----

def test_ftcs_probe_exists():
    resp = solve_direct(_payload("ftcs", SCHEME_PARAMS["ftcs"]["dt"]))
    assert isinstance(resp, dict), f"expected dict, got {type(resp)}"
    assert resp["summary"]["blowUp"] is False, "FTCS should not blow up at r=0.25"
    assert resp["numerics"]["steps"] > 0, "FTCS should have completed steps"
    u = _probe_u_at_tend(resp)
    assert math.isfinite(u), f"FTCS probe u not finite: {u}"


def test_btcs_probe_exists():
    """回归：修复前 BTCS 抛 IndexError（nodes+1 网格点 vs n 系数向量长度不匹配）。"""
    resp = solve_direct(_payload("btcs", SCHEME_PARAMS["btcs"]["dt"]))
    assert isinstance(resp, dict), f"BTCS returned {type(resp)} instead of dict"
    # 若发生 INTERNAL_SOLVER_ERROR 会是 JSONResponse
    if isinstance(resp, JSONResponse):
        raise AssertionError(f"BTCS raised internal error: {resp.body}")
    assert resp["summary"]["blowUp"] is False, "BTCS should not blow up (unconditionally stable)"
    assert resp["numerics"]["steps"] > 0, "BTCS should have completed steps"
    u = _probe_u_at_tend(resp)
    assert math.isfinite(u), f"BTCS probe u not finite: {u}"


def test_cn_probe_exists():
    resp = solve_direct(_payload("cn", SCHEME_PARAMS["cn"]["dt"]))
    assert isinstance(resp, dict), f"CN returned {type(resp)} instead of dict"
    if isinstance(resp, JSONResponse):
        raise AssertionError(f"CN raised internal error: {resp.body}")
    assert resp["summary"]["blowUp"] is False, "CN should not blow up (unconditionally stable)"
    assert resp["numerics"]["steps"] > 0, "CN should have completed steps"
    u = _probe_u_at_tend(resp)
    assert math.isfinite(u), f"CN probe u not finite: {u}"


# ---- 与 oracle 解析解比对 ----

def test_ftcs_accuracy_vs_oracle():
    dt = SCHEME_PARAMS["ftcs"]["dt"]
    tol = SCHEME_PARAMS["ftcs"]["tol"]
    resp = solve_direct(_payload("ftcs", dt))
    u = _probe_u_at_tend(resp)
    err = abs(u - EXACT)
    assert err < tol, f"FTCS err={err:.6e} >= tol={tol} (exact={EXACT:.10f}, u={u:.10f})"


def test_btcs_accuracy_vs_oracle():
    dt = SCHEME_PARAMS["btcs"]["dt"]
    tol = SCHEME_PARAMS["btcs"]["tol"]
    resp = solve_direct(_payload("btcs", dt))
    u = _probe_u_at_tend(resp)
    err = abs(u - EXACT)
    assert err < tol, f"BTCS err={err:.6e} >= tol={tol} (exact={EXACT:.10f}, u={u:.10f})"


def test_cn_accuracy_vs_oracle():
    dt = SCHEME_PARAMS["cn"]["dt"]
    tol = SCHEME_PARAMS["cn"]["tol"]
    resp = solve_direct(_payload("cn", dt))
    u = _probe_u_at_tend(resp)
    err = abs(u - EXACT)
    assert err < tol, f"CN err={err:.6e} >= tol={tol} (exact={EXACT:.10f}, u={u:.10f})"


# ---- 异常路径：INTERNAL_SOLVER_ERROR 不外泄为 500 裸异常 ----

def test_solver_internal_error_wrapped():
    """构造一个会触发内部异常的场景（如 nodes=1 但 validate 已拦截，
    这里用非法 probes 触发 probe_positions 越界作为回归哨兵）。"""
    # nodes=2, dt 合理，但 probes=[2.0] 超出 [0,1] 应由 validate 拦截 → 400
    resp = solve_direct({
        "scheme": "ftcs", "alpha": 1.0, "nodes": 101,
        "dt": 1e-4, "tEnd": 0.01, "length": 1.0,
        "initial": {"kind": "sin", "amplitude": 1.0, "modes": 1},
        "boundary": {"left": {"kind": "dirichlet", "value": 0.0},
                     "right": {"kind": "dirichlet", "value": 0.0}},
        "advection": {"enabled": False},
        "probes": [2.0],   # 越界
        "recordEvery": 1,
    })
    assert isinstance(resp, JSONResponse), "out-of-range probe should return 400 JSONResponse"
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}"
