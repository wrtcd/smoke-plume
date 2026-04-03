"""
Step 2 checkpoint: export Planet blue/NIR ratio + smoke mask (full + preview),
and sub-pixel plume fraction f_p on the TEMPO grid (same as smoke_plume_pipeline).

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

from smoke_plume_pipeline import (
    DEFAULT_PLANET,
    DEFAULT_TEMPO,
    MASK_NODATA_OUT,
    REPO_ROOT,
    compute_smoke_mask_layers,
    reproject_mask_to_tempo,
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
    p.add_argument("--mask-method", choices=("blue_nir", "ndhi", "ndhi_bnir"), default="blue_nir")
    p.add_argument("--ndhi-smoke-below", type=float, default=0.0)
    p.add_argument("--ndhi-bnir-smoke-above", type=float, default=-0.15)
    p.add_argument("--mask-nodata", type=float, default=MASK_NODATA_OUT)
    p.add_argument("--blue-band", type=int, default=2)
    p.add_argument("--nir-band", type=int, default=8)
    p.add_argument("--green-band", type=int, default=3)
    p.add_argument("--preview-max-side", type=int, default=2048, help="Max width/height for *_preview.tif")
    args = p.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    fp_path = args.out / "f_p_tempo_grid.tif"
    with rasterio.open(args.planet) as planet_ds:
        need = max(args.blue_band, args.nir_band)
        if args.mask_method == "ndhi":
            need = max(need, args.green_band)
        if planet_ds.count < need:
            raise ValueError(f"Expected >= {need} bands")
        blue = planet_ds.read(args.blue_band).astype(np.float64)
        pnod = planet_ds.nodata
        if pnod is not None:
            blue = np.where(blue == pnod, np.nan, blue)
        nir = green = None
        if args.mask_method == "ndhi":
            green = planet_ds.read(args.green_band).astype(np.float64)
            if pnod is not None:
                green = np.where(green == pnod, np.nan, green)
        else:
            nir = planet_ds.read(args.nir_band).astype(np.float64)
            if pnod is not None:
                nir = np.where(nir == pnod, np.nan, nir)

        mask_f, index_arr, index_label = compute_smoke_mask_layers(
            method=args.mask_method,
            blue=blue,
            nir=nir,
            green=green,
            blue_nir_max=args.blue_nir_max,
            ndhi_smoke_below=args.ndhi_smoke_below,
            ndhi_bnir_smoke_above=args.ndhi_bnir_smoke_above,
            mask_nodata=args.mask_nodata,
        )

        profile = planet_ds.profile.copy()
        profile.update(dtype=rasterio.float32, count=1, compress="deflate", nodata=None)
        mask_profile = profile.copy()
        mask_profile.update(nodata=args.mask_nodata)

        if index_label == "ndhi_green_blue":
            ratio_path = args.out / "planet_ndhi_green_blue.tif"
        elif index_label == "ndhi_bnir":
            ratio_path = args.out / "planet_ndhi_bnir.tif"
        else:
            ratio_path = args.out / "planet_blue_nir_ratio.tif"
        mask_path = args.out / "planet_smoke_mask.tif"
        with rasterio.open(ratio_path, "w", **profile) as dst:
            dst.write(index_arr, 1)
            dst.set_band_description(1, index_label)
        with rasterio.open(mask_path, "w", **mask_profile) as dst:
            dst.write(mask_f, 1)
            dst.set_band_description(1, "smoke mask: 0 clear 1 smoke nodata invalid")

        ph, pw = index_arr.shape
        qh, qw = _preview_shape(ph, pw, args.preview_max_side)
        ratio_prev, tr_prev = _downsample(
            np.where(np.isfinite(index_arr), index_arr, 0.0),
            planet_ds.transform,
            planet_ds.crs,
            qh,
            qw,
            Resampling.bilinear,
        )
        mask_prev, _ = _downsample(
            np.where(mask_f == args.mask_nodata, 0.0, mask_f),
            planet_ds.transform,
            planet_ds.crs,
            qh,
            qw,
            Resampling.average,
        )

        prev_profile = profile.copy()
        prev_profile.update(width=qw, height=qh, transform=tr_prev)
        if index_label == "ndhi_green_blue":
            prev_ratio_name = "planet_ndhi_green_blue_preview.tif"
        elif index_label == "ndhi_bnir":
            prev_ratio_name = "planet_ndhi_bnir_preview.tif"
        else:
            prev_ratio_name = "planet_blue_nir_ratio_preview.tif"
        with rasterio.open(args.out / prev_ratio_name, "w", **prev_profile) as dst:
            dst.write(ratio_prev, 1)
        with rasterio.open(args.out / "planet_smoke_mask_preview.tif", "w", **prev_profile) as dst:
            dst.write(np.clip(mask_prev, 0.0, 1.0), 1)

        with rasterio.open(args.tempo) as tempo_ds:
            f_p = reproject_mask_to_tempo(
                planet_ds, mask_f, tempo_ds, src_nodata=args.mask_nodata
            )
            tp = tempo_ds.profile.copy()
            tp.update(dtype=rasterio.float32, count=1, compress="deflate", nodata=-9999.0)
            with rasterio.open(fp_path, "w", **tp) as dst:
                dst.write(f_p.astype(np.float32), 1)
                dst.set_band_description(1, "f_p mean smoke fraction per TEMPO pixel")
                dst.update_tags(
                    DESCRIPTION="Sub-pixel plume fraction: Planet smoke mask averaged onto TEMPO grid (0-1).",
                    SOURCE_PLANET=str(args.planet.resolve()),
                    SOURCE_TEMPO=str(args.tempo.resolve()),
                    BLUE_NIR_MAX=str(args.blue_nir_max),
                    MASK_METHOD=args.mask_method,
                )

    print(f"Wrote under {args.out.resolve()}:")
    print(f"  {ratio_path.name}, {mask_path.name} (full resolution)")
    print(f"  {prev_ratio_name}, planet_smoke_mask_preview.tif")
    print(f"  {fp_path.name} - sub-pixel fraction per TEMPO pixel (critical for mass)")


if __name__ == "__main__":
    main()
