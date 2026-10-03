"""数值内核：FTCS / BTCS / CN 三类格式 + 边界 + 对流 + 故障开关。

纪律红线：
- 本模块是纯确定性数值代码，不得调用任何 LLM/AI。
- 默认配置下结果正确、诚实：非法参数报错、越界 CFL 触发稳定性保护、
  并发请求按请求隔离。

故障开关（faults.py 中定义，环境变量控制，默认关闭）：
- QBC_FAULT_CFL_GUARD=off   -> 关闭 r>0.5 的稳定性保护，允许静默进入不稳定区
- QBC_FAULT_SHARED_STATE=on -> 使用进程级共享数组（跨请求可污染）
- QBC_FAULT_SILENT_CLAMP=on -> 负 alpha 静默取绝对值，不报 400
- QBC_FAULT_PARTIAL_ON_TIMEOUT=on -> 超时返回部分结果但不标记 incomplete
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .faults import FAULTS


# ----------------------------- 参数校验 -----------------------------

class ParamError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def validate_params(alpha: float, nodes: int, dt: float, tEnd: float,
                    length: float, probes, scheme: str) -> None:
    """默认配置下严格校验；QBC_FAULT_SILENT_CLAMP=on 时负 alpha 静默取绝对值。"""
    if FAULTS.silent_clamp:
        alpha = abs(alpha)
    else:
        if not (isinstance(alpha, (int, float)) and math.isfinite(alpha)) or alpha <= 0:
            raise ParamError("INVALID_ALPHA", f"alpha must be > 0, got {alpha!r}")
    if not isinstance(nodes, int) or nodes < 2:
        raise ParamError("INVALID_NODES", f"nodes must be int >= 2, got {nodes!r}")
    if not (isinstance(dt, (int, float)) and math.isfinite(dt)) or dt <= 0:
        raise ParamError("INVALID_DT", f"dt must be > 0, got {dt!r}")
    if not (isinstance(tEnd, (int, float)) and math.isfinite(tEnd)) or tEnd < 0:
        raise ParamError("INVALID_TEND", f"tEnd must be >= 0, got {tEnd!r}")
    if not (isinstance(length, (int, float)) and math.isfinite(length)) or length <= 0:
        raise ParamError("INVALID_LENGTH", f"length must be > 0, got {length!r}")
    if probes:
        for p in probes:
            if not (0.0 <= p <= 1.0):
                raise ParamError("PROBE_OUT_OF_RANGE", f"probe {p!r} outside [0,1]")
    if scheme not in ("ftcs", "btcs", "cn"):
        raise ParamError("UNSUPPORTED_SCHEME", f"scheme {scheme!r} not implemented")


# ----------------------------- 初值 / 边界 -----------------------------

def build_initial(kind: str, amplitude: float, modes: int, nodes: int, length: float) -> np.ndarray:
    """初始条件。返回 nodes 个网格点（含两端 0 和 length）。

    统一约定：nodes = 网格点数，dx = length/(nodes-1)。
    网格 x_i = i*dx, i=0..nodes-1。内部节点 [1..nodes-2] 是未知量，两端由边界条件确定。
    目前支持 'sin'：A·sin(m·π·x/L)。其他 kind 暂不支持，返回全 0。
    """
    if kind == "sin":
        x = np.linspace(0.0, length, nodes)
        return amplitude * np.sin(modes * math.pi * x / length)
    return np.zeros(nodes)


def _dx_length(length: float, nodes: int) -> float:
    """网格步长：nodes 个网格点，nodes-1 个间隔，dx = L/(nodes-1)。"""
    return length / (nodes - 1)


@dataclass
class BC:
    kind: str  # 'dirichlet' | 'neumann'
    value: float

    @staticmethod
    def parse(obj: Optional[dict]) -> "BC":
        if not obj:
            return BC(kind="dirichlet", value=0.0)
        return BC(kind=str(obj.get("kind", "dirichlet")).lower(),
                  value=float(obj.get("value", 0.0)))


# ----------------------------- 求解器 -----------------------------

_SHARED_BUF = None  # 模块级：QBC_FAULT_SHARED_STATE=on 时跨请求复用，默认 None（按请求隔离）


def _is_blowup(u: np.ndarray, initial_amp: float) -> bool:
    if not np.all(np.isfinite(u)):
        return True
    if initial_amp == 0:
        return bool(np.max(np.abs(u)) > 1e6)
    return bool(np.max(np.abs(u)) > 1e6 * abs(initial_amp))


def _apply_bc_dirichlet(u: np.ndarray, left: BC, right: BC) -> None:
    u[0] = left.value
    u[-1] = right.value



def _laplacian(u: np.ndarray, dx: float, left: BC, right: BC,
                ghosts: Optional[tuple] = None) -> np.ndarray:
    """二阶中心差分 Laplacian，对内部节点 [1..n-2]。
    n = len(u) = 网格点数。Neumann 时用幽灵点值。
    """
    n = len(u)  # 网格点数
    lap = np.zeros_like(u)
    if left.kind == "dirichlet" and right.kind == "dirichlet":
        # 内部：(u[i-1] - 2u[i] + u[i+1]) / dx^2
        lap[1:n-1] = (u[0:n-2] - 2.0 * u[1:n-1] + u[2:n]) / (dx * dx)
        # 端点：二阶单侧（Dirichlet 已知值直接代入，不参与 Laplacian）
        lap[0] = 0.0
        lap[-1] = 0.0
    elif left.kind == "neumann" and right.kind == "neumann":
        gl = ghosts[0] if ghosts else 0.0
        gr = ghosts[1] if ghosts else 0.0
        # 左端 i=0：(gl - 2u[0] + u[1]) / dx^2
        lap[0] = (gl - 2.0 * u[0] + u[1]) / (dx * dx)
        # 内部
        lap[1:n-1] = (u[0:n-2] - 2.0 * u[1:n-1] + u[2:n]) / (dx * dx)
        # 右端 i=n-1：(u[n-2] - 2u[n-1] + gr) / dx^2
        lap[-1] = (u[-2] - 2.0 * u[-1] + gr) / (dx * dx)
    else:
        # 混合边界，简化处理
        if left.kind == "neumann":
            gl = ghosts[0] if ghosts else 0.0
            lap[0] = (gl - 2.0 * u[0] + u[1]) / (dx * dx)
        else:
            lap[0] = 0.0
        if right.kind == "neumann":
            gr = ghosts[1] if ghosts else 0.0
            lap[-1] = (u[-2] - 2.0 * u[-1] + gr) / (dx * dx)
        else:
            lap[-1] = 0.0
        lap[1:n-1] = (u[0:n-2] - 2.0 * u[1:n-1] + u[2:n]) / (dx * dx)
    return lap


def _advective_term(u: np.ndarray, v: float, dx: float) -> np.ndarray:
    """中心差分对流 v·(u[i+1]-u[i-1])/(2 dx)，仅内部节点 [1..n-2]。"""
    n = len(u)
    adv = np.zeros_like(u)
    if v == 0.0 or n < 3:
        return adv
    adv[1:n-1] = v * (u[2:n] - u[0:n-2]) / (2.0 * dx)
    return adv


def solve_ftcs(alpha: float, nodes: int, dt: float, tEnd: float,
               length: float, u0: np.ndarray, left: BC, right: BC,
               advection_v: float, probes: list, record_every: int) -> dict:
    """显式 FTCS。条件稳定：r = alpha*dt/dx^2 <= 0.5（默认开启 CFL 保护）。

    统一约定：nodes = 网格点数，dx = L/(nodes-1)，所有数组长度 = nodes。
    """
    global _SHARED_BUF
    dx = _dx_length(length, nodes)
    r = alpha * dt / (dx * dx)
    peclet = advection_v * dx / alpha if advection_v != 0 else 0.0
    steps = int(round(tEnd / dt)) if tEnd > 0 else 0
    n = len(u0)  # = nodes

    u = u0.copy()
    if FAULTS.shared_state and _SHARED_BUF is not None:
        u = _SHARED_BUF.copy()

    blowup = False
    # 探针归一化坐标 p∈[0,1] → 索引 int(round(p*(n-1)))，范围 [0, n-1]
    probe_positions = [max(0, min(n - 1, int(round(p * (n - 1))))) for p in probes]
    probe_records = [{"x": probes[i], "points": [{"t": 0.0, "u": float(u[probe_positions[i]])}]} for i in range(len(probes))]

    initial_amp = abs(float(np.max(np.abs(u0)))) if u0.size else 1.0

    # CFL 保护：默认开启。QBC_FAULT_CFL_GUARD=off 时允许 r>0.5 进入不稳定区。
    if r > 0.5 and not FAULTS.cfl_guard_off:
        return {"steps": 0, "r": r, "peclet": peclet, "blowUp": True,
                "u_final": u, "probe_records": probe_records}

    for step in range(1, steps + 1):
        t = step * dt
        lap = _laplacian(u, dx, left, right)
        u_new = u.copy()
        # 内部节点 [1, n-2] 更新；端点由边界条件决定
        u_new[1:n-1] = u[1:n-1] + alpha * dt * lap[1:n-1] + advection_v * dt * (u[2:n] - u[0:n-2]) / (2.0 * dx)
        if left.kind == "dirichlet":
            u_new[0] = left.value
        if right.kind == "dirichlet":
            u_new[-1] = right.value
        if left.kind == "neumann":
            u_new[0] = u_new[1] - 2.0 * left.value * dx
        if right.kind == "neumann":
            u_new[-1] = u_new[-2] + 2.0 * right.value * dx
        u = u_new
        if _is_blowup(u, initial_amp):
            blowup = True
            break
        if record_every > 0 and step % record_every == 0:
            for i, pos in enumerate(probe_positions):
                probe_records[i]["points"].append({"t": t, "u": float(u[pos])})

    if FAULTS.shared_state:
        _SHARED_BUF = u.copy()

    return {"steps": step if steps > 0 else 0, "r": r, "peclet": peclet,
            "blowUp": blowup, "u_final": u, "probe_records": probe_records}


def solve_btcs(alpha: float, nodes: int, dt: float, tEnd: float,
               length: float, u0: np.ndarray, left: BC, right: BC,
               advection_v: float, probes: list, record_every: int) -> dict:
    """隐式 BTCS：三对角矩阵 Thomas 求解。无条件稳定，时间一阶。

    统一约定：nodes = 网格点数，dx = L/(nodes-1)，所有数组长度 = nodes。
    """
    dx = _dx_length(length, nodes)
    r = alpha * dt / (dx * dx)
    peclet = advection_v * dx / alpha if advection_v != 0 else 0.0
    steps = max(1, int(round(tEnd / dt))) if tEnd > 0 else 0
    u = u0.copy()
    n = len(u)  # = nodes
    blowup = False

    # 三对角系数（BTCS：u^{k+1} - r*(u[i+1] - 2u[i] + u[i-1]) = u^k）
    lower_base = np.full(n, -r)
    middle_base = np.full(n, 1.0 + 2.0 * r)
    upper_base = np.full(n, -r)
    lower_base[0] = 0.0
    upper_base[-1] = 0.0

    probe_positions = [max(0, min(n - 1, int(round(p * (n - 1))))) for p in probes]
    probe_records = [{"x": probes[i], "points": [{"t": 0.0, "u": float(u[probe_positions[i]])}]} for i in range(len(probes))]

    for step in range(1, steps + 1):
        t = step * dt
        lower = lower_base.copy()
        middle = middle_base.copy()
        upper = upper_base.copy()
        rhs = u.copy()
        # 边界处理
        if left.kind == "dirichlet":
            rhs[0] = left.value
            middle[0] = 1.0 + r
            lower[0] = 0.0
        if right.kind == "dirichlet":
            rhs[-1] = right.value
            middle[-1] = 1.0 + r
            upper[-1] = 0.0
        if left.kind == "neumann":
            rhs[0] = -left.value * dx
            lower[0] = -1.0
            middle[0] = 1.0
        if right.kind == "neumann":
            rhs[-1] = right.value * dx
            upper[-1] = -1.0
            middle[-1] = 1.0

        u_new = _thomas(lower, middle, upper, rhs)
        u = u_new
        if _is_blowup(u, abs(float(np.max(np.abs(u0)))) if u0.size else 1.0):
            blowup = True
            break
        if record_every > 0 and step % record_every == 0:
            for i, pos in enumerate(probe_positions):
                probe_records[i]["points"].append({"t": t, "u": float(u[pos])})

    return {"steps": step if steps > 0 else 0, "r": r, "peclet": peclet,
            "blowUp": blowup, "u_final": u, "probe_records": probe_records}


def _thomas(lower: np.ndarray, middle: np.ndarray, upper: np.ndarray,
            rhs: np.ndarray) -> np.ndarray:
    """Thomas 三对角求解。O(n) 时间，原地修改。"""
    n = len(rhs)
    cp = np.zeros(n)
    dp = np.zeros(n)
    cp[0] = upper[0] / middle[0]
    dp[0] = rhs[0] / middle[0]
    for i in range(1, n):
        denom = middle[i] - lower[i] * cp[i - 1]
        if i < n - 1:
            cp[i] = upper[i] / denom
        dp[i] = (rhs[i] - lower[i] * dp[i - 1]) / denom
    x = np.zeros(n)
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def solve_cn(alpha: float, nodes: int, dt: float, tEnd: float,
             length: float, u0: np.ndarray, left: BC, right: BC,
             advection_v: float, probes: list, record_every: int) -> dict:
    """Crank-Nicolson：二阶时间精度，无条件稳定。

    统一约定：nodes = 网格点数，dx = L/(nodes-1)，所有数组长度 = nodes。
    """
    dx = _dx_length(length, nodes)
    r = alpha * dt / (dx * dx)
    peclet = advection_v * dx / alpha if advection_v != 0 else 0.0
    steps = max(1, int(round(tEnd / dt))) if tEnd > 0 else 0
    u = u0.copy()
    n = len(u)  # = nodes
    blowup = False
    c = r / 2.0

    # CN： -c*u[i-1]^{k+1} + (1+2c)*u[i]^{k+1} - c*u[i+1]^{k+1}
    #      =  c*u[i-1]^k + (1-2c)*u[i]^k + c*u[i+1]^k
    lower_base = np.full(n, -c)
    middle_base = np.full(n, 1.0 + 2.0 * c)
    upper_base = np.full(n, -c)
    lower_base[0] = 0.0
    upper_base[-1] = 0.0

    probe_positions = [max(0, min(n - 1, int(round(p * (n - 1))))) for p in probes]
    probe_records = [{"x": probes[i], "points": [{"t": 0.0, "u": float(u[probe_positions[i]])}]} for i in range(len(probes))]

    for step in range(1, steps + 1):
        t = step * dt
        lower = lower_base.copy()
        middle = middle_base.copy()
        upper = upper_base.copy()
        # 右端：c*u[i-1]^k + (1-2c)*u[i]^k + c*u[i+1]^k（内部节点 [1, n-2]）
        rhs_new = np.zeros(n)
        rhs_new[1:n-1] = c * u[0:n-2] + (1.0 - 2.0 * c) * u[1:n-1] + c * u[2:n]
        # 端点：由边界条件决定
        if left.kind == "dirichlet":
            rhs_new[0] = left.value
            middle[0] = 1.0 + c
            lower[0] = 0.0
        else:
            rhs_new[0] = -left.value * dx
            lower[0] = -1.0
            middle[0] = 1.0
        if right.kind == "dirichlet":
            rhs_new[-1] = right.value
            middle[-1] = 1.0 + c
            upper[-1] = 0.0
        else:
            rhs_new[-1] = right.value * dx
            upper[-1] = -1.0
            middle[-1] = 1.0
        u_new = _thomas(lower, middle, upper, rhs_new)
        u = u_new
        if _is_blowup(u, abs(float(np.max(np.abs(u0)))) if u0.size else 1.0):
            blowup = True
            break
        if record_every > 0 and step % record_every == 0:
            for i, pos in enumerate(probe_positions):
                probe_records[i]["points"].append({"t": t, "u": float(u[pos])})

    return {"steps": step if steps > 0 else 0, "r": r, "peclet": peclet,
            "blowUp": blowup, "u_final": u, "probe_records": probe_records}


SOLVERS = {"ftcs": solve_ftcs, "btcs": solve_btcs, "cn": solve_cn}
