"""
Smoke plume NO₂ pipeline: Planet smoke mask, overlap fraction f_p on TEMPO grid,
background subtraction, excess column, total NO₂ mass (see also scripts/column_to_mass.py).

Default inputs point at the Palisades pilot under smoke-plume-data/; override with --planet / --tempo.

Run from repo root:
  .\\.venv\\Scripts\\Activate.ps1
  python scripts/smoke_plume_pipeline.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.windows import from_bounds as window_from_bounds
from rasterio.warp import Resampling, reproject
from rasterio.warp import transform_bounds

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLANET = (
    REPO_ROOT
    / "smoke-plume-data/palisades/planet/20250110_185256_28_24e1_3B_AnalyticMS_SR_8b.tif"
)
DEFAULT_TEMPO = REPO_ROOT / "smoke-plume-data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif"
DEFAULT_OUT_DIR = REPO_ROOT / "results/smoke_plume"

# Default: PlanetScope 8-band analytic SR (1-based): Blue=2, NIR=8 (see --blue-band / --nir-band)

MASK_NODATA_OUT = -9999.0

AVOGADRO = 6.022_140_76e23
M_NO2_KG_PER_MOL = 46e-3

# Used in pipeline_summary.json when --time-match is not supplied per case (Palisades pilot example).
DEFAULT_TIME_MATCH = {
    "tempo_granule_utc": "2025-01-10T18:45:29Z → 2025-01-10T18:52:06Z",
    "planet_acquired_utc": "2025-01-10T18:52:56.288697Z",
    "note": "Planet ~50 s after granule end; prefer next L2 granule or explicit ±Δt (PROJECT.md).",
}

# Back-compat for imports
TIME_MATCH = DEFAULT_TIME_MATCH


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


def ndhi_green_blue(green: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """(Green - Blue) / (Green + Blue). Not the same as haze ND(B,NIR); see ndhi_blue_nir."""
    denom = np.maximum(green + blue, 1e-8)
    return (green - blue) / denom


def ndhi_blue_nir(blue: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Normalized difference (Blue - NIR) / (Blue + NIR). Often used as haze / path-radiance contrast."""
    denom = np.maximum(blue + nir, 1e-8)
    return (blue - nir) / denom


def smoke_mask_ndhi_green_blue(
    green: np.ndarray,
    blue: np.ndarray,
    ndhi_smoke_below: float,
) -> np.ndarray:
    """Smoke where green-blue NDHI < threshold (tune per scene)."""
    ndhi = ndhi_green_blue(green, blue)
    valid = np.isfinite(green) & np.isfinite(blue)
    return (ndhi < ndhi_smoke_below) & valid


def smoke_mask_ndhi_blue_nir(
    blue: np.ndarray,
    nir: np.ndarray,
    smoke_above: float,
) -> np.ndarray:
    """
    Smoke/haze where (B-NIR)/(B+NIR) is above threshold.
    Clear vegetation is often strongly negative; haze/smoke can push the index toward 0 or positive.
    """
    idx = ndhi_blue_nir(blue, nir)
    valid = np.isfinite(blue) & np.isfinite(nir)
    return (idx > smoke_above) & valid


def smoke_mask_to_float_raster(
    valid: np.ndarray,
    smoke: np.ndarray,
    mask_nodata: float = MASK_NODATA_OUT,
) -> np.ndarray:
    """Valid clear=0, valid smoke=1, invalid=nodata (not 0 — so QGIS can separate from clear)."""
    return np.where(valid, np.where(smoke, 1.0, 0.0), mask_nodata).astype(np.float32)


def compute_smoke_mask_layers(
    *,
    method: str,
    blue: np.ndarray,
    nir: np.ndarray | None,
    green: np.ndarray | None,
    blue_nir_max: float,
    ndhi_smoke_below: float,
    ndhi_bnir_smoke_above: float = -0.15,
    mask_nodata: float = MASK_NODATA_OUT,
) -> tuple[np.ndarray, np.ndarray, str]:
    """
    Build float smoke mask (0 / 1 / nodata) and an index raster for tuning in QGIS.
    Returns (mask_01, index_float32, index_label) where index is ratio or NDHI (nan invalid).
    """
    m = method.lower().strip()
    if m in ("blue_nir", "blue-nir", "b_nir"):
        if nir is None:
            raise ValueError("blue_nir method requires nir array")
        valid = np.isfinite(blue) & np.isfinite(nir)
        smoke = smoke_mask_from_sr(blue, nir, blue_nir_max)
        mask_01 = smoke_mask_to_float_raster(valid, smoke, mask_nodata)
        denom = np.maximum(nir, 1e-8)
        ratio = (blue / denom).astype(np.float32)
        ratio[~valid] = np.nan
        return mask_01, ratio, "blue_nir_ratio"
    if m in ("ndhi", "ndhi_green_blue"):
        if green is None:
            raise ValueError("ndhi (green-blue) method requires green array")
        valid = np.isfinite(green) & np.isfinite(blue)
        smoke = smoke_mask_ndhi_green_blue(green, blue, ndhi_smoke_below)
        mask_01 = smoke_mask_to_float_raster(valid, smoke, mask_nodata)
        ndhi = ndhi_green_blue(green, blue).astype(np.float32)
        ndhi[~valid] = np.nan
        return mask_01, ndhi, "ndhi_green_blue"
    if m in ("ndhi_bnir", "ndhi_b_nir", "haze_bnir"):
        if nir is None:
            raise ValueError("ndhi_bnir method requires nir array")
        valid = np.isfinite(blue) & np.isfinite(nir)
        smoke = smoke_mask_ndhi_blue_nir(blue, nir, ndhi_bnir_smoke_above)
        mask_01 = smoke_mask_to_float_raster(valid, smoke, mask_nodata)
        idx = ndhi_blue_nir(blue, nir).astype(np.float32)
        idx[~valid] = np.nan
        return mask_01, idx, "ndhi_bnir"
    raise ValueError(
        f"Unknown mask method: {method!r} (use blue_nir, ndhi / ndhi_green_blue, or ndhi_bnir)"
    )


def load_tempo_vcd(path: Path, band: int = 1) -> tuple[np.ndarray, rasterio.DatasetReader]:
    ds = rasterio.open(path)
    if band < 1 or band > ds.count:
        ds.close()
        raise ValueError(f"TEMPO raster has {ds.count} band(s); requested band {band}")
    arr = ds.read(band).astype(np.float64)
    nodata = ds.nodata
    if nodata is not None:
        arr = np.where(arr == nodata, np.nan, arr)
    return arr, ds


def _clip_window_to_dataset(ds: rasterio.DatasetReader, w: Window) -> Window:
    """Clamp a window to dataset bounds (integer pixels)."""
    w2 = w.round_offsets().round_lengths()
    col_off = max(0, int(w2.col_off))
    row_off = max(0, int(w2.row_off))
    col_end = min(ds.width, col_off + int(w2.width))
    row_end = min(ds.height, row_off + int(w2.height))
    width = max(0, col_end - col_off)
    height = max(0, row_end - row_off)
    return Window(col_off, row_off, width, height)


def tempo_window_for_planet_bounds(
    planet_ds: rasterio.DatasetReader,
    tempo_ds: rasterio.DatasetReader,
    *,
    pad_pixels: int = 1,
) -> Window:
    """
    Window TEMPO to Planet scene bounds (in TEMPO CRS).

    Policy: compute f_p, background, ΔVCD, and mass only where Planet was observed, to avoid
    treating "no Planet coverage" as "clear" (f_p=0).
    """
    pb = planet_ds.bounds
    west, south, east, north = transform_bounds(
        planet_ds.crs,
        tempo_ds.crs,
        pb.left,
        pb.bottom,
        pb.right,
        pb.top,
        densify_pts=21,
    )
    w = window_from_bounds(west, south, east, north, transform=tempo_ds.transform)
    w = _clip_window_to_dataset(tempo_ds, w)
    if w.width <= 0 or w.height <= 0:
        raise ValueError("Planet bounds do not overlap TEMPO raster extent.")
    if pad_pixels > 0:
        w = Window(
            max(0, int(w.col_off) - pad_pixels),
            max(0, int(w.row_off) - pad_pixels),
            int(w.width) + 2 * pad_pixels,
            int(w.height) + 2 * pad_pixels,
        )
        w = _clip_window_to_dataset(tempo_ds, w)
    return w


def reproject_mask_to_tempo(
    planet_ds: rasterio.DatasetReader,
    mask_01_or_nodata: np.ndarray,
    tempo_ds: rasterio.DatasetReader,
    *,
    src_nodata: float = MASK_NODATA_OUT,
) -> np.ndarray:
    """Average sub-pixel smoke fraction; src pixels equal to src_nodata do not contribute."""
    dst = np.zeros((tempo_ds.height, tempo_ds.width), dtype=np.float32)
    reproject(
        source=np.asarray(mask_01_or_nodata, dtype=np.float32),
        destination=dst,
        src_transform=planet_ds.transform,
        src_crs=planet_ds.crs,
        dst_transform=tempo_ds.transform,
        dst_crs=tempo_ds.crs,
        resampling=Resampling.average,
        src_nodata=src_nodata,
    )
    return np.clip(dst, 0.0, 1.0)


def reproject_mask_to_tempo_window(
    planet_ds: rasterio.DatasetReader,
    mask_01_or_nodata: np.ndarray,
    tempo_ds: rasterio.DatasetReader,
    window: Window,
    *,
    src_nodata: float = MASK_NODATA_OUT,
) -> np.ndarray:
    """Average sub-pixel smoke fraction onto a TEMPO window (Planet-bounds subset)."""
    if window.width <= 0 or window.height <= 0:
        raise ValueError("Invalid TEMPO window for f_p.")
    dst = np.zeros((int(window.height), int(window.width)), dtype=np.float32)
    dst_transform = rasterio.windows.transform(window, tempo_ds.transform)
    reproject(
        source=np.asarray(mask_01_or_nodata, dtype=np.float32),
        destination=dst,
        src_transform=planet_ds.transform,
        src_crs=planet_ds.crs,
        dst_transform=dst_transform,
        dst_crs=tempo_ds.crs,
        resampling=Resampling.average,
        src_nodata=src_nodata,
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
    tempo_vcd_band: int,
    *,
    mask_method: str = "blue_nir",
    band_green: int = 3,
    ndhi_smoke_below: float = 0.0,
    ndhi_bnir_smoke_above: float = -0.15,
    mask_nodata: float = MASK_NODATA_OUT,
    time_match: dict | None = None,
) -> dict:
    if not planet_path.is_file():
        raise FileNotFoundError(f"Missing Planet raster: {planet_path}")
    if not tempo_path.is_file():
        raise FileNotFoundError(f"Missing TEMPO raster: {tempo_path}")

    out_dir.mkdir(parents=True, exist_ok=True)

    with rasterio.open(tempo_path) as tempo_ds, rasterio.open(planet_path) as planet_ds:
        tw = tempo_window_for_planet_bounds(planet_ds, tempo_ds, pad_pixels=1)
        vcd = tempo_ds.read(tempo_vcd_band, window=tw).astype(np.float64)
        nodata = tempo_ds.nodata
        if nodata is not None:
            vcd = np.where(vcd == nodata, np.nan, vcd)
        h, w = vcd.shape

        need = max(band_blue, band_nir)
        if mask_method.lower().strip() in ("ndhi", "ndhi_green_blue"):
            need = max(need, band_green)
        if planet_ds.count < need:
            raise ValueError(f"Expected >= {need} bands, got {planet_ds.count}")
        blue = planet_ds.read(band_blue).astype(np.float64)
        pnod = planet_ds.nodata
        if pnod is not None:
            blue = np.where(blue == pnod, np.nan, blue)
        nir_arr: np.ndarray | None = None
        green_arr: np.ndarray | None = None
        if mask_method.lower().strip() in ("ndhi", "ndhi_green_blue"):
            green_arr = planet_ds.read(band_green).astype(np.float64)
            if pnod is not None:
                green_arr = np.where(green_arr == pnod, np.nan, green_arr)
        else:
            nir_arr = planet_ds.read(band_nir).astype(np.float64)
            if pnod is not None:
                nir_arr = np.where(nir_arr == pnod, np.nan, nir_arr)

        mask_01, _idx, _label = compute_smoke_mask_layers(
            method=mask_method,
            blue=blue,
            nir=nir_arr,
            green=green_arr,
            blue_nir_max=blue_nir_max,
            ndhi_smoke_below=ndhi_smoke_below,
            ndhi_bnir_smoke_above=ndhi_bnir_smoke_above,
            mask_nodata=mask_nodata,
        )
        f_p = reproject_mask_to_tempo_window(
            planet_ds, mask_01, tempo_ds, tw, src_nodata=mask_nodata
        )
        tempo_profile = tempo_ds.profile.copy()
        tempo_transform = rasterio.windows.transform(tw, tempo_ds.transform)

    # Finite tropospheric VCD only; negatives are allowed (TEMPO user guide). QA/cloud live in the GeoTIFF from tempo_l2_to_4326.py.
    valid = np.isfinite(vcd)
    bg_sel = valid & (f_p <= fp_bg_max)
    if np.sum(bg_sel) < 50:
        bg_sel = valid & (f_p <= min(0.05, fp_bg_max + 0.03))
    if np.sum(bg_sel) < 10:
        vcd_bg = float(np.nanpercentile(vcd[valid], 15))
    else:
        vcd_bg = float(np.nanmedian(vcd[bg_sel]))

    delta_signed = np.where(valid, vcd - vcd_bg, np.nan)
    # Option A: report enhancement above background only (never negative).
    delta_enh = np.where(np.isfinite(delta_signed), np.maximum(delta_signed, 0.0), np.nan)
    delta_plume = f_p.astype(np.float64) * delta_enh

    area = _pixel_areas_m2(tempo_transform, h, w)
    if vcd_units == "molec_cm2":
        mass_kg = excess_mass_molec_cm2(delta_plume, area)
    elif vcd_units == "mol_m2":
        mass_kg = excess_mass_mol_m2(delta_plume, area)
    else:
        raise ValueError(vcd_units)

    plume_mask = f_p > 0.01
    mass_signed_kg = None
    if vcd_units == "molec_cm2":
        mass_signed_kg = excess_mass_molec_cm2(f_p.astype(np.float64) * delta_signed, area)
    elif vcd_units == "mol_m2":
        mass_signed_kg = excess_mass_mol_m2(f_p.astype(np.float64) * delta_signed, area)

    summary = {
        "time_match": time_match if time_match is not None else DEFAULT_TIME_MATCH,
        "inputs": {"planet": str(planet_path), "tempo": str(tempo_path)},
        "domain_policy": "TEMPO is subset to Planet scene bounds (windowed) before f_p, background, ΔVCD, and mass.",
        "parameters": {
            "vcd_units": vcd_units,
            "mask_method": mask_method,
            "mask_nodata": mask_nodata,
            "blue_nir_max": blue_nir_max,
            "ndhi_smoke_below": ndhi_smoke_below,
            "ndhi_bnir_smoke_above": ndhi_bnir_smoke_above,
            "fp_background_max": fp_bg_max,
            "bands": {
                "blue": band_blue,
                "nir": band_nir,
                "green": band_green,
            },
            "tempo_vcd_band": tempo_vcd_band,
        },
        "vcd_background_median": vcd_bg,
        "pixels_tempo": int(h * w),
        "pixels_plume_fp_gt_0.01": int(np.sum(plume_mask)),
        "total_enhancement_no2_kg": mass_kg,
        "total_excess_no2_kg_signed": float(mass_signed_kg) if mass_signed_kg is not None else None,
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
            "quantity": "Sum plume enhancement NO2 mass (f_p × max(VCD − VCD_bg, 0))",
            "value": mass_kg,
            "units": "kg",
        },
        {
            "quantity": "Sum signed plume anomaly (f_p × (VCD − VCD_bg))",
            "value": float(mass_signed_kg) if mass_signed_kg is not None else float("nan"),
            "units": "kg",
        },
    ]
    csv_path = out_dir / "pipeline_table.csv"
    with csv_path.open("w", encoding="utf-8") as f:
        f.write("quantity,value,units\n")
        for r in rows:
            f.write(f"\"{r['quantity']}\",{r['value']},{r['units']}\n")

    if write_maps:
        profile = tempo_profile.copy()
        profile.update(
            dtype=rasterio.float32,
            count=1,
            compress="deflate",
            height=h,
            width=w,
            transform=tempo_transform,
        )
        nd = tempo_profile.get("nodata")
        if nd is None:
            nd = -9999.0
        with rasterio.open(out_dir / "f_p.tif", "w", **profile) as dst:
            dst.write(f_p.astype(np.float32), 1)
            dst.set_band_description(1, "f_p sub-pixel smoke fraction on TEMPO grid")
        # Step 4: full-field excess column ΔVCD = VCD - VCD_bg (not yet scaled by f_p)
        with rasterio.open(out_dir / "delta_vcd.tif", "w", **profile) as dst:
            dst.write(np.where(np.isfinite(delta_signed), delta_signed, nd).astype(np.float32), 1)
            dst.set_band_description(1, "delta VCD = VCD - VCD_bg (signed, all valid TEMPO pixels)")
        # Enhancement-only excess: max(ΔVCD, 0)
        with rasterio.open(out_dir / "delta_vcd_enh.tif", "w", **profile) as dst:
            dst.write(np.where(np.isfinite(delta_enh), delta_enh, nd).astype(np.float32), 1)
            dst.set_band_description(1, "delta VCD enhancement = max(VCD - VCD_bg, 0)")
        # Plume-attributed excess: f_p * ΔVCD
        with rasterio.open(out_dir / "delta_vcd_plume.tif", "w", **profile) as dst:
            dst.write(np.where(np.isfinite(delta_plume), delta_plume, nd).astype(np.float32), 1)
            dst.set_band_description(1, "f_p * max(delta VCD, 0) (plume-weighted enhancement)")
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Smoke plume NO₂: Planet mask, f_p, ΔVCD, mass.")
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
    p.add_argument(
        "--mask-method",
        choices=("blue_nir", "ndhi", "ndhi_bnir"),
        default="blue_nir",
        help=(
            "blue_nir: B/NIR ratio; ndhi: (G-B)/(G+B), smoke if below --ndhi-smoke-below; "
            "ndhi_bnir: (B-NIR)/(B+NIR) haze index, smoke if above --ndhi-bnir-smoke-above."
        ),
    )
    p.add_argument(
        "--ndhi-smoke-below",
        type=float,
        default=0.0,
        help="ndhi (green-blue): smoke where index is below this (try -0.1 to 0.05).",
    )
    p.add_argument(
        "--ndhi-bnir-smoke-above",
        type=float,
        default=-0.15,
        help="ndhi_bnir: smoke/haze where (B-NIR)/(B+NIR) exceeds this (tune; try -0.4 to 0.0).",
    )
    p.add_argument(
        "--mask-nodata",
        type=float,
        default=MASK_NODATA_OUT,
        help="Value for invalid Planet pixels in mask warp (default -9999; clear=0, smoke=1).",
    )
    p.add_argument("--fp-bg-max", type=float, default=0.02, help="Max f_p for background median.")
    p.add_argument("--blue-band", type=int, default=2, help="Planet SR band index for Blue (1-based).")
    p.add_argument("--nir-band", type=int, default=8, help="Planet SR band index for NIR (1-based).")
    p.add_argument(
        "--green-band",
        type=int,
        default=3,
        help="Planet SR Green band (1-based); used when --mask-method ndhi.",
    )
    p.add_argument(
        "--tempo-vcd-band",
        type=int,
        default=1,
        help="Band index in TEMPO GeoTIFF for tropospheric VCD (band 1 after tempo_l2_to_4326 --stack).",
    )
    p.add_argument(
        "--write-maps",
        action="store_true",
        help="Write Step 4 GeoTIFFs: f_p.tif, delta_vcd.tif (VCD-VCD_bg), delta_vcd_plume.tif (f_p*delta_VCD).",
    )
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
            args.tempo_vcd_band,
            mask_method=args.mask_method,
            band_green=args.green_band,
            ndhi_smoke_below=args.ndhi_smoke_below,
            ndhi_bnir_smoke_above=args.ndhi_bnir_smoke_above,
            mask_nodata=args.mask_nodata,
        )
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        print(
            "\nPlace rasters under smoke-plume-data/<region>/ (see PROJECT.md). "
            "Large *.tif files may be gitignored.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(json.dumps(summary, indent=2))
    print(f"\nWrote {args.out / 'pipeline_summary.json'} and pipeline_table.csv")
    if args.write_maps:
        print(f"Also wrote maps: f_p.tif, delta_vcd.tif, delta_vcd_plume.tif under {args.out.resolve()}")


if __name__ == "__main__":
    main()
