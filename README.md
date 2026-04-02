# smoke-plume

Estimate **NO₂** associated with **smoke plumes** by combining **PlanetScope** (high-res smoke mask / overlap fraction \(f_p\)) with **TEMPO** tropospheric NO₂ **vertical column density** (VCD), background subtraction, and column-to-mass conversion.

## Documentation

| Document | Contents |
|----------|----------|
| [PROJECT.md](PROJECT.md) | Goals, locked pilot data, methodology (from scanned notes), notation |
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

Large rasters (`*.tif`, `*.nc`) are **gitignored**; keep them under `data/` locally. Do **not** `pip install gdal` into this venv—use OSGeo4W/QGIS GDAL on PATH if needed, or `scripts/tempo_l2_to_4326.py` for swath→GeoTIFF.

## Typical run (after placing pilot rasters per PROJECT.md)

```powershell
python scripts/tempo_l2_to_4326.py --nc data/palisades/tempo/<granule>.nc -o data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif
python scripts/palisades_pipeline.py --write-maps
python scripts/palisades_sanity_check.py
```

Default pipeline outputs: **`results/palisades/`** (mostly gitignored; JSON/maps are local). Walkthrough checkpoints also use **`results/step_01_inputs/`** … **`step_05_mass/`** (see walkthrough).

## Scripts (overview)

| Script | Role |
|--------|------|
| `tempo_l2_to_4326.py` | TEMPO L2 NetCDF → EPSG:4326 GeoTIFF (QA, cloud, optional AMF plume adjust) |
| `tempo_amf_plume_adjust.py` | AMF rescaling helper (used by tempo script) |
| `palisades_pipeline.py` | Planet mask → \(f_p\), \(VCD_{bg}\), ΔVCD, mass; optional GeoTIFF maps |
| `export_planet_smoke_step2.py` | Step 2: Planet mask + \(f_p\) exports |
| `planet_smoke_mask_qgis.py` | QGIS-oriented mask + index layers |
| `column_to_mass.py` | Integrate `delta_vcd_plume.tif` → kg NO₂ |
| `palisades_sanity_check.py` | Quick checks + preview maps from pipeline outputs |
| `compare_ratio_nd_smoke_mask.py` | Optional: algebra check (B/NIR ratio vs normalized difference threshold) |

## Repository layout

```
├── PROJECT.md              # Science + methodology reference
├── README.md               # This file
├── requirements.txt
├── data/                   # Local-only rasters (see data/README.md)
├── docs/                   # Guides (mask challenges, tuning knobs, fire AOIs)
├── scripts/                # Python pipeline
└── results/                # Walkthrough *.md tracked; other outputs gitignored
```

Reference PDFs **`method.pdf`**, **`masscal.pdf`** live at repo root (see PROJECT.md).
