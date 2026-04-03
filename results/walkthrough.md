## Smoke plume NO₂ — Walkthrough log

This file is a **running lab notebook** for the pipeline. Each step records:

- **Inputs** (file names, times, versions)
- **Actions** (what we did / which script)
- **Outputs** (what got written, where)
- **Observations** (what we noticed, assumptions, caveats)

---

## Step 1 — Acquire coincident data (Planet + TEMPO) and lock metadata

### Inputs (locked)

- **Planet (SR, 8-band GeoTIFF)**: `smoke-plume-data/palisades/planet/20250110_185256_28_24e1_3B_AnalyticMS_SR_8b.tif`
  - **Acquired (UTC)**: `2025-01-10T18:52:56.288697Z`
  - **Bands used by our mask prototype** (1-based): Blue = **2**, NIR = **8**
  - **Sidecar**: `smoke-plume-data/palisades/planet/20250110_185256_28_24e1_metadata.json`

- **TEMPO NO₂ L2 V03 (NetCDF)**: `smoke-plume-data/palisades/tempo/TEMPO_NO2_L2_V03_20250110T184529Z_S008G09.nc`
  - **time_coverage_start/end (UTC)**: `2025-01-10T18:45:29Z → 18:52:06Z`
  - **Key variables present** (as confirmed from the file variable list):
    - **Tropospheric NO₂ VCD**: `/product/vertical_column_troposphere`
    - **QA**: `/product/main_data_quality_flag`
    - **AMF**: `/support_data/amf_total`, `/support_data/amf_troposphere`, `/support_data/amf_stratosphere`
    - **Cloud fraction**: `/support_data/eff_cloud_fraction` (plus AMF cloud fraction/pressure)
    - **SCD**: `/support_data/fitted_slant_column`
    - **Profiles**: `/support_data/gas_profile`, `/support_data/temperature_profile`

### Actions

- Confirmed Planet has the spectral bands needed for the initial smoke mask (Blue + NIR).
- Confirmed TEMPO file contains **tropospheric NO₂ VCD** (not "all gases") plus QA and AMF-related fields.
- Checked for an **averaging kernel (AK)** as a named variable.

### Outputs (checkpoint)

- Step 1 checkpoint folder: `results/step_01_inputs/`
  - `README.md` — what to load/inspect
  - `qgis_layers_step_01.txt` — QGIS layer checklist
  - `step_01_manifest.json` — machine-readable manifest of metadata and variable inventory

### Observations / caveats

- **Time match**: Planet acquisition is ~**50 seconds after** the TEMPO granule end time.
  - This is acceptable for the pilot but is a sensitivity risk if the plume advects quickly.
- **Averaging kernel**: we did **not** find an AK variable exposed by name in this granule's variable list.
  - We do have **AMF**, cloud fraction, SCD, and a `gas_profile`, but not an explicit AK field (as of Step 1).

---

## Step 2 — Detect smoke plume on Planet (plume mask)

### Goal

Create a **binary smoke mask** \(M\) on the **native high-resolution Planet** image, then aggregate it to TEMPO pixels as a **sub-pixel smoke fraction** \(f_p\).

### Inputs

- **Planet (SR, 8-band GeoTIFF)**: `smoke-plume-data/palisades/planet/20250110_185256_28_24e1_3B_AnalyticMS_SR_8b.tif`
  - **Bands used (1-based)**: Blue = **2**, NIR = **8**
  - CRS (from Step 1 manifest): **EPSG:32611**

### Actions (what we actually implemented in code for the pilot)

1. Read Blue and NIR from the Planet SR raster.
2. Compute ratio: **Blue/NIR** (with a small floor in denominator for safety).
3. Define smoke mask:
   - **M = (Blue/NIR < blue_nir_max)** AND finite bands
   - Pilot default parameter: **blue_nir_max = 0.42**

This is a **prototype heuristic** mask (fast + inspectable). It can confuse thin cloud/haze/bright surfaces with smoke; intermediate rasters are written for QGIS inspection.

### Sub-pixel plume fraction \(f_p\) (yes — implemented)

**Critical:** In `scripts/smoke_plume_pipeline.py`, `reproject_mask_to_tempo` warps the **Planet smoke mask** to the **TEMPO** grid using **`Resampling.average`**. Each TEMPO pixel holds a value in **[0, 1]** = **mean mask value** over that footprint = **smoke area fraction** for a 0/1 mask. That is **`f_p`**, used as `delta_vcd_plume = f_p * (VCD - VCD_bg)`.

Export for QGIS (same math): `python scripts/export_planet_smoke_step2.py` writes `results/step_02_plume_mask/f_p_tempo_grid.tif`.

### Outputs (checkpoint)

Folder: `results/step_02_plume_mask/`

- `README.md`, `qgis_layers_step_02.txt`
- **Full-res:** `planet_blue_nir_ratio.tif`, `planet_smoke_mask.tif`
- **Preview (~2048 px max side):** `planet_blue_nir_ratio_preview.tif`, `planet_smoke_mask_preview.tif`
- **TEMPO grid:** `f_p_tempo_grid.tif`

### Observations / caveats

- This mask is **not final**; it is intentionally simple to get the pipeline working end-to-end.
- **`f_p` quality** depends on mask quality; misclassified Planet pixels change the fraction inside each TEMPO cell.

---

## Step 3 — TEMPO NO₂: QA, cloud filter, optional plume AMF adjustment, AMF stack

### Goal

Optionally **rescale tropospheric VCD** for an assumed **plume height** (default **1 km AGL**) using **`scattering_weights`** + **`gas_profile`** prior vs a Gaussian in height; then **QA + cloud** mask; grid to EPSG:4326; optionally **`--stack`** ancillary layers.

### Script / actions

- **`scripts/tempo_amf_plume_adjust.py`** — defines \( \mathrm{VCD}_{adj} = \mathrm{VCD} \times (\mathrm{AMF}_{trop}/\mathrm{AMF}_{adj}) \) with **`--plume-height-agl-m`** / **`--plume-fwhm-m`**.
- **`scripts/tempo_l2_to_4326.py`**: **`--amf-plume-adjust`**, QA, cloud, **`--stack`**.

### Outputs (checkpoint)

- `results/step_03_tempo_qa/README.md` — band table + CLI
- GeoTIFF tags include **`AMF_PLUME_ADJUST`**, **`PLUME_HEIGHT_AGL_M`**, **`PLUME_FWHM_M`** when adjustment is on.

### Downstream

- **`scripts/smoke_plume_pipeline.py`** uses **band 1** as VCD (`--tempo-vcd-band`, default **1**).

### Observations / caveats

- Adjustment uses an **approximate** height–pressure relation and product **vertical sensitivity**; compare to **TEMPO ATBD** for rigorous uncertainty.
- **Plume height** (0.5–2 km literature) is tunable via **`--plume-height-agl-m`**.

---

## Step 4 — Isolate plume NO₂ enhancement (background + excess column)

### Goal

Estimate a **background column** \(VCD_{bg}\), compute **excess** \(\Delta VCD = VCD - VCD_{bg}\), then restrict to the plume with **\(f_p\)** from Step 2: \(\Delta VCD_{plume} = f_p \times \Delta VCD\).

### Script / actions

- **`scripts/smoke_plume_pipeline.py`** — uses **band 1** TEMPO VCD (after Step 3 processing), Planet \(f_p\), **`--fp-bg-max`** for background pixel selection, **`--write-maps`** to export rasters.

### Outputs (checkpoint)

- Folder: **`results/step_04_plume_enhancement/`** — see `README.md`
- **`delta_vcd.tif`** — full-field \(\Delta VCD\); **`delta_vcd_plume.tif`** — \(f_p \times \Delta VCD\); **`f_p.tif`**; plus **`pipeline_summary.json`**.

### Observations / caveats

- Background is **median VCD where \(f_p\) is small** in the same scene, not a separate upwind polygon.
- Urban or regional NO₂ can bias \(VCD_{bg}\); interpret excess as **scene-relative enhancement**.

---

## Step 5 — Convert column to mass (kg NO₂)

### Goal

Integrate **plume-weighted excess column** \(\Delta VCD_{plume}\) (molecules/cm²) over each TEMPO pixel area and convert to **kg NO₂** using Avogadro’s constant and molar mass (46 g/mol).

### Script / actions

- **`scripts/smoke_plume_pipeline.py`** — computes **`total_excess_no2_kg`** (same integral as Step 5).
- **`scripts/column_to_mass.py`** — recomputes mass from **`delta_vcd_plume.tif`** only; writes **`results/step_05_mass/column_mass.json`** for verification.

### Outputs (checkpoint)

- **`results/step_05_mass/README.md`** — formula and CLI
- **`results/step_05_mass/column_mass.json`** — produced by `column_to_mass.py`

### Observations / caveats

- Mass is **column × area** in consistent units; large-scale accuracy depends on Step 3–4 inputs (VCD, background, \(f_p\)).
- **`masscal.pdf`** (§5 style) is the **same** recipe as Step 5; see **`results/step_05_mass/README.md`**. Optional **§6** in `PROJECT.md` is **emission / flux** after mass, not another mass conversion.
