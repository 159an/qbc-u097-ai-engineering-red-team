"""求解服务 FastAPI 入口（端口 8081）。

运行（仓库根目录）：
    python -m uvicorn services.solver.main:app --host 127.0.0.1 --port 8081
说明：services/ 作为命名空间包解析包内相对导入（from . import numerics）。
"""
from __future__ import annotations

import math
import time
import uuid
from typing import Any, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from . import numerics
from .faults import FAULTS

app = FastAPI(title="QBC 工程传热求解服务", version="1.0.0")

SERVICE_VERSION = "1.0.0"
# 单次求解硬超时（秒）。默认配置下应远小于 2 秒（nodes<=401, steps<=20000）。
SOLVE_TIMEOUT_SEC = float(120.0)


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "schemes": ["ftcs", "btcs", "cn"],
        "version": SERVICE_VERSION,
    }


def _err(code: str, message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": {"code": code, "message": message}})


def solve_direct(payload: dict) -> Any:
    """无 HTTP 层的纯函数入口：接收与 /solve 相同结构的 dict，
    返回 resp dict 或 _err(...) JSONResponse。供测试 / 脚本直连，无需起服务。
    """
    return _solve_core(payload)


def _solve_core(payload: dict) -> Any:
    """solve 的核心逻辑，可被 solve（HTTP 层）与 solve_direct（测试）复用。"""
    try:
        alpha = float(payload.get("alpha", 1.0))
        nodes = int(payload.get("nodes", 101))
        dt = float(payload.get("dt", 1e-4))
        tEnd = float(payload.get("tEnd", 0.05))
        length = float(payload.get("length", 1.0))
        scheme = str(payload.get("scheme", "ftcs")).lower()
        probes = [float(p) for p in (payload.get("probes") or [])]
        record_every = int(payload.get("recordEvery", 10))
        advection = payload.get("advection") or {}
        advection_v = float(advection.get("velocity", 0.0)) if advection.get("enabled") else 0.0
    except (TypeError, ValueError) as e:
        return _err("MALFORMED_REQUEST", f"bad numeric field: {e}")

    if FAULTS.silent_clamp and alpha < 0:
        alpha = abs(alpha)

    try:
        numerics.validate_params(alpha, nodes, dt, tEnd, length, probes, scheme)
    except numerics.ParamError as e:
        return _err(e.code, e.message)

    left = numerics.BC.parse(payload.get("boundary", {}).get("left"))
    right = numerics.BC.parse(payload.get("boundary", {}).get("right"))

    u0 = numerics.build_initial(
        str(payload.get("initial", {}).get("kind", "sin")),
        float(payload.get("initial", {}).get("amplitude", 1.0)),
        int(payload.get("initial", {}).get("modes", 1)),
        nodes, length,
    )

    solver = numerics.SOLVERS[scheme]
    t0 = time.monotonic()
    try:
        result = solver(alpha, nodes, dt, tEnd, length, u0, left, right,
                        advection_v, probes, record_every)
    except Exception as e:
        return _err("INTERNAL_SOLVER_ERROR", f"{type(e).__name__}: {e}", status=500)

    elapsed = time.monotonic() - t0

    u_final = result["u_final"]
    probe_records = result["probe_records"]
    n = nodes
    dx = length / n
    r = result["r"]
    peclet = result["peclet"]

    finite_mask = u_final[np.isfinite(u_final)]
    if finite_mask.size == 0:
        max_abs = math.inf
        min_u = math.nan
        max_u = math.nan
    else:
        max_abs = float(np.max(np.abs(finite_mask)))
        min_u = float(np.min(finite_mask))
        max_u = float(np.max(finite_mask))

    blowup = result["blowUp"]
    incomplete = False
    if elapsed > SOLVE_TIMEOUT_SEC and FAULTS.partial_on_timeout:
        pass
    elif elapsed > SOLVE_TIMEOUT_SEC:
        incomplete = True

    resp: dict[str, Any] = {
        "taskId": f"t-{uuid.uuid4().hex[:8]}",
        "status": "completed",
        "numerics": {
            "dx": dx, "dt": dt, "r": r, "peclet": peclet,
            "steps": result["steps"],
        },
        "probes": [
            {"x": rec["x"], "points": rec["points"]} for rec in probe_records
        ],
        "summary": {
            "maxAbsU": max_abs, "minU": min_u, "maxU": max_u, "blowUp": blowup,
        },
    }
    if incomplete:
        resp["incomplete"] = True
    return resp


@app.post("/solve")
async def solve(payload: dict, request: Request) -> Any:
    """POST /solve：HTTP 层薄封装，核心逻辑在 _solve_core。"""
    return _solve_core(payload)
