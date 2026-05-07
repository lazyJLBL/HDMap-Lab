from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.response import ok
from app.geometry_kernel.case_gallery import (
    cases_to_feature_collection,
    load_geometry_cases,
    run_all_geometry_cases,
    run_geometry_case,
)

router = APIRouter(prefix="/geometry", tags=["geometry"])


@router.get("/cases")
def geometry_cases() -> dict[str, Any]:
    cases = load_geometry_cases()
    return ok(
        cases,
        metrics={"total": len(cases)},
        debug_layers={"cases": cases_to_feature_collection(cases)},
    )


@router.post("/cases/run")
def geometry_case_run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    cases = load_geometry_cases()
    case: dict[str, Any] | None = payload.get("case")
    case_id = payload.get("case_id")
    if case is None and case_id:
        case = next((candidate for candidate in cases if candidate.get("id") == case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail="Geometry case not found. Pass case_id or case.")

    result = run_geometry_case(case)
    return ok(
        result,
        metrics={"passed": int(result["passed"]), "failed": int(not result["passed"])},
        warnings=result["reasons"],
        debug_layers=result["debug_layers"],
    )


@router.post("/cases/run-all")
def geometry_cases_run_all() -> dict[str, Any]:
    payload = run_all_geometry_cases()
    return ok(
        payload["results"],
        metrics=payload["summary"],
        warnings=[f"{case_id} failed" for case_id in payload["summary"]["failed_cases"]],
        debug_layers={"cases": cases_to_feature_collection()},
    )
