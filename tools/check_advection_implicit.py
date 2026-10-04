"""D1 对流项验收脚本：FTCS/BTCS/CN 对流项生效性检查（任务书第五节判据 1）。

判据：L=1, alpha=1, v=1, nodes=21, 边界 left=0/right=1, tEnd=3
  稳态解析 u(x)=(exp(Pe·x)-1)/(exp(Pe)-1), Pe=v·L/alpha=1
  离散精确解 u_i=(1-R^i)/(1-R^N), R=(1+P/2)/(1-P/2), P=v·dx/alpha=0.05, N=20
  x=0.25 -> 0.165296(连续) / 0.165281(离散), x=0.5 -> 0.377541/0.377516, x=0.75 -> 0.650068/0.650046
  三格式均应落在离散精确解 ±0.001 内；BTCS 修复前曾因边界双计输出 2× 值，CN 修复前对流符号写反退化为纯扩散。"""
import math
import sys

sys.path.insert(0, ".")
from services.solver.main import solve_direct


def run(scheme, dt):
    payload = {
        "scheme": scheme, "alpha": 1.0, "nodes": 21, "dt": dt, "tEnd": 3.0, "length": 1.0,
        "initial": {"kind": "sin", "amplitude": 1.0, "modes": 1},
        "boundary": {"left": {"kind": "dirichlet", "value": 0.0},
                     "right": {"kind": "dirichlet", "value": 1.0}},
        "advection": {"enabled": True, "velocity": 1.0},
        "probes": [0.25, 0.5, 0.75], "recordEvery": 100000,
    }
    resp = solve_direct(payload)
    if hasattr(resp, "status_code"):
        import json
        print(f"{scheme}: ERROR {resp.status_code} {json.loads(resp.body)}")
        return None
    # solve_direct 返回的是 HTTP 层 resp dict，探针末点即 t=tEnd 终态
    u_final = [p["points"][-1]["u"] for p in resp["probes"]]  # 顺序对应 probes [0.25, 0.5, 0.75]
    pe = resp["numerics"]["peclet"]
    print(f"{scheme:5s} dt={dt:g}: u(0.25)={u_final[0]:.6f} u(0.5)={u_final[1]:.6f} u(0.75)={u_final[2]:.6f}  peclet={pe:.4f} blowUp={resp['summary']['blowUp']} steps={resp['numerics']['steps']}")
    return u_final


if __name__ == "__main__":
    disc = [(1.0 - 0.05 * 0) * (1 - ((1 + 0.025) / (1 - 0.025)) ** i) / (1 - ((1 + 0.025) / (1 - 0.025)) ** 20) for i in (5, 10, 15)]
    ex = [(math.exp(1 * x) - 1) / (math.exp(1) - 1) for x in (0.25, 0.5, 0.75)]
    print(f"exact Pe=1 (continuous): x=0.25 -> {ex[0]:.6f}, x=0.5 -> {ex[1]:.6f}, x=0.75 -> {ex[2]:.6f}")
    print(f"discrete exact (R=(1+P/2)/(1-P/2), P=0.05): x=0.25 -> {disc[0]:.6f}, x=0.5 -> {disc[1]:.6f}, x=0.75 -> {disc[2]:.6f}")
    dx = 1.0 / 20
    r_ftcs = run("ftcs", 0.25 * dx * dx)
    r_btcs = run("btcs", 5e-3)
    r_cn = run("cn", 5e-3)
    target = disc
    for name, got in (("ftcs", r_ftcs), ("btcs", r_btcs), ("cn", r_cn)):
        if got is None:
            continue
        err = max(abs(a - b) for a, b in zip(got, target))
        ok = err < 1e-3
        print(f"[check] {name:5s} max|err| vs discrete-exact = {err:.3e} -> {'OK' if ok else 'FAIL'}")
        if not ok:
            sys.exit(1)
