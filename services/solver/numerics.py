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
    目前支持 'sin'：A·sin(m·π·x/L)。'const'：常数场。其他 kind 暂不支持，返回全 0。
    """
    if kind == "sin":
        x = np.linspace(0.0, length, nodes)
        return amplitude * np.sin(modes * math.pi * x / length)
    if kind == "const":
        return np.full(nodes, float(amplitude))
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
    """二阶中心差分 Laplacian，对全部节点（端点 + 内部）。

    n = len(u) = 网格点数；最后下标 n-1。
    端点处理统一用二阶镜像幽灵点（u[-1]=u[1], u[N]=u[N-2]）：
      左端 i=0:  lap[0] = (u[1] - 2u[0] + u[-1])/dx² = (2u[1] - 2u[0] - g_L·dx·2)/dx²
                  g=0 时 lap[0] = (2u[1] - 2u[0])/dx²（任务书：二阶镜像幽灵点）
      右端 i=n-1: lap[-1] = (u[n-2] - 2u[n-1] + u[n])/dx²
                  g=0 时 lap[-1] = (2u[n-2] - 2u[n-1])/dx²
    """
    n = len(u)  # 网格点数；下标 0..n-1，内部 1..n-2
    lap = np.zeros_like(u)
    if left.kind == "dirichlet" and right.kind == "dirichlet":
        # 内部：(u[i-1] - 2u[i] + u[i+1]) / dx^2
        lap[1:n-1] = (u[0:n-2] - 2.0 * u[1:n-1] + u[2:n]) / (dx * dx)
        # Dirichlet 端点已知值直接代入，不参与 Laplacian 更新
        lap[0] = 0.0
        lap[-1] = 0.0
    elif left.kind == "neumann" and right.kind == "neumann":
        gl = ghosts[0] if ghosts else 0.0
        gr = ghosts[1] if ghosts else 0.0
        # 二阶镜像幽灵点（g=0）：u[-1]=u[1], u[N]=u[N-2]
        # 左端 i=0: (u[1] - 2u[0] + u[-1])/dx², 镜像 u[-1]=u[1]
        lap[0] = (2.0 * u[1] - 2.0 * u[0]) / (dx * dx)
        # 右端 i=n-1: (u[n-2] - 2u[n-1] + u[n])/dx², 镜像 u[n]=u[n-2]
        lap[-1] = (2.0 * u[-2] - 2.0 * u[-1]) / (dx * dx)
        # 非零梯度 g_L：幽灵点偏移 g_L·dx，lap[0] = (u[1] - 2u[0] + (u[1]-2*g_L*dx))/(dx*dx)
        if gl != 0.0:
            lap[0] = (2.0 * u[1] - 2.0 * u[0] - 2.0 * gl * dx) / (dx * dx)
        if gr != 0.0:
            lap[-1] = (2.0 * u[-2] - 2.0 * u[-1] + 2.0 * gr * dx) / (dx * dx)
        # 内部
        lap[1:n-1] = (u[0:n-2] - 2.0 * u[1:n-1] + u[2:n]) / (dx * dx)
    else:
        # 混合边界，简化处理（端点用各自类型，内部不变）
        if left.kind == "neumann":
            gl = ghosts[0] if ghosts else 0.0
            # 二阶镜像幽灵点：(2u[1] - 2u[0]) / dx²（g=0）
            lap[0] = (2.0 * u[1] - 2.0 * u[0] - 2.0 * gl * dx) / (dx * dx)
        else:
            lap[0] = 0.0
        if right.kind == "neumann":
            gr = ghosts[1] if ghosts else 0.0
            lap[-1] = (2.0 * u[-2] - 2.0 * u[-1] + 2.0 * gr * dx) / (dx * dx)
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
        lap = _laplacian(u, dx, left, right, ghosts=(0.0, 0.0))
        u_new = u.copy()
        # 内部节点 [1, n-2] 更新；Neumann 端点行用二阶镜像幽灵点（任务书 4.1）：
        #   i=0:  lap[0]  = (2u[1] - 2u[0]) / dx²（g=0，二阶镜像幽灵点）
        #   i=n-1: lap[-1] = (2u[n-2] - 2u[n-1]) / dx²
        # 对流-扩散：∂u/∂t = alpha*u'' - v*u'（v 向 +x 输送，下游消耗）
        # 中心差：u' ≈ (u[i+1]-u[i-1])/(2dx)，故对流项 = -v*dt*(u[i+1]-u[i-1])/(2dx)
        u_new[1:n-1] = u[1:n-1] + alpha * dt * lap[1:n-1] - advection_v * dt * (u[2:n] - u[0:n-2]) / (2.0 * dx)
        if left.kind == "dirichlet":
            u_new[0] = left.value
        if right.kind == "dirichlet":
            u_new[-1] = right.value
        # Neumann 端点行：二阶镜像幽灵点 FTCS（端点按 PDE 更新，而非一阶单侧赋值）
        #   u_new[0]  = u[0] + alpha*dt*lap[0]   （lap[0]=(2u[1]-2u[0])/dx²，g=0）
        #   u_new[-1] = u[-1]+ alpha*dt*lap[-1]  （lap[-1]=(2u[n-2]-2u[n-1])/dx²，g=0）
        # 这套离散的精确守恒量是有限体积端点半权 H_fvm = dx*(0.5u[0]+Σu[1:-1]+0.5u[-1])
        if left.kind == "neumann":
            u_new[0] = u[0] + alpha * dt * lap[0]
        if right.kind == "neumann":
            u_new[-1] = u[-1] + alpha * dt * lap[-1]
        u = u_new
        if _is_blowup(u, initial_amp):
            blowup = True
            break
        if record_every > 0 and step % record_every == 0:
            for i, pos in enumerate(probe_positions):
                probe_records[i]["points"].append({"t": t, "u": float(u[pos])})
    # 探针末点修正（回归：record_every > steps 时旧实现只记到 t=0，违反「三格式返回 t=tEnd 探针值」约定）
    # 循环内已按 record_every 步长 append；循环后无条件补一个 t=steps*dt 的终态探针，
    # 与循环内已 append 的 t=steps*dt 末点重复时是同一时刻的重复值（幂等，不破坏精度）。
    # 以 t 字段去重：若最后一个点已等于 t_last，则不再追加（避免 pts[-1] 前多一个 t=tEnd 重复项）
    if steps > 0:
        t_last = steps * dt
        for i, pos in enumerate(probe_positions):
            pts = probe_records[i]["points"]
            if not pts or abs(pts[-1]["t"] - t_last) > 1e-12:
                pts.append({"t": t_last, "u": float(u[pos])})

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

    # BTCS 后向欧拉全隐式（∂u/∂t = alpha·u'' − v·u'）：
    #   [ I − dt·alpha·L2 + dt·v·L1 ] u^{k+1} = u^k
    #   L2(u)_i=(u[i-1]-2u[i]+u[i+1])/dx², L1(u)_i=(u[i+1]-u[i-1])/(2dx)
    # 记 r = alpha·dt/dx², c_adv = v·dt/(2dx) = 0.5·r·Pe_cell（内部行）：
    #   lower[i]  = −r − c_adv   （u[i-1] 项）
    #   middle[i] = 1 + 2r
    #   upper[i]  = −r + c_adv   （u[i+1] 项）
    c_adv = 0.5 * r * peclet  # = v*dt/(2dx)

    lower_base = np.full(n, -r - c_adv)
    middle_base = np.full(n, 1.0 + 2.0 * r)
    upper_base = np.full(n, -r + c_adv)
    lower_base[0] = 0.0
    upper_base[-1] = 0.0

    # 边界处理只用「端点单位行」一套机制（与内部行系数分离，绝不混用移项）：
    # Dirichlet：端点行退化为单位行（middle=1, lower=upper=0, rhs=g），u[0]=g、u[-1]=g
    # 每步精确成立、不随 dt/L 漂移；内部行的 lower[1]·u[0]、upper[n-2]·u[-1]
    # 由 Thomas 全系统直接求解，端点值经单位行锁定为 g，无需再向 rhs 移项。
    # Neumann：端点行用单侧二阶差分（lower[0]=−1 / upper[−1]=−1, middle=1），rhs=∓g·dx。

    probe_positions = [max(0, min(n - 1, int(round(p * (n - 1))))) for p in probes]
    probe_records = [{"x": probes[i], "points": [{"t": 0.0, "u": float(u[probe_positions[i]])}]} for i in range(len(probes))]

    for step in range(1, steps + 1):
        t = step * dt
        lower = lower_base.copy()
        middle = middle_base.copy()
        upper = upper_base.copy()
        rhs = u.copy()
        # 边界行覆盖（端点单位行 / Neumann 行）
        if left.kind == "dirichlet":
            rhs[0] = left.value
            lower[0] = 0.0
            middle[0] = 1.0
            upper[0] = 0.0
        if right.kind == "dirichlet":
            rhs[-1] = right.value
            lower[-1] = 0.0
            middle[-1] = 1.0
            upper[-1] = 0.0
        if left.kind == "neumann":
            # 二阶镜像幽灵点 BTCS 端点行 i=0：
            #   LHS: (1+2r)u[0]^{k+1} - 2r·u[1]^{k+1}  =>  middle[0]=1+2r, upper[0]=-2r, lower[0]=0
            #   RHS: u[0]^k  =>  rhs[0]=u[0]^k（g=0）；g≠0 时 rhs 加 2r·dx·g_L（镜像偏移）
            rhs[0] = u[0]
            if left.value != 0.0:
                rhs[0] += 2.0 * r * left.value * dx
            lower[0] = 0.0
            middle[0] = 1.0 + 2.0 * r
            upper[0] = -2.0 * r
        if right.kind == "neumann":
            # 二阶镜像幽灵点 BTCS 端点行 i=n-1：
            #   LHS: -2r·u[n-2]^{k+1} + (1+2r)u[n-1]^{k+1}  =>  middle[-1]=1+2r, lower[-1]=-2r, upper[-1]=0
            #   RHS: u[n-1]^k（g=0）；g≠0 时 rhs 加 2r·dx·g_R
            rhs[-1] = u[-1]
            if right.value != 0.0:
                rhs[-1] += 2.0 * r * right.value * dx
            lower[-1] = -2.0 * r
            middle[-1] = 1.0 + 2.0 * r
            upper[-1] = 0.0

        u_new = _thomas(lower, middle, upper, rhs)
        u = u_new
        if _is_blowup(u, abs(float(np.max(np.abs(u0)))) if u0.size else 1.0):
            blowup = True
            break
        if record_every > 0 and step % record_every == 0:
            for i, pos in enumerate(probe_positions):
                probe_records[i]["points"].append({"t": t, "u": float(u[pos])})
    # 探针末点修正（回归：record_every > steps 时旧实现只记到 t=0，违反「三格式返回 t=tEnd 探针值」约定）
    # 循环内已按 record_every 步长 append；循环后无条件补 t=steps*dt 终态探针，
    # 以 t 字段去重，避免与循环内已 append 的 t=tEnd 末点重复。
    if steps > 0:
        t_last = steps * dt
        for i, pos in enumerate(probe_positions):
            pts = probe_records[i]["points"]
            if not pts or abs(pts[-1]["t"] - t_last) > 1e-12:
                pts.append({"t": t_last, "u": float(u[pos])})

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

    # CN：扩散+对流（二阶时间，时间精度 O(dt²)）：
    #   LHS: (-c-c_adv) u[i-1]^{k+1} + (1+2c) u[i]^{k+1} + (-c+c_adv) u[i+1]^{k+1}
    #   RHS: (c+c_adv) u[i-1]^k + (1-2c) u[i]^k + (c-c_adv) u[i+1]^k
    # 推导：CN 取 LHS=(I+dt/2·A_R), A_R = αL2 − vL1；RHS=(I−dt/2·A_L), A_L = αL2 − vL1。
    # 扩散半权 c = alpha·dt/(2dx²) = r/2；对流半权 c_adv = v·dt/(4dx) = 0.25·r·Pe_cell。
    # LHS u[i-1] 系数：−c−c_adv；u[i+1] 系数：−c+c_adv（左端系数正确）。
    # RHS u[i-1] 系数：c+c_adv；u[i+1] 系数：c−c_adv（右端符号与 LHS 相反，注意勿写反）。
    c = r / 2.0
    c_adv = 0.25 * r * peclet  # = v*dt/(4dx)
    # 内部三对角系数（端点行在循环内覆盖；镜像幽灵点下两端对角系数为 ±2c，内部为 ±c）
    lower_base = np.full(n, -c - c_adv)
    middle_base = np.full(n, 1.0 + 2.0 * c)
    upper_base = np.full(n, -c + c_adv)
    lower_base[0] = 0.0
    upper_base[-1] = 0.0

    probe_positions = [max(0, min(n - 1, int(round(p * (n - 1))))) for p in probes]
    probe_records = [{"x": probes[i], "points": [{"t": 0.0, "u": float(u[probe_positions[i]])}]} for i in range(len(probes))]

    for step in range(1, steps + 1):
        t = step * dt
        lower = lower_base.copy()
        middle = middle_base.copy()
        upper = upper_base.copy()
        # 右端（显式）：内部行用 (I−cA+cbL1)u^k 的三对角公式
        #   b=c_adv=v·dt/(4dx)；内部 [1, n-2]；端点由下段边界条件决定
        rhs_new = np.zeros(n)
        rhs_new[1:n-1] = (c + c_adv) * u[0:n-2] + (1.0 - 2.0 * c) * u[1:n-1] + (c - c_adv) * u[2:n]
        # 端点：由边界条件决定
        if left.kind == "dirichlet":
            rhs_new[0] = left.value
            lower[0] = 0.0
            middle[0] = 1.0
            upper[0] = 0.0
        else:
            # 二阶镜像幽灵点 CN 端点行 i=0（v=0 时端点行对流贡献恒 0，无需 c_adv）：
            #   LHS: (1+2c)u[0]^{k+1} - 2c·u[1]^{k+1}  =>  middle[0]=1+2c, upper[0]=-2c, lower[0]=0
            #   RHS: (I-cA)_row0 · u^k = u[0]^k - c·(u[0]-2u[1]+u[-1])^k，镜像 u[-1]=u[1]
            #       = u[0]^k + c·(2u[1]^k - 2u[0]^k)
            #   g≠0 时镜像幽灵点偏移 g_L·dx：rhs 加 2c·dx·g_L
            rhs_new[0] = u[0] + c * (2.0 * u[1] - 2.0 * u[0])
            if left.value != 0.0:
                rhs_new[0] += 2.0 * c * left.value * dx
            lower[0] = 0.0
            middle[0] = 1.0 + 2.0 * c
            upper[0] = -2.0 * c
        if right.kind == "dirichlet":
            rhs_new[-1] = right.value
            lower[-1] = 0.0
            middle[-1] = 1.0
            upper[-1] = 0.0
        else:
            # 二阶镜像幽灵点 CN 端点行 i=n-1（v=0 时端点行对流贡献恒 0）：
            #   LHS: -2c·u[n-2]^{k+1} + (1+2c)u[n-1]^{k+1}  =>  middle[-1]=1+2c, lower[-1]=-2c, upper[-1]=0
            #   RHS: u[-1]^k + c·(2u[-2]^k - 2u[-1]^k)（镜像 u[n]=u[n-2]）
            #   g≠0 时加 2c·dx·g_R
            rhs_new[-1] = u[-1] + c * (2.0 * u[-2] - 2.0 * u[-1])
            if right.value != 0.0:
                rhs_new[-1] += 2.0 * c * right.value * dx
            lower[-1] = -2.0 * c
            middle[-1] = 1.0 + 2.0 * c
            upper[-1] = 0.0
        u_new = _thomas(lower, middle, upper, rhs_new)
        u = u_new
        if _is_blowup(u, abs(float(np.max(np.abs(u0)))) if u0.size else 1.0):
            blowup = True
            break
        if record_every > 0 and step % record_every == 0:
            for i, pos in enumerate(probe_positions):
                probe_records[i]["points"].append({"t": t, "u": float(u[pos])})
    # 探针末点修正（回归：record_every > steps 时旧实现只记到 t=0，违反「三格式返回 t=tEnd 探针值」约定）
    # 循环内已按 record_every 步长 append；循环后无条件补 t=steps*dt 终态探针，
    # 以 t 字段去重，避免与循环内已 append 的 t=tEnd 末点重复。
    if steps > 0:
        t_last = steps * dt
        for i, pos in enumerate(probe_positions):
            pts = probe_records[i]["points"]
            if not pts or abs(pts[-1]["t"] - t_last) > 1e-12:
                pts.append({"t": t_last, "u": float(u[pos])})

    return {"steps": step if steps > 0 else 0, "r": r, "peclet": peclet,
            "blowUp": blowup, "u_final": u, "probe_records": probe_records}


SOLVERS = {"ftcs": solve_ftcs, "btcs": solve_btcs, "cn": solve_cn}
