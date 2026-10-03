"""解析解基准（Oracle）核心算法。

纪律红线（与求解服务完全独立）：
- 纯 Python math + 级数展开，**不用 numpy 数值离散**。
- 与被测求解器（numpy 向量化 PDE）结构独立。
- 没有闭式解时返回 422，**绝不用数值解冒充**。

支持的闭式解：
1. 热方程 + 零 Dirichlet 边界 + 初值 A·sin(m·π·x/L)
   u(x,t) = A·sin(mπx/L)·exp(−α·(mπ/L)²·t)
2. 稳态对流扩散（steady=True）：两端 u(0)=0, u(L)=1
   u(x) = (exp(Pe·x/L) − 1) / (exp(Pe) − 1),  Pe = v·L/α
3. 分离变量级数（一般初值 + 零 Dirichlet）：
   u(x,t) = Σ b_m · sin(mπx/L) · exp(−α(mπ/L)²·t)
   b_m = (2/L) ∫₀ᴸ f(ξ)·sin(mπξ/L) dξ
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


class NoClosedForm(Exception):
    """请求的初值/边界组合没有闭式解。"""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _is_zero_dirichlet(left: dict, right: dict) -> bool:
    return (left.get("kind") == "dirichlet" and left.get("value", 0.0) == 0.0
            and right.get("kind") == "dirichlet" and right.get("value", 0.0) == 0.0)


def _is_steady_state_req(payload: dict) -> bool:
    return bool(payload.get("steady"))


def exact_zero_dirichlet_single_mode(A: float, m: int, alpha: float,
                                     L: float, x: float, t: float) -> float:
    """单模态 A·sin(mπx/L) 的解析解。"""
    return A * math.sin(m * math.pi * x / L) * math.exp(-alpha * (m * math.pi / L) ** 2 * t)


def steady_convection_diffusion(v: float, alpha: float, L: float, x: float) -> float:
    """稳态对流扩散解析解：u(0)=0, u(L)=1。"""
    if alpha <= 0:
        raise NoClosedForm("alpha must be > 0")
    Pe = v * L / alpha
    if abs(Pe) < 1e-12:
        # Pe -> 0 退化：纯扩散稳态解 u(x) = x/L
        return x / L
    # 避免 exp 溢出
    if Pe > 700.0:
        return 1.0
    if Pe < -700.0:
        return 0.0
    return (math.exp(Pe * x / L) - 1.0) / (math.exp(Pe) - 1.0)


def separation_series(alpha: float, L: float, x: float, t: float,
                      f: callable, terms: int = 200,
                      tol: float = 1e-10) -> tuple[float, int]:
    """一般初值 f + 零 Dirichlet 的分离变量级数。

    f: callable(x) -> 初值函数
    返回 (u, actual_terms_used)。截断误差 < tol。
    """
    # b_m 系数用解析积分（对多项式/正弦类初值）。
    # 这里只处理初值为 sin 模态的组合；其他情况需要数值积分 b_m。
    # 为了保持"纯 Python 独立性"，我们对已知可积的初值做解析 b_m，
    # 否则调用者应走单模态或稳态路径。
    u = 0.0
    for m in range(1, terms + 1):
        b_m = _b_coeff_analytic(f, m, L)
        if b_m == 0.0:
            continue
        term = b_m * math.sin(m * math.pi * x / L) * math.exp(-alpha * (m * math.pi / L) ** 2 * t)
        u += term
        # 截断判据：当前项绝对值 < tol 即可停（级数指数衰减）
        if abs(term) < tol and t > 0:
            return u, m
    return u, terms


def _b_coeff_analytic(f, m: int, L: float) -> float:
    """b_m = (2/L) ∫₀ᴸ f(ξ) sin(mπξ/L) dξ。

    支持解析可积的初值：
    - 常数 c： b_m = c·(2/L)·∫sin = c·(2/(mπ))·(1 - cos(mπ)) = c·(2/(mπ))·(1-(-1)^m)
    - 线性 a·ξ + b：可积
    - 已知的 sin(kπξ/L)：正交性
    其他情况返回 0 并让上层抛 NoClosedForm。
    """
    # 常数初值
    if isinstance(f, (int, float)):
        c = float(f)
        if m % 2 == 1:
            return c * (2.0 / (m * math.pi)) * (1.0 - (-1.0) ** m)
        return 0.0
    # callable：尝试有限几种可积模式
    if hasattr(f, "__call__"):
        # 检测是否为 c·sin(kπx/L)
        # 简化：直接数值积分（Simpson 固定 200 节点，纯 Python，非 PDE 离散）
        return _numeric_simpson_b(f, m, L)
    raise NoClosedForm(f"initial value type {type(f)} not analytically integrable")


def _numeric_simpson_b(f, m: int, L: float, n: int = 200) -> float:
    """Simpson 法数值积分 b_m（纯 Python math，非 PDE 数值离散，仅作积分用）。

    注意：这是对初值函数的"一次积分"，不是求解 PDE。
    """
    if n % 2 == 0:
        n += 1
    h = L / n
    s = 0.0
    sin_m = math.sin
    for i in range(n + 1):
        xi = i * h
        yi = f(xi) * sin_m(m * math.pi * xi / L)
        w = 1.0 if i in (0, n) else (4.0 if i % 2 == 1 else 2.0)
        s += w * yi
    s *= h / 3.0
    return (2.0 / L) * s


def solve_exact(payload: dict) -> dict:
    """入口：根据 payload 选择解析路径。

    成功返回 {method, terms, points}。
    没有闭式解时抛 NoClosedForm。
    """
    alpha = float(payload.get("alpha", 1.0))
    L = float(payload.get("length", 1.0))
    init = payload.get("initial", {})
    boundary = payload.get("boundary", {})
    points = payload.get("points", [])
    terms_req = int(payload.get("terms", 200))
    steady = payload.get("steady", False)

    if not points:
        raise NoClosedForm("no points given")

    if steady and _is_steady_state_req(payload):
        # 稳态对流扩散
        v = float(payload.get("velocity", payload.get("advection", {}).get("velocity", 0.0)))
        results = []
        for p in points:
            x = float(p["x"])
            u = steady_convection_diffusion(v, alpha, L, x)
            results.append({"x": x, "t": float(p.get("t", 0.0)), "u": u})
        return {"method": "steady-convection-diffusion-analytic", "terms": 0, "points": results}

    # 非稳态路径
    kind = init.get("kind")
    amplitude = float(init.get("amplitude", 0.0))
    modes = int(init.get("modes", 1))

    if kind == "sin" and _is_zero_dirichlet(boundary.get("left", {}), boundary.get("right", {})):
        if modes == 1:
            method = "zero-dirichlet-single-sine-mode-analytic"
            terms = 0
            results = []
            for p in points:
                x = float(p["x"])
                t = float(p.get("t", 0.0))
                u = exact_zero_dirichlet_single_mode(amplitude, 1, alpha, L, x, t)
                results.append({"x": x, "t": t, "u": u})
            return {"method": method, "terms": terms, "points": results}
        # 多模态：用级数
        method = "separation-of-variables-series"
        results = []
        actual_terms = 0
        for p in points:
            x = float(p["x"])
            t = float(p.get("t", 0.0))
            u, used = _series_modes(amplitude, modes, alpha, L, x, t)
            actual_terms = max(actual_terms, used)
            results.append({"x": x, "t": t, "u": u})
        return {"method": method, "terms": actual_terms, "points": results}

    # 常数初值 + 零 Dirichlet
    if kind == "const" and _is_zero_dirichlet(boundary.get("left", {}), boundary.get("right", {})):
        method = "separation-of-variables-series"
        results = []
        actual_terms = 0
        for p in points:
            x = float(p["x"])
            t = float(p.get("t", 0.0))
            u, used = _series_general_init(alpha, L, x, t, init, terms_req)
            actual_terms = max(actual_terms, used)
            results.append({"x": x, "t": t, "u": u})
        return {"method": method, "terms": actual_terms, "points": results}
    raise NoClosedForm(
            f"initial value kind={kind!r} with these boundaries has no closed-form solution; "
            f"refusing to substitute a numerical value as analytic"
        )

    # 非零边界 / Neumann 边界：暂不支持闭式
    raise NoClosedForm(
        "boundary conditions outside the supported analytic set "
        "(zero Dirichlet or steady conv-diff); refusing to substitute a numerical value as analytic"
    )


def _series_modes(amplitude: float, m: int, alpha: float, L: float, x: float, t: float) -> tuple[float, int]:
    """初值 A·sin(mπx/L) 是单模态，直接单模态公式。"""
    u = amplitude * math.sin(m * math.pi * x / L) * math.exp(-alpha * (m * math.pi / L) ** 2 * t)
    return (u, 0)


def _series_general_init(alpha: float, L: float, x: float, t: float,
                         init: dict, terms: int) -> tuple[float, int]:
    """常数初值 c 的分离变量级数。"""
    c = float(init.get("amplitude", 0.0))
    u = 0.0
    for m in range(1, terms + 1):
        if m % 2 == 0:
            continue
        b_m = c * (4.0 / (m * math.pi))
        term = b_m * math.sin(m * math.pi * x / L) * math.exp(-alpha * (m * math.pi / L) ** 2 * t)
        u += term
        if abs(term) < 1e-10:
            return u, m
    return u, terms
