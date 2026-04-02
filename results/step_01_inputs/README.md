## Step 1 — Inputs locked (Planet + TEMPO)

This folder is a **checkpoint** for Step 1 (acquire coincident data + lock metadata).

### What we used (exact files)

- **Planet (SR, 8-band)**: `data/palisades/planet/20250110_185256_28_24e1_3B_AnalyticMS_SR_8b.tif`
- **Planet sidecar metadata**: `data/palisades/planet/20250110_185256_28_24e1_metadata.json`
- **TEMPO L2 NO₂ (NetCDF)**: `data/palisades/tempo/TEMPO_NO2_L2_V03_20250110T184529Z_S008G09.nc`
- **Derived TEMPO NO₂ trop VCD raster (EPSG:4326)**: `data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif`

### What to open in QGIS (quick check)

1. Open the Planet GeoTIFF and verify you can display:
   - RGB (visual sanity check)
   - NIR (available as band 8; used by the pipeline)
2. Open the derived TEMPO GeoTIFF (`TEMPO_NO2_trop_warped_4326.tif`) and verify:
   - It’s a single-band raster
   - CRS is EPSG:4326
   - Tags include `SOURCE_NC` (points back to the NetCDF used)

### Manifest (machine-readable)

See `step_01_manifest.json` for:

- Exact file paths
- TEMPO `time_coverage_start/end`
- Which TEMPO fields exist (VCD, AMF, cloud fraction, QA)
- Whether anything AK-like was found (spoiler: not in this granule as a named variable)

