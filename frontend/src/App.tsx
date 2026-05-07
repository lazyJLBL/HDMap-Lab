import { useEffect, useMemo, useRef, useState } from "react";
import L, { GeoJSON as LeafletGeoJSON, Map as LeafletMap } from "leaflet";
import {
  Activity,
  BarChart3,
  Boxes,
  Ban,
  Crosshair,
  FileSearch,
  GitBranch,
  Layers,
  LocateFixed,
  MapPinned,
  Network,
  Route,
  Search,
  Wrench
} from "lucide-react";

type FeatureCollection = GeoJSON.FeatureCollection;

type VisualizationState = {
  roads: FeatureCollection;
  trajectories: FeatureCollection;
  geofences: FeatureCollection;
  pois: FeatureCollection;
  bounds: [number, number, number, number] | null;
};

type LayerFlags = {
  roads: boolean;
  trajectories: boolean;
  geofences: boolean;
  pois: boolean;
  matching: boolean;
  route: boolean;
  nearby: boolean;
};

type NearbyRoad = {
  road_id: string;
  distance: number;
  projection_point: [number, number];
  geometry?: { coordinates?: Array<[number, number]> };
};

type MatchResult = {
  projection_point: [number, number];
  matched_road_id: string;
};

type GeofenceEvent = {
  event: string;
  fence_id: string;
  point: [number, number];
  timestamp?: string;
};

type GeometryCase = {
  id: string;
  category: string;
  description: string;
};

const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const defaultFlags: LayerFlags = {
  roads: true,
  trajectories: true,
  geofences: true,
  pois: true,
  matching: true,
  route: true,
  nearby: true
};

export function App() {
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<Record<string, LeafletGeoJSON | L.LayerGroup>>({});
  const [state, setState] = useState<VisualizationState | null>(null);
  const [flags, setFlags] = useState<LayerFlags>(defaultFlags);
  const [result, setResult] = useState<Record<string, unknown>>({});
  const [algorithm, setAlgorithm] = useState("hmm");
  const [routeAlgorithm, setRouteAlgorithm] = useState("astar");
  const [routeMode, setRouteMode] = useState("shortest_distance");
  const [routeScenario, setRouteScenario] = useState("direct");
  const [geometryCases, setGeometryCases] = useState<GeometryCase[]>([]);
  const [selectedGeometryCaseId, setSelectedGeometryCaseId] = useState("");
  const [mapMatchingStressCase, setMapMatchingStressCase] = useState("parallel_roads_drift");
  const [busy, setBusy] = useState(false);

  const metrics = useMemo(() => {
    return {
      roads: state?.roads.features.length ?? 0,
      trajectories: state?.trajectories.features.length ?? 0,
      geofences: state?.geofences.features.length ?? 0,
      pois: state?.pois.features.length ?? 0
    };
  }, [state]);
  const resultMetrics = useMemo(() => {
    const direct = asRecord(result.metrics);
    const data = asRecord(result.data);
    return direct ?? asRecord(data?.metrics) ?? {};
  }, [result]);
  const warnings = useMemo(() => {
    return Array.isArray(result.warnings) ? result.warnings.map((item) => String(item)) : [];
  }, [result]);
  const debugLayerKeys = useMemo(() => {
    const data = asRecord(result.data);
    const layers = asRecord(result.debug_layers) ?? asRecord(data?.debug_layers);
    return Object.keys(layers ?? {});
  }, [result]);
  const benchmarkRows = useMemo(() => {
    const data = asRecord(result.data);
    const rows = Array.isArray(data?.results) ? data.results : [];
    return rows.filter(isRecord).slice(0, 8);
  }, [result]);

  useEffect(() => {
    const map = L.map("map", { zoomControl: false }).setView([39.91, 116.4], 14);
    mapRef.current = map;
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);
    void refreshState();
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    renderBaseLayers();
  }, [state, flags]);

  async function request(path: string, options?: RequestInit) {
    const response = await fetch(`${apiBase}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json();
  }

  async function runAction(action: () => Promise<Record<string, unknown>>) {
    setBusy(true);
    try {
      const started = performance.now();
      const payload = await action();
      setResult({ ...payload, query_ms: Math.round(performance.now() - started) });
    } catch (error) {
      setResult({ error: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(false);
    }
  }

  async function refreshState() {
    const payload = await request("/visualization/state");
    setState(payload);
    if (payload.bounds && mapRef.current) {
      const [minLon, minLat, maxLon, maxLat] = payload.bounds;
      mapRef.current.fitBounds([
        [minLat, minLon],
        [maxLat, maxLon]
      ], { padding: [24, 24] });
    }
  }

  async function loadSample() {
    await runAction(async () => {
      const payload = await request("/datasets/load", {
        method: "POST",
        body: JSON.stringify({ source: "sample" })
      });
      await refreshState();
      clearOverlay("matching");
      clearOverlay("route");
      clearOverlay("nearby");
      clearOverlay("geofenceEvents");
      return payload;
    });
  }

  async function runNearby() {
    await runAction(async () => {
      const payload = await request("/roads/nearby?lon=116.4015&lat=39.9110&k=5");
      renderNearby(payload.roads ?? []);
      return payload;
    });
  }

  async function runMapMatching() {
    await runAction(async () => {
      const payload = await request("/mapmatch", {
        method: "POST",
        body: JSON.stringify({ algorithm, k: 5 })
      });
      renderMatching(payload.matches ?? []);
      return payload;
    });
  }

  async function runRoute() {
    await runAction(async () => {
      const body: Record<string, unknown> = {
        start: [116.390, 39.900],
        end: [116.410, 39.920],
        mode: routeMode,
        algorithm: routeAlgorithm
      };
      if (routeScenario === "avoid") {
        body.avoid_polygons = [
          [
            [
              [116.398, 39.908],
              [116.406, 39.908],
              [116.406, 39.916],
              [116.398, 39.916],
              [116.398, 39.908]
            ]
          ]
        ];
      }
      if (routeScenario === "waypoints") {
        body.waypoints = [[116.400, 39.910]];
      }
      const payload = await request("/route/shortest", {
        method: "POST",
        body: JSON.stringify(body)
      });
      renderRoute(payload.geometry);
      return payload;
    });
  }

  async function runGeofence() {
    await runAction(async () => {
      const payload = await request("/geofence/check", {
        method: "POST",
        body: JSON.stringify({})
      });
      renderGeofenceEvents(payload.events ?? []);
      return payload;
    });
  }

  async function runSpatialQuery() {
    await runAction(async () => {
      return request("/spatial/query", {
        method: "POST",
        body: JSON.stringify({
          query_type: "points_in_polygon",
          target: "trajectory_points",
          polygon: [
            [
              [116.398, 39.908],
              [116.406, 39.908],
              [116.406, 39.916],
              [116.398, 39.916],
              [116.398, 39.908]
            ]
          ]
        })
      });
    });
  }

  async function runTopologyRepair() {
    await runAction(async () => {
      const payload = await request("/topology/repair", {
        method: "POST",
        body: JSON.stringify({ snap_tolerance_m: 1, apply: false })
      });
      renderFixedRoads(payload.debug_layers?.fixed_roads);
      renderFeatureCollection("issueMarkers", payload.debug_layers?.split_points as FeatureCollection | undefined, {
        color: "#dc2626",
        weight: 4,
        opacity: 0.92,
        fillOpacity: 0.24
      });
      return payload;
    });
  }

  async function loadGeometryCases() {
    await runAction(async () => {
      const payload = await request("/geometry/cases");
      const cases = (payload.data ?? []) as GeometryCase[];
      setGeometryCases(cases);
      if (!selectedGeometryCaseId && cases.length) {
        setSelectedGeometryCaseId(cases[0].id);
      }
      renderFeatureCollection("geometryCases", payload.debug_layers?.cases as FeatureCollection | undefined, {
        color: "#0f766e",
        weight: 4,
        opacity: 0.86,
        fillOpacity: 0.16
      });
      return payload;
    });
  }

  async function runGeometryCase() {
    await runAction(async () => {
      const caseId = selectedGeometryCaseId || geometryCases[0]?.id;
      const payload = await request("/geometry/cases/run", {
        method: "POST",
        body: JSON.stringify({ case_id: caseId })
      });
      renderFeatureCollection("geometryCaseResult", payload.debug_layers?.case_geometry as FeatureCollection | undefined, {
        color: payload.data?.passed ? "#16a34a" : "#dc2626",
        weight: 5,
        opacity: 0.9,
        fillOpacity: 0.18
      });
      return payload;
    });
  }

  async function runSpatialBenchmark() {
    await runAction(async () => {
      const payload = await request("/benchmarks/spatial-index", {
        method: "POST",
        body: JSON.stringify({ iterations: 10, return_debug_layers: true })
      });
      renderFeatureCollection("benchmarkItems", payload.debug_layers?.items_sample as FeatureCollection | undefined, {
        color: "#475569",
        weight: 2,
        opacity: 0.4
      });
      renderFeatureCollection("queryBbox", payload.debug_layers?.sample_bbox_query as FeatureCollection | undefined, {
        color: "#f59e0b",
        weight: 3,
        opacity: 0.95,
        fillOpacity: 0.08
      });
      return payload;
    });
  }

  async function runMapMatchingBenchmark() {
    await runAction(async () => {
      return request("/benchmarks/map-matching", {
        method: "POST",
        body: JSON.stringify({ k: 5 })
      });
    });
  }

  async function runMapMatchingStress() {
    await runAction(async () => {
      const payload = await request("/benchmarks/map-matching", {
        method: "POST",
        body: JSON.stringify({
          cases: [mapMatchingStressCase],
          algorithms: ["nearest", "hmm"],
          k: 5,
          radius_m: 150,
          return_debug_layers: true
        })
      });
      const layers = payload.debug_layers?.[mapMatchingStressCase];
      renderFeatureCollection("mapMatchingStressRoads", layers?.roads as FeatureCollection | undefined, {
        color: "#334155",
        weight: 5,
        opacity: 0.78
      });
      renderFeatureCollection("mapMatchingStressGps", layers?.trajectory as FeatureCollection | undefined, {
        color: "#7c3aed",
        weight: 4,
        opacity: 0.9
      });
      return payload;
    });
  }

  async function runTrajectoryAnalysis() {
    await runAction(async () => {
      return request("/trajectory/analyze", {
        method: "POST",
        body: JSON.stringify({})
      });
    });
  }

  async function runRoutingExplain() {
    await runAction(async () => {
      const payload = await request("/routing/explain", {
        method: "POST",
        body: JSON.stringify({
          start: [116.390, 39.900],
          end: [116.410, 39.920],
          mode: routeMode,
          algorithm: routeAlgorithm,
          preferred_road_classes: ["primary", "secondary", "residential"],
          turn_penalty_seconds: 8
        })
      });
      renderRoute(payload.data?.geometry);
      return payload;
    });
  }

  async function loadExperiments() {
    await runAction(async () => request("/visualization/experiments"));
  }

  function clearOverlay(key: string) {
    const layer = layerRef.current[key];
    if (layer && mapRef.current) {
      layer.removeFrom(mapRef.current);
      delete layerRef.current[key];
    }
  }

  function addLayer(key: string, layer: LeafletGeoJSON | L.LayerGroup) {
    clearOverlay(key);
    layerRef.current[key] = layer;
    if (mapRef.current) {
      layer.addTo(mapRef.current);
    }
  }

  function renderBaseLayers() {
    if (!state || !mapRef.current) return;
    clearOverlay("roads");
    clearOverlay("trajectories");
    clearOverlay("geofences");
    clearOverlay("pois");
    if (flags.roads) {
      addLayer("roads", L.geoJSON(state.roads, { style: { color: "#334155", weight: 4, opacity: 0.75 } }));
    }
    if (flags.trajectories) {
      addLayer("trajectories", L.geoJSON(state.trajectories, { style: { color: "#2563eb", weight: 4, dashArray: "6 6" } }));
    }
    if (flags.geofences) {
      addLayer("geofences", L.geoJSON(state.geofences, { style: { color: "#dc2626", fillColor: "#f87171", fillOpacity: 0.18, weight: 2 } }));
    }
    if (flags.pois) {
      addLayer("pois", L.geoJSON(state.pois, {
        pointToLayer: (_, latlng) => L.circleMarker(latlng, {
          radius: 6,
          color: "#047857",
          fillColor: "#10b981",
          fillOpacity: 0.9,
          weight: 2
        })
      }));
    }
  }

  function renderNearby(roads: NearbyRoad[]) {
    if (!flags.nearby) return;
    const group = L.layerGroup();
    roads.forEach((road) => {
      if (road.geometry?.coordinates?.length) {
        const latlngs = road.geometry.coordinates.map((coord) => [coord[1], coord[0]] as [number, number]);
        L.polyline(latlngs, { color: "#f59e0b", weight: 8, opacity: 0.72 }).bindTooltip(road.road_id).addTo(group);
      }
      L.circleMarker([road.projection_point[1], road.projection_point[0]], {
        radius: 7,
        color: "#b45309",
        fillColor: "#f59e0b",
        fillOpacity: 0.9,
        weight: 2
      }).bindTooltip(road.road_id).addTo(group);
    });
    addLayer("nearby", group);
  }

  function renderMatching(matches: MatchResult[]) {
    if (!flags.matching) return;
    const group = L.layerGroup();
    const latlngs = matches.map((match) => [match.projection_point[1], match.projection_point[0]] as [number, number]);
    if (latlngs.length > 1) {
      L.polyline(latlngs, { color: "#7c3aed", weight: 5 }).addTo(group);
    }
    latlngs.forEach((latlng, index) => {
      L.circleMarker(latlng, {
        radius: 5,
        color: "#581c87",
        fillColor: "#a855f7",
        fillOpacity: 1,
        weight: 2
      }).bindTooltip(matches[index].matched_road_id).addTo(group);
    });
    addLayer("matching", group);
  }

  function renderGeofenceEvents(events: GeofenceEvent[]) {
    const group = L.layerGroup();
    events.forEach((event) => {
      const color = event.event === "enter" ? "#16a34a" : "#dc2626";
      L.circleMarker([event.point[1], event.point[0]], {
        radius: 8,
        color,
        fillColor: color,
        fillOpacity: 0.9,
        weight: 3
      }).bindTooltip(`${event.event}: ${event.fence_id}`).addTo(group);
    });
    addLayer("geofenceEvents", group);
  }

  function renderRoute(geometry?: { coordinates?: Array<[number, number]> }) {
    if (!flags.route || !geometry?.coordinates?.length) return;
    const latlngs = geometry.coordinates.map((coord) => [coord[1], coord[0]] as [number, number]);
    addLayer("route", L.layerGroup([L.polyline(latlngs, { color: "#0891b2", weight: 7, opacity: 0.85 })]));
  }

  function renderFixedRoads(collection?: FeatureCollection) {
    if (!collection?.features?.length) return;
    renderFeatureCollection("fixedRoads", collection, { color: "#16a34a", weight: 3, opacity: 0.85, dashArray: "5 5" });
  }

  function renderFeatureCollection(key: string, collection?: FeatureCollection, style?: L.PathOptions) {
    if (!collection?.features?.length) return;
    addLayer(key, L.geoJSON(collection, {
      style: () => style ?? { color: "#2563eb", weight: 4, opacity: 0.82, fillOpacity: 0.16 },
      pointToLayer: (feature, latlng) => {
        const layer = String(feature.properties?.layer ?? "");
        const color = layer.includes("intersection") || layer.includes("projection") ? "#dc2626" : (style?.color as string | undefined) ?? "#2563eb";
        return L.circleMarker(latlng, {
          radius: 7,
          color,
          fillColor: color,
          fillOpacity: 0.9,
          weight: 2
        });
      },
      onEachFeature: (feature, layer) => {
        const props = feature.properties ?? {};
        const label = [props.case_id, props.layer].filter(Boolean).join(" / ");
        if (label) layer.bindTooltip(label);
      }
    }));
  }

  function toggleLayer(key: keyof LayerFlags) {
    setFlags((current) => ({ ...current, [key]: !current[key] }));
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <header className="brand">
          <MapPinned size={24} />
          <div>
            <h1>HDMap-Lab</h1>
            <p>Computational Geometry Workbench for Map Algorithms</p>
          </div>
        </header>

        <section className="metrics" aria-label="Dataset metrics">
          <Metric label="Roads" value={metrics.roads} />
          <Metric label="Traj" value={metrics.trajectories} />
          <Metric label="Fence" value={metrics.geofences} />
          <Metric label="POI" value={metrics.pois} />
        </section>

        <section className="focus-strip" aria-label="Demo scenarios">
          <span>Dirty Road Repair</span>
          <span>Spatial Index Benchmark</span>
          <span>HMM Matching / Routing</span>
        </section>

        <section className="panel">
          <div className="panel-title">
            <Layers size={18} />
            <span>Layers</span>
          </div>
          <div className="toggles">
            {(Object.keys(flags) as Array<keyof LayerFlags>).map((key) => (
              <button key={key} className={flags[key] ? "toggle on" : "toggle"} onClick={() => toggleLayer(key)}>
                {key}
              </button>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-title">
            <Activity size={18} />
            <span>Algorithms</span>
          </div>
          <button className="command" disabled={busy} onClick={loadSample}>
            <Boxes size={18} /> Load Sample
          </button>
          <div className="field-row">
            <label>Map Matching</label>
            <select value={algorithm} onChange={(event) => setAlgorithm(event.target.value)}>
              <option value="hmm">HMM</option>
              <option value="candidate_cost">Candidate Cost</option>
              <option value="nearest">Nearest</option>
            </select>
          </div>
          <button className="command" disabled={busy} onClick={runMapMatching}>
            <GitBranch size={18} /> Match
          </button>
          <div className="field-row">
            <label>Route Mode</label>
            <select value={routeMode} onChange={(event) => setRouteMode(event.target.value)}>
              <option value="shortest_distance">Distance</option>
              <option value="shortest_time">Time</option>
            </select>
          </div>
          <div className="field-row">
            <label>Route Algo</label>
            <select value={routeAlgorithm} onChange={(event) => setRouteAlgorithm(event.target.value)}>
              <option value="astar">A*</option>
              <option value="dijkstra">Dijkstra</option>
            </select>
          </div>
          <div className="field-row">
            <label>Scenario</label>
            <select value={routeScenario} onChange={(event) => setRouteScenario(event.target.value)}>
              <option value="direct">Direct</option>
              <option value="avoid">Avoid Fence</option>
              <option value="waypoints">Via Node</option>
            </select>
          </div>
          <button className="command" disabled={busy} onClick={runRoute}>
            <Route size={18} /> Route
          </button>
          <button className="command secondary" disabled={busy} onClick={() => setRouteScenario("avoid")}>
            <Ban size={18} /> Avoid Demo
          </button>
          <button className="command" disabled={busy} onClick={runNearby}>
            <LocateFixed size={18} /> Nearby
          </button>
          <button className="command" disabled={busy} onClick={runGeofence}>
            <Crosshair size={18} /> Geofence
          </button>
          <button className="command" disabled={busy} onClick={runSpatialQuery}>
            <Search size={18} /> Query
          </button>
        </section>

        <section className="panel">
          <div className="panel-title">
            <Network size={18} />
            <span>Experiments</span>
          </div>
          <div className="field-row">
            <label>Geom Case</label>
            <select value={selectedGeometryCaseId} onChange={(event) => setSelectedGeometryCaseId(event.target.value)}>
              {geometryCases.length === 0 ? <option value="">Load cases</option> : null}
              {geometryCases.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.id}
                </option>
              ))}
            </select>
          </div>
          <button className="command" disabled={busy} onClick={loadGeometryCases}>
            <FileSearch size={18} /> Geometry Cases
          </button>
          <button className="command secondary" disabled={busy || (!selectedGeometryCaseId && geometryCases.length === 0)} onClick={runGeometryCase}>
            <Crosshair size={18} /> Run Case
          </button>
          <button className="command" disabled={busy} onClick={runTopologyRepair}>
            <Wrench size={18} /> Repair
          </button>
          <button className="command" disabled={busy} onClick={runSpatialBenchmark}>
            <BarChart3 size={18} /> Index Bench
          </button>
          <button className="command" disabled={busy} onClick={runMapMatchingBenchmark}>
            <GitBranch size={18} /> Match Bench
          </button>
          <div className="field-row">
            <label>Stress</label>
            <select value={mapMatchingStressCase} onChange={(event) => setMapMatchingStressCase(event.target.value)}>
              <option value="parallel_roads_drift">Parallel Drift</option>
              <option value="low_frequency_sampling">Low Frequency</option>
              <option value="overpass_layer_confusion">Overpass</option>
              <option value="wrong_nearest_road">Wrong Nearest</option>
            </select>
          </div>
          <button className="command secondary" disabled={busy} onClick={runMapMatchingStress}>
            <GitBranch size={18} /> Stress Test
          </button>
          <button className="command" disabled={busy} onClick={runTrajectoryAnalysis}>
            <Activity size={18} /> Trajectory
          </button>
          <button className="command" disabled={busy} onClick={runRoutingExplain}>
            <Route size={18} /> Explain
          </button>
          <button className="command secondary" disabled={busy} onClick={loadExperiments}>
            <FileSearch size={18} /> Catalog
          </button>
        </section>

        <section className="result-panel">
          <div className="panel-title">
            <Search size={18} />
            <span>Result</span>
          </div>
          <div className="result-summary">
            <SummaryBlock title="Metrics" values={resultMetrics} />
            <div className="summary-block">
              <span>Warnings</span>
              <strong>{warnings.length}</strong>
            </div>
            <div className="summary-block wide">
              <span>Debug Layers</span>
              <strong>{debugLayerKeys.length ? debugLayerKeys.join(", ") : "none"}</strong>
            </div>
          </div>
          {benchmarkRows.length ? (
            <table className="benchmark-table">
              <thead>
                <tr>
                  <th>Index</th>
                  <th>Query</th>
                  <th>p95 ms</th>
                  <th>Recall</th>
                </tr>
              </thead>
              <tbody>
                {benchmarkRows.map((row, index) => (
                  <tr key={`${String(row.index)}-${String(row.query_type)}-${index}`}>
                    <td>{String(row.index ?? "-")}</td>
                    <td>{String(row.query_type ?? "-")}</td>
                    <td>{formatCell(row.p95_ms)}</td>
                    <td>{formatCell(row.recall)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </section>
      </aside>
      <main className="map-shell">
        <div id="map" />
        <div className="map-legend" aria-label="Map layer legend">
          <LegendItem color="#334155" label="Original road" />
          <LegendItem color="#16a34a" label="Repaired road" />
          <LegendItem color="#2563eb" label="GPS / trajectory" />
          <LegendItem color="#7c3aed" label="Matched path" />
          <LegendItem color="#f59e0b" label="Query bbox" />
          <LegendItem color="#0891b2" label="Route" />
          <LegendItem color="#dc2626" label="Issue marker" />
        </div>
      </main>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SummaryBlock({ title, values }: { title: string; values: Record<string, unknown> }) {
  const entries = Object.entries(values).slice(0, 3);
  return (
    <div className="summary-block wide">
      <span>{title}</span>
      <strong>{entries.length ? entries.map(([key, value]) => `${key}: ${formatCell(value)}`).join(" | ") : "none"}</strong>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span className="legend-item">
      <i style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return isRecord(value) ? value : null;
}

function formatCell(value: unknown) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return "-";
}
