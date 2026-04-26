from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from app.models import POI, GeoFence, RoadEdge, RoadNode, Trajectory, TrajectoryPoint


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS road_nodes (
                id TEXT PRIMARY KEY,
                lon REAL NOT NULL,
                lat REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS road_edges (
                id TEXT PRIMARY KEY,
                from_node TEXT NOT NULL,
                to_node TEXT NOT NULL,
                geometry_json TEXT NOT NULL,
                length REAL NOT NULL,
                speed_limit REAL NOT NULL,
                road_type TEXT NOT NULL,
                oneway INTEGER NOT NULL,
                direction TEXT NOT NULL DEFAULT 'both',
                road_class TEXT NOT NULL DEFAULT 'local',
                lane_count INTEGER NOT NULL DEFAULT 1,
                turn_restrictions_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS trajectories (
                id TEXT PRIMARY KEY,
                points_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS geofences (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                geometry_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pois (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                lon REAL NOT NULL,
                lat REAL NOT NULL,
                properties_json TEXT NOT NULL
            );
            """
        )
        self._ensure_road_edge_columns()
        self._conn.commit()

    def _ensure_road_edge_columns(self) -> None:
        rows = self._conn.execute("PRAGMA table_info(road_edges)").fetchall()
        columns = {row["name"] for row in rows}
        migrations = {
            "direction": "ALTER TABLE road_edges ADD COLUMN direction TEXT NOT NULL DEFAULT 'both'",
            "road_class": "ALTER TABLE road_edges ADD COLUMN road_class TEXT NOT NULL DEFAULT 'local'",
            "lane_count": "ALTER TABLE road_edges ADD COLUMN lane_count INTEGER NOT NULL DEFAULT 1",
            "turn_restrictions_json": "ALTER TABLE road_edges ADD COLUMN turn_restrictions_json TEXT NOT NULL DEFAULT '[]'",
            "metadata_json": "ALTER TABLE road_edges ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'",
        }
        for column, statement in migrations.items():
            if column not in columns:
                self._conn.execute(statement)

    def clear(self) -> None:
        self._conn.executescript(
            """
            DELETE FROM road_nodes;
            DELETE FROM road_edges;
            DELETE FROM trajectories;
            DELETE FROM geofences;
            DELETE FROM pois;
            """
        )
        self._conn.commit()

    def replace_all(
        self,
        nodes: Iterable[RoadNode],
        roads: Iterable[RoadEdge],
        trajectories: Iterable[Trajectory],
        geofences: Iterable[GeoFence],
        pois: Iterable[POI],
    ) -> None:
        self.clear()
        self.upsert_nodes(nodes)
        self.upsert_roads(roads)
        self.upsert_trajectories(trajectories)
        self.upsert_geofences(geofences)
        self.upsert_pois(pois)

    def upsert_nodes(self, nodes: Iterable[RoadNode]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO road_nodes(id, lon, lat) VALUES (?, ?, ?)",
            [(node.id, node.lon, node.lat) for node in nodes],
        )
        self._conn.commit()

    def upsert_roads(self, roads: Iterable[RoadEdge]) -> None:
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO road_edges
                (id, from_node, to_node, geometry_json, length, speed_limit, road_type, oneway,
                 direction, road_class, lane_count, turn_restrictions_json, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    road.id,
                    road.from_node,
                    road.to_node,
                    json.dumps(road.geometry),
                    road.length,
                    road.speed_limit,
                    road.road_type,
                    int(road.oneway),
                    road.direction,
                    road.road_class,
                    road.lane_count,
                    json.dumps(road.turn_restrictions or []),
                    json.dumps(road.metadata or {}),
                )
                for road in roads
            ],
        )
        self._conn.commit()

    def upsert_trajectories(self, trajectories: Iterable[Trajectory]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO trajectories(id, points_json) VALUES (?, ?)",
            [
                (
                    trajectory.id,
                    json.dumps(
                        [
                            {
                                "lon": point.lon,
                                "lat": point.lat,
                                "timestamp": point.timestamp,
                            }
                            for point in trajectory.points
                        ]
                    ),
                )
                for trajectory in trajectories
            ],
        )
        self._conn.commit()

    def upsert_geofences(self, geofences: Iterable[GeoFence]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO geofences(id, name, geometry_json) VALUES (?, ?, ?)",
            [
                (
                    geofence.id,
                    geofence.name,
                    json.dumps(geofence.coordinates),
                )
                for geofence in geofences
            ],
        )
        self._conn.commit()

    def upsert_pois(self, pois: Iterable[POI]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO pois(id, name, lon, lat, properties_json) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    poi.id,
                    poi.name,
                    poi.lon,
                    poi.lat,
                    json.dumps(poi.properties),
                )
                for poi in pois
            ],
        )
        self._conn.commit()

    def list_nodes(self) -> list[RoadNode]:
        rows = self._conn.execute("SELECT * FROM road_nodes").fetchall()
        return [RoadNode(row["id"], row["lon"], row["lat"]) for row in rows]

    def list_roads(self) -> list[RoadEdge]:
        rows = self._conn.execute("SELECT * FROM road_edges").fetchall()
        return [
            RoadEdge(
                id=row["id"],
                from_node=row["from_node"],
                to_node=row["to_node"],
                geometry=[tuple(coord) for coord in json.loads(row["geometry_json"])],
                length=row["length"],
                speed_limit=row["speed_limit"],
                road_type=row["road_type"],
                oneway=bool(row["oneway"]),
                direction=row["direction"],
                road_class=row["road_class"],
                lane_count=row["lane_count"],
                turn_restrictions=json.loads(row["turn_restrictions_json"]),
                metadata=json.loads(row["metadata_json"]),
            )
            for row in rows
        ]

    def list_trajectories(self) -> list[Trajectory]:
        rows = self._conn.execute("SELECT * FROM trajectories").fetchall()
        trajectories: list[Trajectory] = []
        for row in rows:
            points = [
                TrajectoryPoint(item["lon"], item["lat"], item.get("timestamp"))
                for item in json.loads(row["points_json"])
            ]
            trajectories.append(Trajectory(row["id"], points))
        return trajectories

    def list_geofences(self) -> list[GeoFence]:
        rows = self._conn.execute("SELECT * FROM geofences").fetchall()
        return [
            GeoFence(
                row["id"],
                row["name"],
                [[tuple(coord) for coord in ring] for ring in json.loads(row["geometry_json"])],
            )
            for row in rows
        ]

    def list_pois(self) -> list[POI]:
        rows = self._conn.execute("SELECT * FROM pois").fetchall()
        return [
            POI(
                id=row["id"],
                name=row["name"],
                lon=row["lon"],
                lat=row["lat"],
                properties=json.loads(row["properties_json"]),
            )
            for row in rows
        ]

    def has_roads(self) -> bool:
        row = self._conn.execute("SELECT COUNT(*) AS count FROM road_edges").fetchone()
        return bool(row and row["count"])
