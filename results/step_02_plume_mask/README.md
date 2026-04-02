## Step 2 — Planet smoke plume mask (pilot heuristic)

### Purpose

Detect the smoke plume footprint on the **Planet surface reflectance** scene at native resolution.

This step produces a **binary mask** \(M\) which is aggregated onto the TEMPO grid as the **smoke fraction** \(f_p\).

### Inputs (locked)

- Planet SR GeoTIFF: `data/palisades/planet/20250110_185256_28_24e1_3B_AnalyticMS_SR_8b.tif`
- Bands used (1-based indexing, as in `scripts/palisades_pipeline.py`):
  - **Blue**: band **2**
  - **NIR**: band **8**

### Mask definition (current pilot)

Compute:

- `ratio = blue / max(nir, 1e-8)`

Then:

- `M = (ratio < blue_nir_max) & finite(blue) & finite(nir)`

Parameter used in the pilot run:

- `blue_nir_max = 0.42`

### Generated outputs (option C: full + preview)

**QGIS-friendly names** (same mask math; default folder `results/qgis_planet_smoke/`):

`python scripts/planet_smoke_mask_qgis.py`

**Full Step 2 export** (ratio, mask, preview, `f_p`):

`python scripts/export_planet_smoke_step2.py`

Writes under `results/step_02_plume_mask/`:

| File | Description |
|------|-------------|
| `planet_blue_nir_ratio.tif` | Full-res blue/NIR ratio |
| `planet_smoke_mask.tif` | Full-res binary mask (0/1) |
| `planet_blue_nir_ratio_preview.tif` | Preview ratio (max dimension ~2048 px) |
| `planet_smoke_mask_preview.tif` | Preview mask (averaged to preview grid) |
| `f_p_tempo_grid.tif` | **Sub-pixel plume fraction** on the **TEMPO** grid (0–1); same logic as `palisades_pipeline.py` |

### Sub-pixel plume fraction \(f_p\) (critical)

Yes — this is implemented in **`scripts/palisades_pipeline.py`**: the Planet binary mask is reprojected onto the TEMPO raster with **`Resampling.average`**, so each TEMPO cell gets the **mean** of mask values inside that footprint (equivalently: smoke area fraction when the mask is 0/1). That array is **`f_p`**; mass uses `f_p * (VCD - VCD_bg)` per pixel.

The export script writes the same field as **`f_p_tempo_grid.tif`** for QGIS inspection.
