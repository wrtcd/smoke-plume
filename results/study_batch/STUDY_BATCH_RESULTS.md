# Study batch — smoke plume NO₂ pipeline results

Report generated: **2026-04-06** (full regeneration after TEMPO preprocessing policy: `main_data_quality_flag == 0`, **`eff_cloud_fraction` ≤ 0.2**, tropospheric VCD retained including **negative** values where valid; see `scripts/tempo_l2_to_4326.py` and `scripts/smoke_plume_pipeline.py`).

## What was run

- **TEMPO L2 → GeoTIFF:** `scripts/tempo_l2_to_4326.py` per region (default **`--max-cloud 0.2`**; no extra cloud flags). Each study folder’s granule was warped to `tempo/TEMPO_NO2_trop_warped_4326.tif` (overwritten).
- **Main pipeline:** `scripts/smoke_plume_pipeline.py` via `scripts/run_all_cases.py` (`mask_method=blue_nir`, `blue_nir_max=0.42`, `fp_background_max=0.02`, TEMPO VCD units `molec_cm2`, bands Blue=2 / NIR=8).
- **Regions:** six folders under `smoke-plume-data/` with `case.json`.
- **Outputs per case:** `results/study_batch/<region>/pipeline_summary.json`, `pipeline_table.csv`, maps (`f_p.tif`, `delta_vcd.tif`, `delta_vcd_plume.tif`), `maps/*.png`, sanity artifacts.
- **Batch index:** `results/study_batch/batch_summary.json`.
- **Figures for docs:** `scripts/render_case_study_comparison.py`, `scripts/sync_guide_case_images.py`.

## Summary table

| Region | Status | Total excess NO₂ (kg) | VCD background median (molec/cm²) | TEMPO pixels | Plume pixels (f_p > 0.01) |
|--------|--------|----------------------:|-----------------------------------:|-------------:|-------------------------:|
| airport | ok | 1,539.92 | 3.81 × 10¹⁴ | 9,312,186 | 470 |
| bridge | ok | 4,000.93 | 5.00 × 10¹⁴ | 8,550,000 | 532 |
| eaton | ok | 1,701.86 | 5.72 × 10¹⁴ | 7,941,600 | 840 |
| line | ok | 2,769.43 | 6.80 × 10¹⁴ | 7,952,400 | 433 |
| palisades | ok | 1,466.93 | 6.50 × 10¹⁴ | 8,920,800 | 901 |
| park | ok | 1,485.69 | 3.18 × 10¹⁴ | 9,680,400 | 662 |

Values are from each `pipeline_summary.json` under `results/study_batch/<region>/` for this batch.

## Plain-English pipeline guide

Step-by-step explanation with diagrams (and pointers to these previews): **[docs/pipeline_layman_guide.md](../../docs/pipeline_layman_guide.md)**.

## Visual outputs (PNG + GeoTIFF maps)

Generated with `scripts/study_batch_visuals.py` (re-runs each case with map writes, then `smoke_plume_sanity_check.py`).

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
- **Time collocation (bridge):** see `time_match` in `smoke-plume-data/bridge/case.json` and `results/study_batch/bridge/pipeline_summary.json`.

## Reproduce

Warp TEMPO (defaults include cloud ≤ 0.2), then batch:

```powershell
py -3 scripts/tempo_l2_to_4326.py --nc smoke-plume-data/palisades/tempo/<granule>.nc -o smoke-plume-data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif
py -3 scripts/run_all_cases.py --cases-root smoke-plume-data --out-root results/study_batch --write-maps
```

## Caveats

- Masses depend on **mask thresholds**, **background** definition on low-f_p pixels, and **TEMPO** QA/cloud/VCD policy in `tempo_l2_to_4326.py`.
- **VCD background** is in **molecules/cm²** (large magnitudes are expected).
- Cross-region **comparability** is limited: different fires, dates, granules, and swath extents.
