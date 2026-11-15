from __future__ import annotations

from fastapi import Request

from app.runtime import Runtime


def get_runtime(request: Request) -> Runtime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise RuntimeError("Runtime not initialised")
    return runtime
