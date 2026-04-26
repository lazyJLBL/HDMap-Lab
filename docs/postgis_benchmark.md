# PostGIS Benchmark

HDMap-Lab keeps core spatial algorithms self-developed. PostGIS is used only as an external comparison target.

Start PostGIS:

```bash
docker compose up -d postgis
```

Run the comparison:

```bash
python -m benchmarks.postgis_benchmark \
  --roads data/roads.geojson \
  --iterations 100
```

The script loads roads into a PostGIS table, creates a GiST index, and compares `ST_Intersects` bbox queries against the in-process HDMap-Lab STR R-tree.

Default connection:

```text
postgresql://hdmap:hdmap@127.0.0.1:5432/hdmap_lab
```

Override it with:

```bash
$env:HDMAP_POSTGIS_DSN="postgresql://user:pass@host:5432/db"
```
