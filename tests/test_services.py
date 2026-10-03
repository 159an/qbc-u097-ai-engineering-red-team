"""D6 单元测试：证明服务本身是对的（验收标准第五节）。

运行（一键起服务+测试，仓库根目录）：
    python tools/run_tests.py
或手动起服务后：
    python -m pytest tests/ -v

覆盖：
- FTCS 稳定性边界（r=0.49 收敛 / r=0.51 发散）
- 参数校验 400 路径（alpha=-1, nodes=1 等）
- Oracle 解析解精度（单模态 + 稳态对流扩散）
- Oracle 422 路径（无闭式解时拒答）
"""
from __future__ import annotations

import math
import pytest
import requests

SOLVER = "http://127.0.0.1:8081"
ORACLE = "http://127.0.0.1:8082"


def solve(body: dict) -> requests.Response:
    return requests.post(f"{SOLVER}/solve", json=body, timeout=60)


def exact(body: dict) -> requests.Response:
    return requests.post(f"{ORACLE}/exact", json=body, timeout=30)


def base_body(**over) -> dict:
    b = {
        "scheme": "ftcs", "alpha": 1.0, "nodes": 101, "dt": 0.0001,
        "tEnd": 0.05, "length": 1.0,
        "initial": {"kind": "sin", "amplitude": 1.0, "modes": 1},
        "boundary": {"left": {"kind": "dirichlet", "value": 0.0},
                     "right": {"kind": "dirichlet", "value": 0.0}},
        "advection": {"enabled": False, "velocity": 0.0},
        "probes": [0.25, 0.5, 0.75], "recordEvery": 10,
    }
    b.update(over)
    return b


# ---- D1 验收 ----

def test_health_solver():
    r = requests.get(f"{SOLVER}/health", timeout=5)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "ftcs" in r.json()["schemes"]


def test_ftcs_r049_converges():
    # r = alpha*dt/dx^2 = 1 * dt / (1/101)^2 = 10201*dt
    # 要 r=0.49 -> dt = 0.49/10201 ≈ 4.7999e-5
    dt = 0.49 / (101.0 * 101.0)
    r = solve(base_body(dt=dt, tEnd=0.01))
    assert r.status_code == 200
    j = r.json()
    assert j["summary"]["blowUp"] is False
    assert math.isclose(j["numerics"]["r"], 0.49, abs_tol=1e-3)


def test_ftcs_r051_blowup():
    dt = 0.51 / (101.0 * 101.0)
    r = solve(base_body(dt=dt, tEnd=0.05))
    assert r.status_code == 200
    j = r.json()
    # 默认开启 CFL 保护：r>0.5 直接标记不稳定（steps=0, blowUp=True）
    assert j["summary"]["blowUp"] is True
    assert j["numerics"]["steps"] == 0


def test_alpha_negative_400():
    r = solve(base_body(alpha=-1.0))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_ALPHA"


def test_nodes_1_400():
    r = solve(base_body(nodes=1))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_NODES"


def test_tend_zero_returns_initial():
    r = solve(base_body(tEnd=0.0))
    assert r.status_code == 200
    j = r.json()
    assert j["numerics"]["steps"] == 0
    # 探针值应为初值 A·sin(m·π·x) 在节点处的离散值（x=50/101≈0.495，非精确 0.5）
    u500 = [p for p in j["probes"] if math.isclose(p["x"], 0.5)][0]["points"][0]["u"]
    # 节点 50 在 nodes=101 时 x=50/101，sin(π·50/101)≈0.99988，放宽到 0.01
    assert math.isclose(u500, math.sin(math.pi * 50 / 101), abs_tol=1e-6)


def test_probe_out_of_range_400():
    r = solve(base_body(probes=[1.5]))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "PROBE_OUT_OF_RANGE"


def test_nodes_2_3_no_crash():
    for n in (2, 3):
        r = solve(base_body(nodes=n, probes=[0.5]))
        assert r.status_code == 200, f"nodes={n} crashed"


# ---- D2 验收 ----

def test_oracle_single_mode_hand_computed():
    """情况 1：A=1, m=1, α=1, L=1, (x=0.5, t=0.001) 应等于 exp(−π²·0.001)"""
    r = exact({
        "alpha": 1.0, "length": 1.0,
        "initial": {"kind": "sin", "amplitude": 1.0, "modes": 1},
        "boundary": {"left": {"kind": "dirichlet", "value": 0.0},
                     "right": {"kind": "dirichlet", "value": 0.0}},
        "points": [{"x": 0.5, "t": 0.001}],
    })
    assert r.status_code == 200
    j = r.json()
    expected = math.exp(-math.pi**2 * 0.001)
    assert math.isclose(j["points"][0]["u"], expected, rel_tol=1e-6)


def test_oracle_steady_convection():
    """情况 2：稳态对流扩散，v=1, α=1, L=1，Pe=1，u(0.5) 公式值"""
    r = exact({
        "alpha": 1.0, "length": 1.0, "velocity": 1.0,
        "steady": True,
        "boundary": {"left": {"kind": "dirichlet", "value": 0.0},
                     "right": {"kind": "dirichlet", "value": 1.0}},
        "points": [{"x": 0.5, "t": 0.0}],
    })
    assert r.status_code == 200
    j = r.json()
    Pe = 1.0
    expected = (math.exp(Pe * 0.5) - 1.0) / (math.exp(Pe) - 1.0)
    assert math.isclose(j["points"][0]["u"], expected, rel_tol=1e-9)


def test_oracle_no_closed_form_422():
    """Neumann 边界 + sin 初值：无闭式解 -> 422"""
    r = exact({
        "alpha": 1.0, "length": 1.0,
        "initial": {"kind": "sin", "amplitude": 1.0, "modes": 1},
        "boundary": {"left": {"kind": "neumann", "value": 0.0},
                     "right": {"kind": "dirichlet", "value": 0.0}},
        "points": [{"x": 0.5, "t": 0.01}],
    })
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "NO_CLOSED_FORM"


def test_oracle_health():
    r = requests.get(f"{ORACLE}/health", timeout=5)
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ---- 并发一致性（D1 验收：10 并发结果与串行逐位一致） ----

def test_concurrent_consistency():
    import concurrent.futures
    body = base_body()

    def one(_):
        return solve(body).json()["probes"][1]["points"][-1]["u"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(one, range(10)))
    assert len(set(results)) == 1, f"并发结果不一致: {set(results)}"
