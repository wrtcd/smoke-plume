# Smoke plume NO₂ — Palisades (and generalizable fires)

## Project summary

### Goal

Estimate **nitrogen dioxide (NO₂)** burden associated with **smoke plumes** (e.g. Palisades fire) by combining:

- **PlanetScope** — high spatial resolution imagery to locate smoke pixels and define plume extent on the ground.
- **TEMPO** (geostationary; NetCDF products) — **hourly** (or sub-hourly, product-dependent) **NO₂ vertical column density (VCD)** and ancillary fields over the Americas.

The workflow aligns **PlanetScope** and **TEMPO in time**, maps **smoke masks** onto **TEMPO’s grid/footprints**, uses **area overlap** (and any weighting rules) so coarse TEMPO pixels are not treated as uniformly “smoke,” and applies **background subtraction** so reported NO₂ reflects **excess column** (smoke-impacted signal relative to clean air or a reference region/time), not the full ambient column alone. It then converts **background-subtracted VCD** to **molecule counts and/or mass** using consistent units (column × area, Avogadro’s number, NO₂ molar mass, etc.). **Plume height** assumptions (e.g. **0.5–2 km** from literature) support interpretation when translating **column** to **volume-mean concentration** or when discussing mixing; they are documented alongside the retrieval’s own assumptions (e.g. air mass factors in the NetCDF).

### Spatial footprint, resolution, and cadence (reference)

Typical or product-level values; **always confirm** footprint, spatial sampling, grid, and observation times in **file metadata** for the granules you use.

| Source | Spatial footprint (extent) | Native / reporting resolution | Temporal |
|--------|---------------------------|-------------------------------|----------|
| **PlanetScope** | **Per scene or strip**—tens of km across (product/order dependent); you only get coverage where scenes intersect your AOI | ~3–4 m ground sampling (product/region dependent) | Revisit varies by latitude and constellation; often multiple scenes per day in many areas, not guaranteed hourly |
| **TEMPO NO₂ (L2)** | **Field of Regard**—daylight North America (CONUS, southern Canada, Mexico, etc.); granules tile east–west strips within that domain | ~2 km × ~4–5 km (varies with scan geometry; see attributes) | ~Hourly in daylight over the Americas; packaged in sub-hourly granules |
| **TEMPO (L3 gridded, if used)** | Same **geographic domain** as L2, on a regular lat–lon grid | Often ~0.02° regular grid (~2 km scale at mid-latitudes) | Same underlying cadence, resampled to a fixed grid |
| **CalFire perimeter** | **California** incident perimeters (state agency product); not a satellite swath | Vector polygons (not a raster cell size) | Irregular updates—often daily or a few times per week on large fires; not aligned to hourly TEMPO |

### Current methodology (conversation baseline)

*This section will be replaced or merged with the **exact steps, formulas, and product names** from your scanned print once that file is uploaded and transcribed.*

1. **Inputs** — TEMPO NetCDF scene(s) for NO₂ VCD (+ QA/geometry as required); PlanetScope assets whose acquisition **temporally intersects** the TEMPO observation window used.
2. **Smoke mask** — Derive smoke pixels from PlanetScope (bands/thresholds or indices as specified in the reference document).
3. **Spatial coregistration** — Project smoke polygons/rasters to a common CRS; compute **overlap area** between smoke and each TEMPO pixel (or subcell weighting per reference).
4. **Background subtraction** — Define **background** NO₂ (spatial mask, time window, or reference scene—per the reference document); subtract it from the plume-relevant column so integration uses **ΔVCD** (excess NO₂) where required.
5. **Column integration** — Apply the reference document’s rules to combine **background-subtracted** VCD with overlap fractions and pixel areas to obtain **total excess NO₂** (molecules and/or kg) attributable to the smoke-impacted region.
6. **Documentation** — Record assumptions (background definition, height range, QA filtering, time matching tolerance) for reproducibility.

### Pending integration from scanned reference

**Status:** A printed/scanned methodology document is to be uploaded. After upload, this file will be updated so that **equations, variable names, units, and processing order** match that reference **exactly**.

Action items live in **TODO.txt** (same folder as this file).

---

*Last updated: background subtraction, footprint + resolution table; scanned methodology still pending.*
