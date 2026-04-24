from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import datasets, geofence, mapmatch, roads, route, spatial_query, visualization
from app.settings import settings
from app.storage.runtime import get_runtime

logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("hdmap_lab")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting HDMap-Lab runtime")
    get_runtime()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Spatial Algorithm Platform for Map and Trajectory Data",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router)
app.include_router(roads.router)
app.include_router(spatial_query.router)
app.include_router(geofence.router)
app.include_router(mapmatch.router)
app.include_router(route.router)
app.include_router(visualization.router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": 422,
                "message": "Request validation failed",
                "details": exc.errors(),
            }
        },
    )


@app.get("/health")
def health() -> dict:
    runtime = get_runtime()
    return {
        "status": "ok",
        "roads": len(runtime.roads),
        "nodes": len(runtime.nodes),
        "trajectories": len(runtime.trajectories),
    }


@app.get("/stats", tags=["stats"])
def stats() -> dict:
    runtime = get_runtime()
    return {
        "dataset": {
            "roads": len(runtime.roads),
            "nodes": len(runtime.nodes),
            "trajectories": len(runtime.trajectories),
            "geofences": len(runtime.geofences),
            "pois": len(runtime.pois),
        },
        "indexes": {
            "road_rtree": "ready" if runtime.roads else "empty",
            "road_kdtree": "ready" if runtime.roads else "empty",
            "road_graph": {
                "nodes": len(runtime.graph.nodes),
                "edges": sum(len(arcs) for arcs in runtime.graph.adjacency.values()),
            },
        },
    }
