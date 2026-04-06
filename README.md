# smoke-plume

Estimate **NO₂** associated with **smoke plumes** by combining **PlanetScope** (high-res smoke mask / overlap fraction \(f_p\)) with **TEMPO** tropospheric NO₂ **vertical column density** (VCD), background subtraction, and column-to-mass conversion.

## Documentation

| Document | Contents |
|----------|----------|
| [PROJECT.md](PROJECT.md) | Goals, locked pilot data, methodology (from scanned notes), notation |
| [docs/pipeline_layman_guide.md](docs/pipeline_layman_guide.md) | Beginner-friendly pipeline tour (steps, diagrams, glossary) |
| [docs/README.md](docs/README.md) | Index of guides (mask caveats, tuning parameters, fire AOIs) |
| [results/walkthrough.md](results/walkthrough.md) | Step-by-step lab log (inputs, scripts, checkpoints) |

## Environment (Windows)

1. Install **Python 3.10+** (user install is fine; no admin required): [python.org/downloads](https://www.python.org/downloads/)
2. From the repo root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Large rasters (`*.tif`, `*.nc`) are **gitignored**; study-region folders live under **`smoke-plume-data/`** (see `smoke-plume-data/README.md`). Do **not** `pip install gdal` into this venv—use OSGeo4W/QGIS GDAL on PATH if needed, or `scripts/tempo_l2_to_4326.py` for swath→GeoTIFF.

## Typical run (after placing pilot rasters per PROJECT.md)

```powershell
py -3 scripts/tempo_l2_to_4326.py --nc smoke-plume-data/palisades/tempo/<granule>.nc -o smoke-plume-data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif
py -3 scripts/smoke_plume_pipeline.py --write-maps
py -3 scripts/smoke_plume_sanity_check.py
```

`tempo_l2_to_4326.py` defaults: **`main_data_quality_flag == 0`**, mask **`eff_cloud_fraction` > 0.2**, tropospheric VCD **may be negative** (not stripped before gridding). Use **`--no-cloud-mask`** only if you need to skip cloud screening.

`smoke_plume_pipeline.py` domain policy: TEMPO is **subset to the Planet scene bounds** before computing \(f_p\), background, ΔVCD, and mass (so missing Planet coverage is not treated as clear sky).

Batch (six regions under `smoke-plume-data/`, each with `case.json`):

```powershell
python scripts/run_all_cases.py --cases-root smoke-plume-data --out-root results/study_batch --write-maps
```

Default single-run outputs: **`results/smoke_plume/`** (mostly gitignored; JSON/maps are local). Walkthrough checkpoints also use **`results/step_01_inputs/`** … **`step_05_mass/`** (see walkthrough).

## Scripts (overview)

| Script | Role |
|--------|------|
| `tempo_l2_to_4326.py` | TEMPO L2 NetCDF → EPSG:4326 GeoTIFF (QA, cloud, optional AMF plume adjust) |
| `tempo_amf_plume_adjust.py` | AMF rescaling helper (used by tempo script) |
| `smoke_plume_pipeline.py` | Planet mask → \(f_p\), \(VCD_{bg}\), ΔVCD, mass; optional GeoTIFF maps |
| `export_planet_smoke_step2.py` | Step 2: Planet mask + \(f_p\) exports |
| `planet_smoke_mask_qgis.py` | QGIS-oriented mask + index layers |
| `column_to_mass.py` | Integrate `delta_vcd_plume.tif` → kg NO₂ |
| `smoke_plume_sanity_check.py` | Quick checks + preview maps from pipeline outputs |
| `compare_ratio_nd_smoke_mask.py` | Optional: algebra check (B/NIR ratio vs normalized difference threshold) |
| `run_all_cases.py` | Run `smoke_plume_pipeline` for many regions (folder layout or JSON manifest → `batch_summary.json`) |
| `study_batch_visuals.py` | For each `results/study_batch/<case>/`: write map GeoTIFFs + PNG previews (`maps/*.png`) via sanity check |
| `render_pipeline_guide_assets.py` | Build small schematic PNGs in `docs/images/` for [pipeline_layman_guide.md](docs/pipeline_layman_guide.md) |
| `render_case_study_comparison.py` | Build six-case bar/scatter figures in `docs/images/` from `results/study_batch/*/pipeline_summary.json` |
| `gee_tempo_l3_no2_layers.js` | Optional: Earth Engine — TEMPO NO₂ L3 QA-filtered maps (edit AOI/dates) |

## Repository layout

```
├── PROJECT.md              # Science + methodology reference
├── README.md               # This file
├── requirements.txt
├── smoke-plume-data/       # Study regions: planet/ + tempo/ per folder (see smoke-plume-data/README.md)
├── docs/                   # Guides (mask challenges, tuning knobs, fire AOIs)
├── scripts/                # Python pipeline
└── results/                # Walkthrough *.md tracked; other outputs gitignored
```

Reference PDFs **`method.pdf`**, **`masscal.pdf`** live at repo root (see PROJECT.md).
