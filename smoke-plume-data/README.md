# Local data (large rasters ignored by git)

Place large files here; `*.tif`, `*.nc`, and typical rasters are **gitignored** (see `.gitignore`). Small **Planet sidecar JSON** (`*_metadata.json`) and **GeoJSON** under `fire_aoi/` may be tracked.

## Study regions (six cases)

Each folder is one fire / AOI with the same layout:

| Folder | Contents |
|--------|----------|
| `airport/` | `planet/`, `tempo/`, optional `case.json` |
| `bridge/` | same |
| `eaton/` | same |
| `line/` | same |
| `palisades/` | same (pilot; includes example warped TEMPO GeoTIFF) |
| `park/` | same |

`case.json` (if present) lists the Planet SR GeoTIFF and the **warped** TEMPO VCD GeoTIFF (`TEMPO_NO2_trop_warped_4326.tif`) for `scripts/run_all_cases.py`. Generate the GeoTIFF from each granule with `scripts/tempo_l2_to_4326.py` if it is not present yet.

```
smoke-plume-data/<region>/planet/   # PlanetScope SR GeoTIFF + optional *_metadata.json
smoke-plume-data/<region>/tempo/    # TEMPO L2 NetCDF + warped GeoTIFF
smoke-plume-data/fire_aoi/          # Fire search boxes — see fire_aoi/README.md
```

Planet **UTC** times for TEMPO: `python scripts/print_planet_acquired_table.py` (see `docs/study_regions_planet_tempo_match.md` if present).

See **PROJECT.md** (“Locked data”) for pilot naming and methodology.
