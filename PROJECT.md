# Smoke plume NO₂ — Palisades (and generalizable fires)

## Project summary

### Goal

Estimate **nitrogen dioxide (NO₂)** burden associated with **smoke plumes** (e.g., the Palisades fire) by combining:

- **PlanetScope** — high spatial resolution imagery to locate smoke pixels and define plume extent on the ground.
- **TEMPO** (geostationary; NetCDF products) — **hourly** (or sub-hourly, product-dependent) **NO₂ vertical column density (VCD)** and ancillary fields over the Americas.

The workflow aligns **PlanetScope** and **TEMPO in time**, maps **smoke masks** onto **TEMPO’s grid/footprints**, uses **area overlap** (and any weighting rules) so coarse TEMPO pixels are not treated as uniformly “smoke,” and applies **background subtraction** so reported NO₂ reflects **excess column** (smoke-impacted signal relative to clean air or a reference region/time), not the full ambient column alone. It then converts **background-subtracted VCD** to **molecule counts and/or mass** using consistent units (column × area, Avogadro’s number, NO₂ molar mass, etc.). **Plume height** assumptions (e.g. **0.5–2 km** from literature) support interpretation when translating **column** to **volume-mean concentration** or when discussing mixing; they are documented alongside the retrieval’s own assumptions (e.g. air mass factors in the NetCDF).

### Spatial footprint, resolution, and cadence (reference)

Typical or product-level values; **always confirm** footprint, spatial sampling, grid, and observation times in **file metadata** for the granules you use.


| Source                          | Spatial footprint (extent)                                                                                                           | Native / reporting resolution                               | Temporal                                                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **PlanetScope**                 | **Per scene or strip**—tens of km across (product/order dependent); you only get coverage where scenes intersect your AOI            | ~3–4 m ground sampling (product/region dependent)           | Revisit varies by latitude and constellation; often multiple scenes per day in many areas, not guaranteed hourly |
| **TEMPO NO₂ (L2)**              | **Field of Regard**—daylight North America (CONUS, southern Canada, Mexico, etc.); granules tile east–west strips within that domain | ~2 km × ~4–5 km (varies with scan geometry; see attributes) | ~Hourly in daylight over the Americas; packaged in sub-hourly granules                                           |
| **TEMPO (L3 gridded, if used)** | Same **geographic domain** as L2, on a regular lat–lon grid                                                                          | Often ~0.02° regular grid (~2 km scale at mid-latitudes)     | Same underlying cadence, resampled to a fixed grid                                                               |
| **CalFire perimeter**           | **California** incident perimeters (state agency product); not a satellite swath                                                     | Vector polygons (not a raster cell size)                    | Irregular updates—often daily or a few times per week on large fires; not aligned to hourly TEMPO                |


### Locked data — Palisades pilot (TODO 2)

Working configuration for this repository’s first case; update if you change dates, AOI, or product versions.


| Item                        | Choice                                                                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **TEMPO product**           | **NO₂ L2 V03** (NetCDF); collection short name **TEMPO_NO2_L2**                                                                                  |
| **TEMPO granule (example)** | `TEMPO_NO2_L2_V03_20250110T184529Z_S008G09.nc`                                                                                                    |
| **TEMPO UTC window**        | **2025-01-10 18:45:29 → 18:52:06** (file `time_coverage_start` / `time_coverage_end`)                                                             |
| **TEMPO NO₂ field**         | `/product/vertical_column_troposphere` (plus QA / geolocation per methodology)                                                                    |
| **Planet scene**            | **20250110_185256_28_24e1**                                                                                                                       |
| **Planet `acquired` (UTC)** | **2025-01-10T18:52:56.288697Z**                                                                                                                   |
| **Planet product**          | **Surface reflectance** (PSScene SR as ordered; bands for smoke mask per methodology)                                                             |
| **Time-match note**         | Planet acquisition is **~50 s after** this granule’s **End**; use the **next** L2 granule in time, or define an explicit **±Δt** tolerance for analysis. |
| **GEE-only check**          | **NASA/TEMPO/NO2_L3_QA** — L3 QA-filtered maps; **not** interchangeable with L2 footprints.                                                               |


Local data layout: `data/palisades/tempo/`, `data/palisades/planet/`.

**Pilot test rasters (first integration test):**

| Role | File |
|------|------|
| **Planet (SR)** | `data/palisades/planet/20250110_185256_28_24e1_3B_AnalyticMS_SR_8b.tif` — 8-band **analytic surface reflectance** (RGB + NIR, etc.) for smoke masking. |
| **TEMPO (NO₂ trop., mapped)** | `data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif` — `gdalwarp -geoloc` export of `/product/vertical_column_troposphere` in **EPSG:4326** (from the locked L2 granule). |

Python dependencies: see **`requirements.txt`** in the repository root.

### Methodology (from scanned notes: `method.pdf`, `masscal.pdf`)

Transcribed from your printed scans (including handwritten notes). **Confirm symbols and thresholds** against the product files you use (HDF/NetCDF attributes, QA definitions).

**Notation:** Equations below use **Unicode** (e.g. Δ, ×, ≈, ∑) and **bold monospace** (`VCD_adj` style) so they **show in any Markdown preview**. Built-in preview often **does not** render LaTeX (`$…$` / `$$…$$`). To try KaTeX anyway: **Settings** → search **Markdown Math** → enable, or rely on this folder’s `.vscode/settings.json`.

---

#### 1. Data acquisition and preprocessing

**1.1 Acquire coincident data**

- **PlanetScope:** surface reflectance (SR); RGB and NIR bands.
- **TEMPO:** Level-2 tropospheric NO₂ **vertical column density (VCD)**; **averaging kernel (AK)**; **air mass factor (AMF)**; **QA** flags.
- **Optional:** GOES-16 for cloud/smoke context; winds and planetary boundary layer height from NOAA or reanalysis.

**1.2 Temporal collocation**

- Choose the TEMPO overpass **closest in time** (hourly cadence).
- If the plume is evolving quickly, consider **two adjacent TEMPO hours** to test sensitivity to time choice.

**1.3 Spatial alignment**

- Reproject PlanetScope to the TEMPO grid, or vice versa, while preserving **native high-resolution plume geometry** on Planet and **coarse TEMPO pixels** for NO₂.
- Note (from scan): TEMPO ground sampling is **~2–4 km** (verify in granule metadata).

---

#### 2. Smoke plume detection from Planet

**2.1 Plume mask**

- Build spectral tests, e.g. **blue/NIR ratio** or haze index; texture and brightness thresholds; optional ML segmentation.
- **Output:** binary mask **M(x,y) ∈ {0, 1}**.

**2.2 Sub-pixel plume fraction (per TEMPO pixel)**

Aggregate Planet mask pixels that fall inside each TEMPO footprint:

`f_p = Σ(M_Planet) / N`

where **Σ(M_Planet)** is the sum of the mask over Planet pixels inside one TEMPO footprint, and **N** is the number of Planet pixels in that TEMPO pixel.

(Equivalently: plume area within the TEMPO pixel ÷ total TEMPO pixel area, when numerator and denominator use the same grid.)

---

#### 3. Prepare TEMPO NO₂

**3.1 Quality filtering**

- Apply QA for cloud fraction and retrieval quality.
- Exclude or down-weight pixels with **high cloud fraction** (order **~0.2–0.3**, tune to product) and low QA.

**3.2 AMF / vertical sensitivity**

- Slant column density (SCD) and VCD relate as **VCD = SCD / AMF** (as in the product); for checks, **SCD ≈ VCD × AMF**.
- For smoke, the vertical profile may differ from the standard prior; use an **adjusted AMF** from the averaging kernel and an assumed profile:
  **AMF_adj = Σ_z w(z)·AK(z)**
  - **AK(z):** averaging kernel (**from product HDF/NetCDF**).
  - **w(z):** assumed NO₂ vertical shape (e.g. plume height from fire data or literature; scan notes **~0.5–2 km**—**replace with your prior**).
- Adjusted column:
  **VCD_adj = SCD / AMF_adj**

---

#### 4. Isolate plume NO₂ enhancement

**4.1 Background**

- Define an **upwind / background** region outside the plume mask but with **similar surface/urban** character where possible.
- Background column (example from scan):
  **VCD_bg = median(VCD_adj over background pixels)**

**4.2 Excess NO₂**

**ΔVCD = VCD_adj − VCD_bg**

Apply plume overlap:

**ΔVCD_plume = f_p × ΔVCD**

---

#### 5. Convert column to mass

**Mass_NO2 = ΔVCD_plume × A × (molecules → mol → kg)**

- **A:** TEMPO **pixel area** (m²).
- Convert **molecules cm⁻² → mol m⁻² → kg** using Avogadro’s constant (**6.022×10²³** mol⁻¹) and NO₂ molar mass (**≈46 g mol⁻¹**).

**Worked example (from `masscal.pdf`, section “5. Example (NO₂ pixel)”)**

- Assumptions: **VCD = 5×10¹⁵ molecules·cm⁻²**; pixel **3 km × 3 km** → **A = 9×10⁶ m² = 9×10¹⁰ cm²**.
- Molecules in column: **N = 5×10¹⁵ × 9×10¹⁰ = 4.5×10²⁶** molecules.
- Mass: **M = (4.5×10²⁶ / 6.022×10²³) × 46 g·mol⁻¹ ≈ 3435 g ≈ 3.4 kg NO₂** in that pixel column.

---

#### 6. Emission / flux (optional extensions)

**Method A — Mass balance (“box”)**

- **M_total = Σ Mass_NO2** over plume pixels.
- **E = M_total / τ** with **τ** = effective NO₂ lifetime (**~1–6 h**, chemistry-dependent).

**Method B — Flux (cross-section)**

- Define a transect **perpendicular to wind** (details on the original scan continue below this step; complete from your printed copy if you use this path).

---

For setup commands and script index, see **README.md** in the repository root.

---

*Last updated: pilot rasters + `requirements.txt`; locked Palisades data; methodology from `method.pdf` and `masscal.pdf`; formulas in plain/Unicode for reliable Markdown preview.*