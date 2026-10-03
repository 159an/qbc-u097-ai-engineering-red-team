"""解析解基准服务（Oracle）FastAPI 入口（端口 8082）。

红线：
- 纯确定性，**无任何 LLM/AI 调用**。
- 与被测求解服务结构独立（纯 Python math，非 numpy 数值离散）。
- 无闭式解时返回 422，**绝不返回数值解冒充解析解**。

运行（仓库根目录）：
    python -m uvicorn services.oracle.main:app --host 127.0.0.1 --port 8082
说明：services/ 作为命名空间包解析包内相对导入。
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import exact
from .exact import NoClosedForm

app = FastAPI(title="QBC 解析解基准服务 (Oracle)", version="1.0.0")

SERVICE_VERSION = "1.0.0"


@app.get("/health")
def health() -> dict:
    return {"ok": True, "method": "analytic-exact", "version": SERVICE_VERSION}


def _err(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": {"code": code, "message": message}})


@app.post("/exact")
async def exact_endpoint(payload: dict) -> Any:
    # 参数基本校验
    try:
        alpha = float(payload.get("alpha", 1.0))
        length = float(payload.get("length", 1.0))
        if alpha <= 0:
            return _err("INVALID_ALPHA", "alpha must be > 0", 400)
        if length <= 0:
            return _err("INVALID_LENGTH", "length must be > 0", 400)
        points = payload.get("points") or []
        if not points:
            return _err("NO_POINTS", "at least one point required", 400)
        for p in points:
            x = float(p.get("x"))
            if x < 0 or x > 1.0:
                return _err("POINT_OUT_OF_RANGE",
                            f"x must be in [0,1] (normalized), got {x}", 400)
    except (TypeError, ValueError) as e:
        return _err("MALFORMED_REQUEST", f"bad field: {e}", 400)

    try:
        result = exact.solve_exact(payload)
        return result
    except NoClosedForm as e:
        return _err("NO_CLOSED_FORM", e.reason, 422)
    except Exception as e:
        return _err("INTERNAL_ORACLE_ERROR", f"{type(e).__name__}: {e}", 500)
