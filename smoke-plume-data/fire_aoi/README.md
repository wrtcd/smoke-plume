# Fire AOI bounding boxes (GeoJSON)

Approximate **axis-aligned** search boxes from **`docs/fire_locations_explore.md`** (WGS84 / EPSG:4326). **Not** official fire perimeters.

| Location | Use when |
|----------|----------|
| **`single_feature/<id>.geojson`** | **Default for uploads** — one [GeoJSON `Feature`](https://datatracker.ietf.org/doc/html/rfc7946#section-3.2) per file (`type`, `id`, `properties`, `geometry`). Works with **Planet** Features Manager / Orders API and most AOI tools. |
| **`<id>.geojson`** (under this folder) | Same geometry wrapped in a **`FeatureCollection`** with one feature (+ optional `bbox`). |
| **`polygon_only/<id>.geojson`** | Root object is only a **`Polygon`** geometry — **not** a Feature. Some clients accept this; **Planet** and many others do **not** (they expect `Feature` or `FeatureCollection`). Using this can produce errors like *“Failed to get geographical boundaries from file data”*. |
| `california_fires_aoi.geojson` | All **six** incidents in one collection (large merged extent). |

**Regenerate** after editing corners in `scripts/build_fire_aoi_geojson.py`:

```text
python scripts/build_fire_aoi_geojson.py
```

Polygons use signed **longitude**, **latitude** order; ring is SW → SE → NE → NW → SW.

---

### NASA Satellite Data Explorer (SDX) / `Cannot read ... 'lng'`

The [SDX user guide](https://csdap.earthdata.nasa.gov/user-guide/) allows GeoJSON AOIs; multi-feature files are merged and can confuse the client. Try **`single_feature/palisades-fire-2025.geojson`**, or **Edit AOI bounds** with NE/SW from the doc, or draw on the map.

---

### Planet Labs

Planet’s [Features API](https://docs.planet.com/develop/apis/features/uploading-and-validating-features/) accepts **Feature** or **FeatureCollection** with **Polygon** / **MultiPolygon** in **EPSG:4326**. A file whose root `type` is only **`Polygon`** (see **`polygon_only/`**) is **not** valid for that API — use **`single_feature/`** or the per-fire **`FeatureCollection`** files instead.
