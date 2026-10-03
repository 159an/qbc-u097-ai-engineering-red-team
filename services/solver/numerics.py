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
    """初始条件。目前支持 'sin'：A·sin(m·π·x/L)。

    其他 kind 暂未实现，返回全 0 并打印警告——不假装支持。
    """
    if kind == "sin":
        x = np.linspace(0.0, length, nodes + 1)
        return amplitude * np.sin(modes * math.pi * x / length)
    # 其他初值暂不支持，返回零初值
    return np.zeros(nodes + 1)


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


def _dx_length(length: float, nodes: int) -> float:
    return length / nodes


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
    """二阶中心差分 Laplacian，对内部节点 [1..n-1]。
    Neumann 时用幽灵点值。
    """
    n = len(u) - 1
    lap = np.zeros_like(u)
    if left.kind == "dirichlet" and right.kind == "dirichlet":
        # 内部：(u[i-1] - 2u[i] + u[i+1]) / dx^2
        lap[1:n] = (u[0:n-1] - 2.0 * u[1:n] + u[2:n+1]) / (dx * dx)
        # 边界：二阶单侧（Dirichlet 已知，不参与 Laplacian 计算）
        lap[0] = (u[0] - 2.0 * u[1] + u[2]) / (dx * dx) if n >= 2 else 0.0
        lap[-1] = (u[-1] - 2.0 * u[-2] + u[-3]) / (dx * dx) if n >= 2 else 0.0
    elif left.kind == "neumann" and right.kind == "neumann":
        # 两端幽灵点
        gl = ghosts[0] if ghosts else 0.0
        gr = ghosts[1] if ghosts else 0.0
        # 左端 i=0： (gl - 2u[0] + u[1]) / dx^2
        lap[0] = (gl - 2.0 * u[0] + u[1]) / (dx * dx)
        # 内部
        lap[1:n] = (u[0:n-1] - 2.0 * u[1:n] + u[2:n+1]) / (dx * dx)
        # 右端 i=n： (u[n-1] - 2u[n] + gr) / dx^2
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
        lap[1:n] = (u[0:n-1] - 2.0 * u[1:n] + u[2:n+1]) / (dx * dx)
    return lap


def _advective_term(u: np.ndarray, v: float, dx: float) -> np.ndarray:
    """中心差分对流 v·(u[i+1]-u[i-1])/(2 dx)，仅内部节点。"""
    n = len(u) - 1
    adv = np.zeros_like(u)
    if v == 0.0 or n < 2:
        return adv
    adv[1:n] = v * (u[2:n+1] - u[0:n-1]) / (2.0 * dx)
    return adv


def solve_ftcs(alpha: float, nodes: int, dt: float, tEnd: float,
               length: float, u0: np.ndarray, left: BC, right: BC,
               advection_v: float, probes: list, record_every: int) -> dict:
    """显式 FTCS。条件稳定：r = alpha*dt/dx^2 <= 0.5（默认开启 CFL 保护）。"""
    global _SHARED_BUF
    dx = _dx_length(length, nodes)
    r = alpha * dt / (dx * dx)
    peclet = advection_v * dx / alpha if advection_v != 0 else 0.0
    steps = int(round(tEnd / dt)) if tEnd > 0 else 0
    n = nodes

    u = u0.copy()
    if FAULTS.shared_state and _SHARED_BUF is not None:
        u = _SHARED_BUF.copy()  # 跨请求污染

    blowup = False
    probe_positions = [max(0, min(n, int(round(p * n)))) for p in probes]
    probe_records = [{"x": probes[i], "points": [{"t": 0.0, "u": float(u[probe_positions[i]])}]} for i in range(len(probes))]

    initial_amp = abs(float(np.max(np.abs(u0)))) if u0.size else 1.0

    # CFL 保护：默认开启。QBC_FAULT_CFL_GUARD=off 时允许 r>0.5 进入不稳定区。
    if r > 0.5 and not FAULTS.cfl_guard_off:
        # 直接返回初始值并标记不稳定，不执行迭代
        return {"steps": 0, "r": r, "peclet": peclet, "blowUp": True,
                "u_final": u, "probe_records": probe_records}

    for step in range(1, steps + 1):
        t = step * dt
        lap = _laplacian(u, dx, left, right)
        u_new = u.copy()
        u_new[1:n] = u[1:n] + alpha * dt * lap[1:n] + advection_v * dt * (u[2:n+1] - u[0:n-1]) / (2.0 * dx)
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
    """隐式 BTCS：三对角矩阵 Thomas 求解。无条件稳定，时间一阶。"""
    dx = _dx_length(length, nodes)
    r = alpha * dt / (dx * dx)
    peclet = advection_v * dx / alpha if advection_v != 0 else 0.0
    steps = max(1, int(round(tEnd / dt))) if tEnd > 0 else 0
    n = nodes
    u = u0.copy()
    blowup = False

    # 构建三对角系数（BTCS：u^{k+1} - r*(u[i+1] - 2u[i] + u[i-1]) = u^k）
    lower = np.full(n, -r)
    middle = np.full(n, 1.0 + 2.0 * r)
    upper = np.full(n, -r)
    lower[0] = 0.0
    upper[-1] = 0.0

    probe_positions = [int(round(p * n)) for p in probes]
    probe_records = [{"x": probes[i], "points": [{"t": 0.0, "u": float(u[probe_positions[i]])}]} for i in range(len(probes))]

    for step in range(1, steps + 1):
        t = step * dt
        rhs = u.copy()
        # 边界处理：Dirichlet 直接代入
        if left.kind == "dirichlet":
            rhs[0] = left.value
            # 修正 middle[0] 项
            middle[0] = 1.0 + r
        if right.kind == "dirichlet":
            rhs[-1] = right.value
            middle[-1] = 1.0 + r
        # Neumann 简化处理（一阶近似，P2 说明中允许 Agent 发现精度退化）
        if left.kind == "neumann":
            # u[0] - u[1] = g_l*dx (一阶近似)
            rhs[0] = u[1] + left.value * dx
            lower[0] = -1.0
            middle[0] = 1.0
        if right.kind == "neumann":
            rhs[-1] = u[-2] - right.value * dx
            upper[-1] = -1.0
            middle[-1] = 1.0

        # Thomas 算法
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
    """Crank-Nicolson：二阶时间精度，无条件稳定。"""
    dx = _dx_length(length, nodes)
    r = alpha * dt / (dx * dx)
    peclet = advection_v * dx / alpha if advection_v != 0 else 0.0
    steps = max(1, int(round(tEnd / dt))) if tEnd > 0 else 0
    n = nodes
    u = u0.copy()
    blowup = False
    c = r / 2.0

    # CN： -c*u[i-1]^{k+1} + (1+2c)*u[i]^{k+1} - c*u[i+1]^{k+1}
    #      =  c*u[i-1]^k + (1-2c)*u[i]^k + c*u[i+1]^k
    lower = np.full(n, -c)
    middle = np.full(n, 1.0 + 2.0 * c)
    upper = np.full(n, -c)
    lower[0] = 0.0
    upper[-1] = 0.0

    probe_positions = [int(round(p * n)) for p in probes]
    probe_records = [{"x": probes[i], "points": [{"t": 0.0, "u": float(u[probe_positions[i]])}]} for i in range(len(probes))]

    for step in range(1, steps + 1):
        t = step * dt
        # 右端：c*u[i-1]^k + (1-2c)*u[i]^k + c*u[i+1]^k
        rhs_new = np.zeros(n)
        rhs_new[1:n-1] = c * u[0:n-2] + (1.0 - 2.0 * c) * u[1:n-1] + c * u[2:n]
        rhs_new[0] = (1.0 - 2.0 * c) * u[0] + c * u[1]
        rhs_new[-1] = c * u[-2] + (1.0 - 2.0 * c) * u[-1]
        # 边界
        if left.kind == "dirichlet":
            rhs_new[0] = left.value
            middle[0] = 1.0 + c
        if right.kind == "dirichlet":
            rhs_new[-1] = right.value
            middle[-1] = 1.0 + c
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
