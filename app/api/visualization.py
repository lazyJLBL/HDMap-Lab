from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.storage.runtime import get_runtime

router = APIRouter(prefix="/visualization", tags=["visualization"])


@router.get("/state")
def visualization_state() -> dict:
    return get_runtime().visualization_state()


@router.get("/export")
def visualization_export() -> dict:
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "format": "geojson-layer-bundle",
        "layers": get_runtime().visualization_state(),
    }
