"""
Step 2 checkpoint: export Planet blue/NIR ratio + smoke mask (full + preview),
and sub-pixel plume fraction f_p on the TEMPO grid (same as palisades_pipeline).

Run from repo root:
  python scripts/export_planet_smoke_step2.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.warp import Resampling, reproject

from palisades_pipeline import (
    DEFAULT_PLANET,
    DEFAULT_TEMPO,
    REPO_ROOT,
    reproject_mask_to_tempo,
    smoke_mask_from_sr,
)

DEFAULT_OUT = REPO_ROOT / "results/step_02_plume_mask"


def _preview_shape(height: int, width: int, max_side: int) -> tuple[int, int]:
    m = max(height, width)
    if m <= max_side:
        return height, width
    scale = max_side / float(m)
    return max(2, int(round(height * scale))), max(2, int(round(width * scale)))


def _downsample(
    arr: np.ndarray,
    src_transform: Affine,
    src_crs,
    out_h: int,
    out_w: int,
    resampling: Resampling,
) -> tuple[np.ndarray, Affine]:
    dst = np.empty((out_h, out_w), dtype=np.float32)
    scale_x = (arr.shape[1]) / out_w
    scale_y = (arr.shape[0]) / out_h
    dst_transform = src_transform * Affine.scale(scale_x, scale_y)
    reproject(
        source=arr.astype(np.float32),
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=src_crs,
        resampling=resampling,
    )
    return dst, dst_transform


def main() -> None:
    p = argparse.ArgumentParser(description="Step 2: Planet ratio/mask + f_p export for QGIS")
    p.add_argument("--planet", type=Path, default=DEFAULT_PLANET)
    p.add_argument("--tempo", type=Path, default=DEFAULT_TEMPO)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--blue-nir-max", type=float, default=0.42)
    p.add_argument("--blue-band", type=int, default=2)
    p.add_argument("--nir-band", type=int, default=8)
    p.add_argument("--preview-max-side", type=int, default=2048, help="Max width/height for *_preview.tif")
    args = p.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.planet) as planet_ds:
        if planet_ds.count < max(args.blue_band, args.nir_band):
            raise ValueError(f"Expected >= {max(args.blue_band, args.nir_band)} bands")
        blue = planet_ds.read(args.blue_band).astype(np.float64)
        nir = planet_ds.read(args.nir_band).astype(np.float64)
        pnod = planet_ds.nodata
        if pnod is not None:
            blue = np.where(blue == pnod, np.nan, blue)
            nir = np.where(nir == pnod, np.nan, nir)

        denom = np.maximum(nir, 1e-8)
        ratio = (blue / denom).astype(np.float32)
        ratio[~np.isfinite(blue) | ~np.isfinite(nir)] = np.nan

        mask_bool = smoke_mask_from_sr(blue, nir, args.blue_nir_max)
        mask_f = mask_bool.astype(np.float32)

        profile = planet_ds.profile.copy()
        profile.update(dtype=rasterio.float32, count=1, compress="deflate", nodata=None)

        ratio_path = args.out / "planet_blue_nir_ratio.tif"
        mask_path = args.out / "planet_smoke_mask.tif"
        with rasterio.open(ratio_path, "w", **profile) as dst:
            dst.write(ratio, 1)
            dst.set_band_description(1, "blue / nir")
        with rasterio.open(mask_path, "w", **profile) as dst:
            dst.write(mask_f, 1)
            dst.set_band_description(1, "smoke mask 0/1")

        ph, pw = ratio.shape
        qh, qw = _preview_shape(ph, pw, args.preview_max_side)
        ratio_prev, tr_prev = _downsample(
            np.where(np.isfinite(ratio), ratio, 0.0),
            planet_ds.transform,
            planet_ds.crs,
            qh,
            qw,
            Resampling.bilinear,
        )
        mask_prev, _ = _downsample(
            mask_f,
            planet_ds.transform,
            planet_ds.crs,
            qh,
            qw,
            Resampling.average,
        )

        prev_profile = profile.copy()
        prev_profile.update(width=qw, height=qh, transform=tr_prev)
        with rasterio.open(args.out / "planet_blue_nir_ratio_preview.tif", "w", **prev_profile) as dst:
            dst.write(ratio_prev, 1)
        with rasterio.open(args.out / "planet_smoke_mask_preview.tif", "w", **prev_profile) as dst:
            dst.write(np.clip(mask_prev, 0.0, 1.0), 1)

        with rasterio.open(args.tempo) as tempo_ds:
            f_p = reproject_mask_to_tempo(planet_ds, mask_bool, tempo_ds)
            tp = tempo_ds.profile.copy()
            tp.update(dtype=rasterio.float32, count=1, compress="deflate", nodata=-9999.0)
            fp_path = args.out / "f_p_tempo_grid.tif"
            with rasterio.open(fp_path, "w", **tp) as dst:
                dst.write(f_p.astype(np.float32), 1)
                dst.set_band_description(1, "f_p mean smoke fraction per TEMPO pixel")
                dst.update_tags(
                    DESCRIPTION="Sub-pixel plume fraction: Planet smoke mask averaged onto TEMPO grid (0-1).",
                    SOURCE_PLANET=str(args.planet.resolve()),
                    SOURCE_TEMPO=str(args.tempo.resolve()),
                    BLUE_NIR_MAX=str(args.blue_nir_max),
                )

    print(f"Wrote under {args.out.resolve()}:")
    print(f"  {ratio_path.name}, {mask_path.name} (full resolution)")
    print("  planet_blue_nir_ratio_preview.tif, planet_smoke_mask_preview.tif")
    print(f"  {fp_path.name} - sub-pixel fraction per TEMPO pixel (critical for mass)")


if __name__ == "__main__":
    main()
