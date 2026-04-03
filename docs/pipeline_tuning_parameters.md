# Pipeline tuning parameters (end-to-end)

This document lists **knobs that change numerical outputs** if you adjust them: smoke fraction \(f_p\), background \(VCD_{bg}\), excess column, and reported mass. Use it like a checklist of “sliders” when reproducing or sensitivity-testing a run.

**Related:** [smoke_mask_challenges.md](smoke_mask_challenges.md) (why masks are hard, not more parameters).

---

## Flow (dependency order)

1. **TEMPO L2 → GeoTIFF** — `scripts/tempo_l2_to_4326.py` (VCD grid, QA, optional AMF plume adjustment).
2. **Planet mask / \(f_p\)** — `scripts/smoke_plume_pipeline.py` (and optional QGIS exports: `planet_smoke_mask_qgis.py`, `export_planet_smoke_step2.py`).
3. **Mass from column** — `scripts/column_to_mass.py` (re-integrates `delta_vcd_plume.tif` if you change units or swap rasters).

Changing an **earlier** step’s outputs (especially TEMPO VCD or Planet scene) propagates to everything downstream.

---

## 1. `tempo_l2_to_4326.py` (TEMPO swath → EPSG:4326)

| Parameter | Default | Effect if changed |
|-----------|---------|-------------------|
| `--nc` | *(required)* | Different granule → different scene, time, geometry, QA, and VCD field. |
| `-o` / `--output` | next to `.nc` | Where the warped GeoTIFF is written; downstream scripts point here. |
| `--bbox` W S E N | full valid swath | **Clips** extent and which pixels are interpolated; changes every TEMPO pixel value and overlap with Planet. |
| `--res` | ~long side / 3600°, min 0.005° | **Finer** res → more pixels, different interpolation; **coarser** → smoother fields, different sub-pixel overlap with \(f_p\). |
| `--no-qa` | off (QA on) | If set, keeps pixels with `main_data_quality_flag != 0` → usually **higher** noise / different VCD. |
| `--max-cloud` F | off | Masks high cloud fraction; stricter F → **fewer** pixels, different valid mask and medians. |
| `--ground-qa-zero` | off | Also requires `ground_pixel_quality_flag == 0`; can remove more pixels (check ATBD semantics). |
| `--stack` | off | Writes **multi-band** GeoTIFF (VCD + AMF, cloud, QA…). Affects **`--tempo-vcd-band`** in the main pipeline (band 1 = VCD if stacked as expected). |
| `--amf-plume-adjust` | off | Rescales tropospheric VCD using scattering weights vs assumed vertical plume shape → **systematic** VCD change where enabled. |
| `--plume-height-agl-m` | `1000` | Center height (m AGL) of Gaussian plume used in AMF adjustment → changes rescaling. |
| `--plume-fwhm-m` | `500` | Vertical FWHM (m) of that Gaussian → changes how sensitivity is weighted in height. |

**Implementation note:** `tempo_amf_plume_adjust.py` uses fixed atmosphere approximations (scale height, layer construction); those are **not** CLI parameters but affect results when `--amf-plume-adjust` is on.

---

## 2. `smoke_plume_pipeline.py` (mask → \(f_p\) → \(VCD_{bg}\) → ΔVCD → mass)

### Inputs (largest leverage)

| Parameter | Default | Effect |
|-----------|---------|--------|
| `--planet` | Pilot path under `smoke-plume-data/palisades/` | **Different scene / geometry** → new smoke mask and \(f_p\). |
| `--tempo` | Pilot warped GeoTIFF | **Different VCD grid** → new background, ΔVCD, mass. |
| `--out` | `results/smoke_plume` | Output folder only (does not change math). |

### Vertical column interpretation

| Parameter | Default | Effect |
|-----------|---------|--------|
| `--vcd-units` | `molec_cm2` | Must match the TEMPO GeoTIFF; wrong choice → **wrong mass scaling** (same formula family, different conversion). |
| `--tempo-vcd-band` | `1` | Which band is read as tropospheric VCD. **Must** match how `tempo_l2_to_4326.py` wrote the file (band 1 = VCD; other bands if `--stack`). |

### Smoke mask and \(f_p\)

| Parameter | Default | Effect |
|-----------|---------|--------|
| `--mask-method` | `blue_nir` | Switches rule: `blue_nir`, `ndhi` (G–B / G+B), or `ndhi_bnir` (B–NIR / B+NIR) → different mask and \(f_p\). |
| `--blue-nir-max` | `0.42` | For `blue_nir`: smoke where B/NIR **below** this → **strong** sensitivity of plume area. |
| `--ndhi-smoke-below` | `0.0` | For `ndhi`: smoke where green–blue NDHI **below** this. |
| `--ndhi-bnir-smoke-above` | `-0.15` | For `ndhi_bnir`: smoke where (B−NIR)/(B+NIR) **above** this. |
| `--mask-nodata` | `-9999` | Invalid mask pixels for warp; should match GeoTIFF nodata. Changing without consistent files can affect \(f_p\) averaging at edges. |
| `--blue-band` | `2` | Wrong band → wrong reflectances and mask. |
| `--nir-band` | `8` | Same (Planet 8-band SR convention). |
| `--green-band` | `3` | Used for `--mask-method ndhi` only. |

### Background \(VCD_{bg}\) and excess column

| Parameter | Default | Effect |
|-----------|---------|--------|
| `--fp-bg-max` | `0.02` | Max \(f_p\) for pixels eligible for **background median**. Higher → more “smoky” pixels can enter \(VCD_{bg}\) → **lower** typical \(VCD_{bg}\) and **larger** ΔVCD (and mass). |

### Outputs

| Flag | Effect |
|------|--------|
| `--write-maps` | Writes `f_p.tif`, `delta_vcd.tif`, `delta_vcd_plume.tif`; mass in JSON is still computed either way when the script runs. |

### Internal fallbacks (not CLI — change code to tune)

These alter \(VCD_{bg}\) when there are **few** low-\(f_p\) pixels:

- If count of `f_p <= fp_bg_max` is **&lt; 50**, the pipeline relaxes to `f_p <= min(0.05, fp_bg_max + 0.03)`.
- If still **&lt; 10**, it uses the **15th percentile** of valid VCD over all valid pixels instead of the median over low-\(f_p\) pixels.

**Summary stats only (not mass):** `pixels_plume_fp_gt_0.01` uses a fixed **`f_p > 0.01`** threshold in code.

---

## 3. `export_planet_smoke_step2.py` (Step 2 checkpoint)

Same **mask-related** parameters as the main pipeline for Planet exports (`--mask-method`, `--blue-nir-max`, `--ndhi-*`, bands, `--mask-nodata`) plus **`--preview-max-side`** (preview resolution only — does not change full-res mask or \(f_p\) written at full resolution).

| Parameter | Effect |
|-----------|--------|
| `--planet`, `--tempo`, `--out` | Paths; different inputs → different outputs. |

---

## 4. `planet_smoke_mask_qgis.py` (QGIS-oriented exports)

Same mask tunables as §2–3. Additional:

| Parameter | Effect |
|-----------|--------|
| `--preview-max-side` | Preview size only. |
| `--no-preview` / `--mask-only` | What files are written; full-res mask unchanged if produced. |
| `--with-fp` | Computes `f_p_tempo_grid.tif` using same warp as pipeline when `--tempo` is set. |

---

## 5. `column_to_mass.py` (Step 5 re-mass from raster)

| Parameter | Default | Effect |
|-----------|---------|--------|
| `--raster` | step_04 plume raster | **Different GeoTIFF** → different integrated mass (e.g. after regenerating `delta_vcd_plume.tif`). |
| `--vcd-units` | `molec_cm2` | Must match raster units; wrong value → **wrong kg**. |
| `--out-json` | `results/step_05_mass/column_mass.json` | Output path only. |

Constants **`AVOGADRO`** and **`M_NO2_KG_PER_MOL`** in `smoke_plume_pipeline.py` define the conversion; change only for a deliberate unit/molar-mass revision.

---

## 6. Other scripts (minor / diagnostic)

| Script | Tunables |
|--------|----------|
| `compare_ratio_nd_smoke_mask.py` | `--blue-nir-max`, `--blue-band`, `--nir-band`, `--planet` — comparison only. |
| `smoke_plume_sanity_check.py` | `--results-dir` — reads existing outputs; does not change pipeline numbers. |

---

## 7. Batch and study-batch helpers

### `run_all_cases.py` (many regions, one CLI)

Runs `smoke_plume_pipeline.run(...)` once per discovered case. **All pipeline numeric flags** mirror the main pipeline (same defaults as §2): `--vcd-units`, `--mask-method`, `--blue-nir-max`, `--ndhi-smoke-below`, `--ndhi-bnir-smoke-above`, `--mask-nodata`, `--fp-bg-max`, `--blue-band`, `--nir-band`, `--green-band`, `--tempo-vcd-band`, `--write-maps`.

| Parameter | Default | Effect |
|-----------|---------|--------|
| `--cases-root` | *(optional if manifest set)* | Folder with one subfolder per region (`case.json` or `planet.tif` + `tempo.tif`). |
| `--manifest` | off | JSON list of cases (see `cases_manifest.example.json`); alternative to `--cases-root`. |
| `--out-root` | *(required)* | Base output; each case writes to `out-root/<case_id>/`. |
| `--dry-run` | off | List cases only; no pipeline runs. |
| `--fail-fast` | off | Stop on first failure; default is run all and record errors in `batch_summary.json`. |

Case-specific inputs come from each folder’s `case.json` (paths, optional `time_match`), not from extra CLI knobs.

### `study_batch_visuals.py` (maps + PNG previews after the fact)

Re-runs the pipeline with parameters **read from** each case’s `pipeline_summary.json`, then runs `smoke_plume_sanity_check.py`. Does not introduce new **math** parameters beyond what is already stored in that JSON.

| Parameter | Default | Effect |
|-----------|---------|--------|
| `--results-root` | `results/study_batch` | Parent of per-case folders (`airport`, `bridge`, …). |
| `--only` | off | Space-separated case ids; if omitted, every case with `pipeline_summary.json` is processed. |

### `smoke_plume_sanity_check.py`

| Parameter | Default | Effect |
|-----------|---------|--------|
| `--results-dir` | pilot results path | Folder with pipeline outputs; writes `maps/*.png`, `sanity_report.json`. Read-only for VCD/mass numbers unless you re-run the pipeline first. |

---

## Quick “sensitivity” order (what to move first)

1. **Inputs:** TEMPO granule / warping (`--bbox`, `--res`, QA, cloud, **`--amf-plume-adjust`** and height/FWHM).  
2. **Planet scene** and **mask method** + thresholds (`--blue-nir-max`, `--ndhi-*`, `--mask-method`).  
3. **Background** (`--fp-bg-max`).  
4. **Band index** mistakes (`--tempo-vcd-band`, Planet bands).  
5. **`--vcd-units`** anywhere VCD is interpreted (pipeline + `column_to_mass.py`).

Recording **`pipeline_summary.json`** after each run captures most CLI-relevant parameters for the main pipeline step.
