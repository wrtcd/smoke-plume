# Study batch — smoke plume NO₂ pipeline results

Report generated: **2026-04-03** (bridge case re-run after Planet SR asset fix; other regions unchanged since last full batch).

## What was run

- **Script:** `scripts/smoke_plume_pipeline.py` (same defaults as `scripts/run_all_cases.py`: `mask_method=blue_nir`, `blue_nir_max=0.42`, `fp_background_max=0.02`, TEMPO VCD units `molec_cm2`, bands Blue=2 / NIR=8).
- **Regions:** six folders under `smoke-plume-data/` with `case.json`.
- **Outputs per case:** `results/study_batch/<region>/pipeline_summary.json`, `pipeline_table.csv`.
- **Batch index:** `results/study_batch/batch_summary.json` (bridge row updated to match the re-run).

## Summary table

| Region | Status | Total excess NO₂ (kg) | VCD background median (molec/cm²) | TEMPO pixels | Plume pixels (f_p > 0.01) |
|--------|--------|----------------------:|-----------------------------------:|-------------:|-------------------------:|
| airport | ok | 1,515.49 | 5.48 × 10¹⁴ | 9,640,800 | 467 |
| bridge | ok | 3,986.60 | 8.26 × 10¹⁴ | 8,874,000 | 534 |
| eaton | ok | 1,957.25 | 6.74 × 10¹⁴ | 8,035,200 | 845 |
| line | ok | 2,831.66 | 6.92 × 10¹⁴ | 8,222,400 | 433 |
| palisades | ok | 1,375.01 | 9.20 × 10¹⁴ | 2,096,220 | 73 |
| park | ok | 1,237.55 | 5.86 × 10¹⁴ | 9,309,600 | 649 |

Values are taken from each `pipeline_summary.json` under `results/study_batch/<region>/` (bridge updated **2026-04-03**; others from the prior successful batch on the same machine).

## Plain-English pipeline guide

Step-by-step explanation with diagrams (and pointers to these previews): **[docs/pipeline_layman_guide.md](../../docs/pipeline_layman_guide.md)**.

## Visual outputs (PNG + GeoTIFF maps)

Generated **2026-04-03** with `scripts/study_batch_visuals.py` (re-runs each case with map writes, then `smoke_plume_sanity_check.py`). Total runtime ~3–4 minutes for all six cases on a typical laptop.

**Per region** (`results/study_batch/<region>/`):

| Artifact | Description |
|----------|-------------|
| `maps/f_p_preview.png` | Plume overlap fraction **f_p** on the TEMPO grid (cropped near plume, magma colormap). |
| `maps/delta_vcd_plume_preview.png` | **f_p × ΔVCD** (plume-weighted excess column), same crop. |
| `maps/histograms.png` | Distributions of f_p and log10(plume ΔVCD) where f_p > 0.01. |
| `f_p.tif`, `delta_vcd.tif`, `delta_vcd_plume.tif` | Full-resolution GeoTIFFs (large files; full swath extent). |
| `sanity_report.json`, `sanity_table.csv` | Checks + scalar exports from the sanity step. |

Regenerate (all cases):

```powershell
py -3 scripts/study_batch_visuals.py --results-root results/study_batch
```

Single case:

```powershell
py -3 scripts/study_batch_visuals.py --results-root results/study_batch --only palisades
```

## Bridge — Planet asset correction

- **Issue:** An earlier bridge Planet file was **not** analytic **surface reflectance** (`AnalyticMS_8b.tif` without `_SR_`). The blue/NIR smoke mask did not behave like the other study scenes, producing **0** TEMPO pixels with f_p > 0.01 and negligible mass.
- **Fix:** Use **PSScene analytic SR** 8-band: `smoke-plume-data/bridge/planet/20240910_184221_67_24f3_3B_AnalyticMS_SR_8b.tif`, referenced in `smoke-plume-data/bridge/case.json`.
- **After re-run:** **534** plume pixels (f_p > 0.01) and **~3,987 kg** total excess NO₂ (same pipeline parameters as other regions).
- **Time collocation (bridge):** see `time_match` in `smoke-plume-data/bridge/case.json` and `results/study_batch/bridge/pipeline_summary.json`.

## Reproduce

Full batch (all regions):

```powershell
py -3 scripts/run_all_cases.py --cases-root smoke-plume-data --out-root results/study_batch
```

Bridge only (after editing paths if needed):

```powershell
py -3 scripts/smoke_plume_pipeline.py `
  --planet smoke-plume-data/bridge/planet/20240910_184221_67_24f3_3B_AnalyticMS_SR_8b.tif `
  --tempo smoke-plume-data/bridge/tempo/TEMPO_NO2_trop_warped_4326.tif `
  --out results/study_batch/bridge
```

## Caveats

- Masses are **method-dependent** (mask thresholds, background definition on low-f_p pixels, TEMPO QA/cloud policy in `tempo_l2_to_4326.py`).
- **VCD background** is reported in **molecules/cm²** (large magnitudes are expected).
- Cross-region **comparability** is limited: different fires, dates, granules, and scene extents.
