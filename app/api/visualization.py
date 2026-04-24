from __future__ import annotations

from fastapi import APIRouter

from app.storage.runtime import get_runtime

router = APIRouter(prefix="/visualization", tags=["visualization"])


@router.get("/state")
def visualization_state() -> dict:
    return get_runtime().visualization_state()

