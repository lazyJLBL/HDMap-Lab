from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import datasets, geofence, mapmatch, roads, route, spatial_query, visualization
from app.storage.runtime import get_runtime


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_runtime()
    yield


app = FastAPI(
    title="HDMap-Lab",
    description="Spatial Algorithm Platform for Map and Trajectory Data",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/health")
def health() -> dict:
    runtime = get_runtime()
    return {
        "status": "ok",
        "roads": len(runtime.roads),
        "nodes": len(runtime.nodes),
        "trajectories": len(runtime.trajectories),
    }
