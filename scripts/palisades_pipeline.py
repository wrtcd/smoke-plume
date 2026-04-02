"""
Palisades pilot pipeline (TODO 3): time-match metadata, Planet smoke mask,
overlap fraction f_p on TEMPO grid, background subtraction, excess column,
total NO2 mass.

Expects pilot rasters from PROJECT.md (local; *.tif is gitignored):
  - data/palisades/planet/20250110_185256_28_24e1_3B_AnalyticMS_SR_8b.tif
  - data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif

Run from repo root:
  .\\.venv\\Scripts\\Activate.ps1
  python scripts/palisades_pipeline.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLANET = REPO_ROOT / "data/palisades/planet/20250110_185256_28_24e1_3B_AnalyticMS_SR_8b.tif"
DEFAULT_TEMPO = REPO_ROOT / "data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif"
DEFAULT_OUT_DIR = REPO_ROOT / "results/palisades"

# Default: PlanetScope 8-band analytic SR (1-based): Blue=2, NIR=8 (see --blue-band / --nir-band)

AVOGADRO = 6.022_140_76e23
M_NO2_KG_PER_MOL = 46e-3

TIME_MATCH = {
    "tempo_granule_utc": "2025-01-10T18:45:29Z → 2025-01-10T18:52:06Z",
    "planet_acquired_utc": "2025-01-10T18:52:56.288697Z",
    "note": "Planet ~50 s after granule end; prefer next L2 granule or explicit ±Δt (PROJECT.md).",
}


def _pixel_areas_m2(transform: rasterio.Affine, height: int, width: int) -> np.ndarray:
    res_lon = abs(transform[0])
    res_lat = abs(transform[4])
    cols = np.arange(width, dtype=np.float64)
    rows = np.arange(height, dtype=np.float64)
    lon = transform[2] + (cols + 0.5) * transform[0]
    lat = transform[5] + (rows + 0.5) * transform[4]
    lon_g, lat_g = np.meshgrid(lon, lat)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * np.cos(np.radians(lat_g))
    return (res_lon * m_per_deg_lon) * (res_lat * m_per_deg_lat)


def smoke_mask_from_sr(
    blue: np.ndarray,
    nir: np.ndarray,
    blue_nir_max: float,
) -> np.ndarray:
    denom = np.maximum(nir, 1e-8)
    ratio = blue / denom
    return (ratio < blue_nir_max) & np.isfinite(blue) & np.isfinite(nir)


def load_tempo_vcd(path: Path) -> tuple[np.ndarray, rasterio.DatasetReader]:
    ds = rasterio.open(path)
    arr = ds.read(1).astype(np.float64)
    nodata = ds.nodata
    if nodata is not None:
        arr = np.where(arr == nodata, np.nan, arr)
    return arr, ds


def reproject_mask_to_tempo(
    planet_ds: rasterio.DatasetReader,
    mask: np.ndarray,
    tempo_ds: rasterio.DatasetReader,
) -> np.ndarray:
    dst = np.zeros((tempo_ds.height, tempo_ds.width), dtype=np.float32)
    reproject(
        source=mask.astype(np.float32),
        destination=dst,
        src_transform=planet_ds.transform,
        src_crs=planet_ds.crs,
        dst_transform=tempo_ds.transform,
        dst_crs=tempo_ds.crs,
        resampling=Resampling.average,
    )
    return np.clip(dst, 0.0, 1.0)


def excess_mass_molec_cm2(
    delta_vcd_plume: np.ndarray,
    area_m2: np.ndarray,
) -> float:
    """Total mass (kg) when VCD is in molecules/cm²."""
    a_cm2 = area_m2 * 1.0e4
    molecules = np.nansum(delta_vcd_plume * a_cm2)
    return float(molecules / AVOGADRO * M_NO2_KG_PER_MOL)


def excess_mass_mol_m2(delta_vcd_plume: np.ndarray, area_m2: np.ndarray) -> float:
    """Total mass (kg) when VCD is in mol/m²."""
    moles = np.nansum(delta_vcd_plume * area_m2)
    return float(moles * M_NO2_KG_PER_MOL)


def run(
    planet_path: Path,
    tempo_path: Path,
    out_dir: Path,
    vcd_units: str,
    blue_nir_max: float,
    fp_bg_max: float,
    write_maps: bool,
    band_blue: int,
    band_nir: int,
) -> dict:
    if not planet_path.is_file():
        raise FileNotFoundError(f"Missing Planet raster: {planet_path}")
    if not tempo_path.is_file():
        raise FileNotFoundError(f"Missing TEMPO raster: {tempo_path}")

    out_dir.mkdir(parents=True, exist_ok=True)

    vcd, tempo_ds = load_tempo_vcd(tempo_path)
    h, w = vcd.shape

    with rasterio.open(planet_path) as planet_ds:
        if planet_ds.count < band_nir:
            raise ValueError(f"Expected >= {band_nir} bands, got {planet_ds.count}")
        blue = planet_ds.read(band_blue).astype(np.float64)
        nir = planet_ds.read(band_nir).astype(np.float64)
        pnod = planet_ds.nodata
        if pnod is not None:
            blue = np.where(blue == pnod, np.nan, blue)
            nir = np.where(nir == pnod, np.nan, nir)

        mask = smoke_mask_from_sr(blue, nir, blue_nir_max)
        f_p = reproject_mask_to_tempo(planet_ds, mask, tempo_ds)

    valid = np.isfinite(vcd) & (vcd > 0)
    bg_sel = valid & (f_p <= fp_bg_max)
    if np.sum(bg_sel) < 50:
        bg_sel = valid & (f_p <= min(0.05, fp_bg_max + 0.03))
    if np.sum(bg_sel) < 10:
        vcd_bg = float(np.nanpercentile(vcd[valid], 15))
    else:
        vcd_bg = float(np.nanmedian(vcd[bg_sel]))

    delta = np.where(valid, vcd - vcd_bg, np.nan)
    delta_plume = f_p.astype(np.float64) * delta

    area = _pixel_areas_m2(tempo_ds.transform, h, w)
    if vcd_units == "molec_cm2":
        mass_kg = excess_mass_molec_cm2(delta_plume, area)
    elif vcd_units == "mol_m2":
        mass_kg = excess_mass_mol_m2(delta_plume, area)
    else:
        raise ValueError(vcd_units)

    plume_mask = f_p > 0.01
    summary = {
        "time_match": TIME_MATCH,
        "inputs": {"planet": str(planet_path), "tempo": str(tempo_path)},
        "parameters": {
            "vcd_units": vcd_units,
            "blue_nir_max": blue_nir_max,
            "fp_background_max": fp_bg_max,
            "bands": {"blue": band_blue, "nir": band_nir},
        },
        "vcd_background_median": vcd_bg,
        "pixels_tempo": int(h * w),
        "pixels_plume_fp_gt_0.01": int(np.sum(plume_mask)),
        "total_excess_no2_kg": mass_kg,
    }

    meta_path = out_dir / "pipeline_summary.json"
    meta_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    rows = [
        {
            "quantity": "VCD background (median over low-f_p pixels)",
            "value": vcd_bg,
            "units": vcd_units,
        },
        {
            "quantity": "Sum excess NO2 mass (f_p × (VCD − VCD_bg))",
            "value": mass_kg,
            "units": "kg",
        },
    ]
    csv_path = out_dir / "pipeline_table.csv"
    with csv_path.open("w", encoding="utf-8") as f:
        f.write("quantity,value,units\n")
        for r in rows:
            f.write(f"\"{r['quantity']}\",{r['value']},{r['units']}\n")

    if write_maps:
        profile = tempo_ds.profile.copy()
        profile.update(dtype=rasterio.float32, count=1, compress="deflate")
        with rasterio.open(out_dir / "f_p.tif", "w", **profile) as dst:
            dst.write(f_p.astype(np.float32), 1)
        with rasterio.open(out_dir / "delta_vcd_plume.tif", "w", **profile) as dst:
            dst.write(np.where(np.isfinite(delta_plume), delta_plume, tempo_ds.nodata or -9999.0).astype(np.float32), 1)

    tempo_ds.close()
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Palisades smoke plume NO2 pipeline (TODO 3).")
    p.add_argument("--planet", type=Path, default=DEFAULT_PLANET)
    p.add_argument("--tempo", type=Path, default=DEFAULT_TEMPO)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument(
        "--vcd-units",
        choices=("molec_cm2", "mol_m2"),
        default="molec_cm2",
        help="TEMPO GeoTIFF vertical column units (NASA browse / GEE: molec_cm2).",
    )
    p.add_argument("--blue-nir-max", type=float, default=0.42, help="Smoke: blue/NIR below this (tune).")
    p.add_argument("--fp-bg-max", type=float, default=0.02, help="Max f_p for background median.")
    p.add_argument("--blue-band", type=int, default=2, help="Planet SR band index for Blue (1-based).")
    p.add_argument("--nir-band", type=int, default=8, help="Planet SR band index for NIR (1-based).")
    p.add_argument("--write-maps", action="store_true", help="Write f_p and delta_vcd_plume GeoTIFFs.")
    args = p.parse_args()

    try:
        summary = run(
            args.planet,
            args.tempo,
            args.out,
            args.vcd_units,
            args.blue_nir_max,
            args.fp_bg_max,
            args.write_maps,
            args.blue_band,
            args.nir_band,
        )
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        print(
            "\nPlace pilot rasters under data/palisades/ (see PROJECT.md). "
            "Large *.tif files are gitignored.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(json.dumps(summary, indent=2))
    print(f"\nWrote {args.out / 'pipeline_summary.json'} and pipeline_table.csv")


if __name__ == "__main__":
    main()
