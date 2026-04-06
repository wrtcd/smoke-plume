"""
Create Planet smoke-mask GeoTIFFs you can open in QGIS (same CRS and grid as the Planet scene).

Writes (default output folder: results/qgis_planet_smoke/):
  - smoke_mask.tif          — 0 = clear, 1 = smoke; invalid = nodata (default -9999, not 0)
  - blue_nir_ratio.tif, ndhi_green_blue.tif, or ndhi_bnir.tif — index for tuning (--mask-method)
  - *_preview.tif           — downsampled for faster panning (unless --no-preview)

Optional: --with-fp and a TEMPO raster → f_p_tempo_grid.tif (smoke fraction on TEMPO pixels).

Run from repo root with venv active:
  python scripts/planet_smoke_mask_qgis.py
  python scripts/planet_smoke_mask_qgis.py --planet path/to/AnalyticMS_SR.tif -o my_folder
  python scripts/planet_smoke_mask_qgis.py --mask-only
"""

from __future__ import annotations

import argparse
import sys
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
    reproject_mask_to_tempo_window,
    tempo_window_for_planet_bounds,
)

DEFAULT_OUT = REPO_ROOT / "results/qgis_planet_smoke"


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
    scale_x = arr.shape[1] / out_w
    scale_y = arr.shape[0] / out_h
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
    p = argparse.ArgumentParser(
        description="Export Planet smoke mask GeoTIFF(s) for QGIS (native Planet CRS)."
    )
    p.add_argument("--planet", type=Path, default=DEFAULT_PLANET, help="Planet SR GeoTIFF")
    p.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT, help="Output directory")
    p.add_argument("--blue-nir-max", type=float, default=0.42, help="Smoke if blue/NIR < this")
    p.add_argument(
        "--mask-method",
        choices=("blue_nir", "ndhi", "ndhi_bnir"),
        default="blue_nir",
        help=(
            "blue_nir: B/NIR; ndhi: (G-B)/(G+B), smoke if index < --ndhi-smoke-below; "
            "ndhi_bnir: (B-NIR)/(B+NIR), smoke if index > --ndhi-bnir-smoke-above"
        ),
    )
    p.add_argument(
        "--ndhi-smoke-below",
        type=float,
        default=0.0,
        help="ndhi (green-blue): smoke where index is below this.",
    )
    p.add_argument(
        "--ndhi-bnir-smoke-above",
        type=float,
        default=-0.15,
        help="ndhi_bnir: smoke/haze where (B-NIR)/(B+NIR) is above this.",
    )
    p.add_argument(
        "--mask-nodata",
        type=float,
        default=MASK_NODATA_OUT,
        help="GeoTIFF nodata for invalid pixels (clear=0, smoke=1).",
    )
    p.add_argument("--blue-band", type=int, default=2, help="Blue band index (1-based)")
    p.add_argument("--nir-band", type=int, default=8, help="NIR band index (1-based)")
    p.add_argument("--green-band", type=int, default=3, help="Green band (1-based); NDHI mode only")
    p.add_argument("--no-preview", action="store_true", help="Skip *_preview.tif files")
    p.add_argument("--preview-max-side", type=int, default=2048)
    p.add_argument(
        "--with-fp",
        action="store_true",
        help="Also write f_p on TEMPO grid (needs --tempo)",
    )
    p.add_argument("--tempo", type=Path, default=DEFAULT_TEMPO, help="TEMPO GeoTIFF for f_p")
    p.add_argument(
        "--mask-only",
        action="store_true",
        help="Only smoke_mask.tif and index layer; no preview, no f_p",
    )
    args = p.parse_args()

    if not args.planet.is_file():
        print(f"Planet file not found: {args.planet}", file=sys.stderr)
        sys.exit(1)

    args.out.mkdir(parents=True, exist_ok=True)

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

        mask_path = args.out / "smoke_mask.tif"
        if index_label == "ndhi_green_blue":
            ratio_path = args.out / "ndhi_green_blue.tif"
            idx_desc = "(G-B)/(G+B); smoke where index < --ndhi-smoke-below"
            idx_tags = {"NDHI_SMOKE_BELOW": str(args.ndhi_smoke_below), "METHOD": "ndhi_green_blue"}
        elif index_label == "ndhi_bnir":
            ratio_path = args.out / "ndhi_bnir.tif"
            idx_desc = "(B-NIR)/(B+NIR); smoke/haze where index > --ndhi-bnir-smoke-above"
            idx_tags = {"NDHI_BNIR_SMOKE_ABOVE": str(args.ndhi_bnir_smoke_above), "METHOD": "ndhi_bnir"}
        else:
            ratio_path = args.out / "blue_nir_ratio.tif"
            idx_desc = "blue / nir (tune smoke threshold)"
            idx_tags = {"SMOKE_RULE": f"mask = (ratio < {args.blue_nir_max})", "METHOD": "blue_nir"}

        with rasterio.open(ratio_path, "w", **profile) as dst:
            dst.write(index_arr, 1)
            dst.set_band_description(1, idx_desc)
            dst.update_tags(**idx_tags)
        with rasterio.open(mask_path, "w", **mask_profile) as dst:
            dst.write(mask_f, 1)
            dst.set_band_description(1, "smoke mask: 0=clear 1=smoke nodata=invalid")
            dst.update_tags(
                MASK_METHOD=args.mask_method,
                MASK_NODATA=str(args.mask_nodata),
                BLUE_NIR_MAX=str(args.blue_nir_max),
            )

        written = [mask_path.name, ratio_path.name]

        if not args.mask_only and not args.no_preview:
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
            mask_for_prev = np.where(mask_f == args.mask_nodata, 0.0, mask_f)
            mask_prev, _ = _downsample(
                mask_for_prev,
                planet_ds.transform,
                planet_ds.crs,
                qh,
                qw,
                Resampling.average,
            )
            prev_profile = profile.copy()
            prev_profile.update(width=qw, height=qh, transform=tr_prev)
            if index_label == "ndhi_green_blue":
                prev_ratio_name = "ndhi_green_blue_preview.tif"
            elif index_label == "ndhi_bnir":
                prev_ratio_name = "ndhi_bnir_preview.tif"
            else:
                prev_ratio_name = "blue_nir_ratio_preview.tif"
            with rasterio.open(args.out / prev_ratio_name, "w", **prev_profile) as dst:
                dst.write(ratio_prev, 1)
            with rasterio.open(args.out / "smoke_mask_preview.tif", "w", **prev_profile) as dst:
                dst.write(np.clip(mask_prev, 0.0, 1.0), 1)
            written.extend([prev_ratio_name, "smoke_mask_preview.tif"])

        fp_path = None
        if args.with_fp and not args.mask_only:
            if not args.tempo.is_file():
                print("Warning: --with-fp but TEMPO file missing; skipping f_p.", file=sys.stderr)
            else:
                with rasterio.open(args.tempo) as tempo_ds:
                    tw = tempo_window_for_planet_bounds(planet_ds, tempo_ds, pad_pixels=1)
                    f_p = reproject_mask_to_tempo_window(
                        planet_ds, mask_f, tempo_ds, tw, src_nodata=args.mask_nodata
                    )
                    tp = tempo_ds.profile.copy()
                    tp.update(
                        dtype=rasterio.float32,
                        count=1,
                        compress="deflate",
                        nodata=-9999.0,
                        height=int(tw.height),
                        width=int(tw.width),
                        transform=rasterio.windows.transform(tw, tempo_ds.transform),
                    )
                    fp_path = args.out / "f_p_tempo_grid.tif"
                    with rasterio.open(fp_path, "w", **tp) as dst:
                        dst.write(f_p.astype(np.float32), 1)
                        dst.set_band_description(1, "f_p smoke fraction per TEMPO pixel")
                        dst.update_tags(SOURCE_PLANET=str(args.planet.resolve()))
                    written.append(fp_path.name)

    print(f"QGIS layers written under {args.out.resolve()}:")
    for w in written:
        print(f"  {w}")
    print("\nIn QGIS: Project > Add Raster Layer, pick smoke_mask.tif (same CRS as Planet).")
    print("Set layer nodata to match the GeoTIFF (default -9999) so border is not confused with clear=0.")


if __name__ == "__main__":
    main()
