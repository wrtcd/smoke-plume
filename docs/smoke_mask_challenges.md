# Smoke mask challenges (Planet + simple spectral rules)

This note collects practical issues that come up when building a **binary smoke mask** from PlanetScope surface reflectance and using it for **\(f_p\)** in the TEMPO pipeline. It mirrors discussion in development (QGIS checks, coastal scenes, urban pilots).

---

## 1. Nodata vs “clear sky” (value 0)

If invalid pixels (outside the swath, missing SR) are encoded as **0** in the same raster as **clear = 0**, QGIS and simple stats cannot tell **background** from **valid clear land/sky**.

**Mitigation in this repo:** the exported smoke mask uses a dedicated **nodata** value for invalid pixels (default **−9999**), with **0 = clear** and **1 = smoke** where the pixel is valid. When warping to the TEMPO grid, invalid mask pixels are passed as **src_nodata** so they do not average in as “clear.”

---

## 2. “NDHI” naming: two different indices

The acronym **NDHI** is not used consistently in the literature.

| Name in scripts | Formula | Role |
|-----------------|--------|------|
| **`ndhi`** (green–blue) | \((G - B) / (G + B)\) | Contrasts green vs blue; **not** the usual B–NIR haze index. |
| **`ndhi_bnir`** (blue–NIR) | \((B - NIR) / (B + NIR)\) | Common **haze / path-radiance** style contrast between shortwave blue and NIR. |

Smoke/haze often pushes the **blue–NIR** index toward values that differ from healthy vegetation (which is typically **strongly negative** in \((B-NIR)/(B+NIR)\) when NIR is high). The **green–blue** index answers a different question (spectral shape near the blue–green edge).

**Takeaway:** pick the method to match the physics you care about; tune thresholds per scene (`--ndhi-smoke-below` vs `--ndhi-bnir-smoke-above`).

---

## 3. Water and ocean margins (e.g. Pacific coast)

**Water** is spectrally ambiguous for single-rule masks: low NIR, variable visible bands, sun glint, and coastal mixing can resemble **smoke-like** behaviour in **B/NIR** or **NDHI-style** indices.

**Mitigations:**

- Try **different Planet scenes** (less ocean in frame, different geometry/sun).
- **Tune** `blue_nir_max`, `--ndhi-smoke-below`, or `--ndhi-bnir-smoke-above` using the exported **index** GeoTIFF in QGIS.
- Consider an explicit **water mask** later (e.g. NDWI or similar) and **exclude** water from the smoke classification.

---

## 4. Roads, urban grid, and built-up areas

**Asphalt**, **building shadows**, **mixed 3 m pixels** (roof + street + tree), and **regular street grids** often fall into similar ratio / NDHI ranges as **haze or aerosol** when using a **global threshold**.

This is an expected limitation of **one spectral rule** over complex cities (e.g. northern parts of a basin scene showing a strong “grid”).

**Mitigations:**

- **Tighten thresholds** using the index rasters; compare false positives on roads vs true plume.
- **Scene selection:** views with **less urban footprint** in the plume ROI when possible.
- **Post-processing** (e.g. removing tiny isolated patches) only with care, so real plume fragments are not removed.
- Longer term: **multi-criteria** rules (e.g. combine with thermal if available), **masks** for urban/water, or **supervised** models—outside the current minimal pipeline.

---

## 5. Mask quality vs fire-location exploration

Getting a **clean** mask often requires **iterating**: different **Planet acquisitions**, **fire locations**, and **thresholds**. The pilot scene is not guaranteed to be optimal; coastal + urban + smoke in one frame is inherently hard.

---

## 6. Summary table

| Challenge | Symptom | Directions to improve |
|-----------|---------|------------------------|
| Nodata vs clear | Black border looks like clear | Use nodata ≠ 0; warp with `src_nodata` |
| Index choice | Confusion about “NDHI” | Use `ndhi_bnir` for B–NIR haze-style; `ndhi` for G–B |
| Water | Ocean/water flagged as smoke | Tune indices; scene choice; future water mask |
| Urban / roads | Grid-like false positives | Tune thresholds; reduce urban in ROI; richer rules later |
| Reproducibility | Different mass if mask drifts | Save `pipeline_summary.json` parameters and mask method |

---

## Related scripts

- `scripts/smoke_plume_pipeline.py` — `--mask-method`, `--ndhi-bnir-smoke-above`, `--mask-nodata`
- `scripts/planet_smoke_mask_qgis.py` — QGIS-oriented exports (`ndhi_green_blue.tif`, `ndhi_bnir.tif`, etc.)
- `scripts/export_planet_smoke_step2.py` — Step 2 checkpoint outputs
