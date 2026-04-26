from __future__ import annotations

from typing import Any


def ok(
    data: Any,
    metrics: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    debug_layers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "data": data,
        "metrics": metrics or {},
        "warnings": warnings or [],
        "debug_layers": debug_layers or {},
    }
