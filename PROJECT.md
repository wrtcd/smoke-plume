# Smoke plume NO₂ — Palisades (and generalizable fires)

## Project summary

### Goal

Estimate **nitrogen dioxide (NO₂)** burden associated with **smoke plumes** (e.g. Palisades fire) by combining:

- **PlanetScope** — high spatial resolution imagery to locate smoke pixels and define plume extent on the ground.
- **TEMPO** (geostationary; NetCDF products) — **hourly** (or sub-hourly, product-dependent) **NO₂ vertical column density (VCD)** and ancillary fields over the Americas.

The workflow aligns **PlanetScope** and **TEMPO in time**, maps **smoke masks** onto **TEMPO’s grid/footprints**, uses **area overlap** (and any weighting rules) so coarse TEMPO pixels are not treated as uniformly “smoke,” and converts **VCD** to **molecule counts and/or mass** using consistent units (column × area, Avogadro’s number, NO₂ molar mass, etc.). **Plume height** assumptions (e.g. **0.5–2 km** from literature) support interpretation when translating **column** to **volume-mean concentration** or when discussing mixing; they are documented alongside the retrieval’s own assumptions (e.g. air mass factors in the NetCDF).

### Current methodology (conversation baseline)

*This section will be replaced or merged with the **exact steps, formulas, and product names** from your scanned print once that file is uploaded and transcribed.*

1. **Inputs** — TEMPO NetCDF scene(s) for NO₂ VCD (+ QA/geometry as required); PlanetScope assets whose acquisition **temporally intersects** the TEMPO observation window used.
2. **Smoke mask** — Derive smoke pixels from PlanetScope (bands/thresholds or indices as specified in the reference document).
3. **Spatial coregistration** — Project smoke polygons/rasters to a common CRS; compute **overlap area** between smoke and each TEMPO pixel (or subcell weighting per reference).
4. **Column integration** — Apply the reference document’s rules to combine VCD with overlap fractions and pixel areas to obtain **total NO₂** (molecules and/or kg) over the smoke-impacted region.
5. **Documentation** — Record assumptions (height range, QA filtering, time matching tolerance) for reproducibility.

### Pending integration from scanned reference

**Status:** A printed/scanned methodology document is to be uploaded. After upload, this file will be updated so that **equations, variable names, units, and processing order** match that reference **exactly**.

Action items live in **TODO.txt** (same folder as this file).

---

*Last updated: draft before scanned methodology upload.*
