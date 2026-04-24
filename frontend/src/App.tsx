import { useEffect, useMemo, useRef, useState } from "react";
import L, { GeoJSON as LeafletGeoJSON, Map as LeafletMap } from "leaflet";
import {
  Activity,
  Boxes,
  Ban,
  Crosshair,
  GitBranch,
  Layers,
  LocateFixed,
  MapPinned,
  Route,
  Search
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
  const [busy, setBusy] = useState(false);

  const metrics = useMemo(() => {
    return {
      roads: state?.roads.features.length ?? 0,
      trajectories: state?.trajectories.features.length ?? 0,
      geofences: state?.geofences.features.length ?? 0,
      pois: state?.pois.features.length ?? 0
    };
  }, [state]);

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
            <p>Spatial Algorithm Platform</p>
          </div>
        </header>

        <section className="metrics" aria-label="Dataset metrics">
          <Metric label="Roads" value={metrics.roads} />
          <Metric label="Traj" value={metrics.trajectories} />
          <Metric label="Fence" value={metrics.geofences} />
          <Metric label="POI" value={metrics.pois} />
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

        <section className="result-panel">
          <div className="panel-title">
            <Search size={18} />
            <span>Result</span>
          </div>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </section>
      </aside>
      <main className="map-shell">
        <div id="map" />
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
