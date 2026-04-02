"""
Compare Planet smoke mask from blue/NIR ratio (pipeline) vs normalized difference
with the mathematically equivalent ND threshold.

For positive B, N with r = B/N:  ND = (B-N)/(B+N) = (r-1)/(r+1).
So  r < r_max  <=>  ND < (r_max - 1) / (r_max + 1).

Small disagreements can occur where NIR is tiny (ratio uses max(NIR, 1e-8)).

Run from repo root:
  python scripts/compare_ratio_nd_smoke_mask.py          # demo only (no numpy needed)
  python scripts/compare_ratio_nd_smoke_mask.py --demo   # same
  python scripts/compare_ratio_nd_smoke_mask.py --planet data/palisades/planet/your.tif   # needs numpy, rasterio

Uses .format() instead of f-strings so this runs on Python 3.5+; smoke_mask is inlined
so we do not import palisades_pipeline (which requires 3.6+ for f-strings).
"""

from __future__ import print_function

import argparse
from pathlib import Path

# NumPy / rasterio imported inside analyze_raster so `python ... --demo` works
# without those deps (e.g. system Python 3.5 with no venv).

def smoke_mask_from_sr(blue, nir, blue_nir_max):
    """Same logic as palisades_pipeline.smoke_mask_from_sr (kept inline for Py3.5)."""
    import numpy as np

    denom = np.maximum(nir, 1e-8)
    ratio = blue / denom
    return (ratio < blue_nir_max) & np.isfinite(blue) & np.isfinite(nir)


def ratio_max_to_nd_cutoff(r_max):
    """ND threshold such that (B/N < r_max) <=> (ND < nd) for B,N > 0."""
    return (r_max - 1.0) / (r_max + 1.0)


def mask_from_nd(blue, nir, r_max):
    """Same decision as ratio < r_max when NIR >= 1e-8 and B+N != 0."""
    import numpy as np

    nd = (blue - nir) / (blue + nir)
    valid = np.isfinite(blue) & np.isfinite(nir) & (blue + nir != 0.0)
    return (nd < ratio_max_to_nd_cutoff(r_max)) & valid


def run_demo(r_max=0.42):
    nd_cut = ratio_max_to_nd_cutoff(r_max)
    print("Smoke mask rule comparison (positive surface reflectance)")
    print("  Pipeline:  blue / max(nir, 1e-8)  <  {0}".format(r_max))
    print("  Equivalent ND:  (blue - nir) / (blue + nir)  <  {0:.6f}".format(nd_cut))
    print("  (Using ND = 0.42 would NOT match — that is on the wrong scale.)")
    print()
    print("Example pixels (B, N) -> ratio r, ND, smoke by ratio? smoke by ND?")
    examples = [
        (0.10, 0.40),
        (0.15, 0.40),
        (0.42, 1.00),
        (0.30, 0.20),
        (0.05, 0.02),
    ]
    for b, n in examples:
        r = b / max(n, 1e-8)
        nd = (b - n) / (b + n)
        sr = r < r_max
        snd = nd < nd_cut
        print(
            "  B={0:.2f}, N={1:.2f}  ->  r={2:.4f}, ND={3:+.4f}  |  ratio_smoke={4}  nd_smoke={5}  match={6}".format(
                b, n, r, nd, sr, snd, sr == snd
            )
        )


def analyze_raster(planet, r_max, blue_band, nir_band):
    import numpy as np
    import rasterio

    nd_cut = ratio_max_to_nd_cutoff(r_max)
    with rasterio.open(str(planet)) as ds:
        if ds.count < max(blue_band, nir_band):
            raise ValueError(
                "Need bands blue={0}, nir={1}; count={2}".format(blue_band, nir_band, ds.count)
            )
        blue = ds.read(blue_band).astype(np.float64)
        nir = ds.read(nir_band).astype(np.float64)
        pnod = ds.nodata
        if pnod is not None:
            blue = np.where(blue == pnod, np.nan, blue)
            nir = np.where(nir == pnod, np.nan, nir)

    mask_ratio = smoke_mask_from_sr(blue, nir, r_max)
    mask_nd = mask_from_nd(blue, nir, r_max)

    valid_both = np.isfinite(blue) & np.isfinite(nir)
    n_valid = int(np.sum(valid_both))
    same_mask = mask_ratio == mask_nd
    n_match = int(np.sum(same_mask & valid_both))
    n_mismatch = int(np.sum(~same_mask & valid_both))

    print("Raster: {0}".format(planet))
    print("  Valid pixels: {0:,}".format(n_valid))
    print("  Smoke (ratio < {0}): {1:,}".format(r_max, int(np.sum(mask_ratio & valid_both))))
    print("  Smoke (ND < {0:.6f}): {1:,}".format(nd_cut, int(np.sum(mask_nd & valid_both))))
    print("  Same mask on valid pixels: {0:,} match, {1:,} differ".format(n_match, n_mismatch))
    if n_valid > 0:
        pct = 100.0 * n_mismatch / n_valid
        print("  Mismatch rate: {0:.4f}% of valid pixels".format(pct))
    if n_mismatch > 0:
        only_ratio = mask_ratio & ~mask_nd & valid_both
        only_nd = mask_nd & ~mask_ratio & valid_both
        print(
            "  Only ratio smoke: {0:,}  |  Only ND smoke: {1:,}".format(
                int(np.sum(only_ratio)), int(np.sum(only_nd))
            )
        )
        tiny_n = valid_both & (nir < 1e-8) & (nir > 0)
        print("  Pixels with 0 < nir < 1e-8 (ratio denom clamp): {0:,}".format(int(np.sum(tiny_n))))


def main():
    p = argparse.ArgumentParser(description="Compare ratio vs ND smoke masks")
    p.add_argument("--demo", action="store_true", help="Print threshold math + example pixels")
    p.add_argument("--planet", type=Path, default=None, help="Planet SR GeoTIFF (requires numpy, rasterio)")
    p.add_argument("--blue-nir-max", type=float, default=0.42)
    p.add_argument("--blue-band", type=int, default=2)
    p.add_argument("--nir-band", type=int, default=8)
    args = p.parse_args()

    # No --planet: only print demo (works on bare Python). Full raster compare needs deps.
    if args.planet is None:
        run_demo(args.blue_nir_max)
        print()
        print("To compare masks on a GeoTIFF, install numpy and rasterio, then:")
        print('  python scripts/compare_ratio_nd_smoke_mask.py --planet "path/to/planet_sr.tif"')
        return

    if args.demo:
        run_demo(args.blue_nir_max)

    planet = args.planet
    if not planet.is_file():
        raise IOError("Missing Planet raster: {0}".format(planet))
    print()
    try:
        analyze_raster(planet, args.blue_nir_max, args.blue_band, args.nir_band)
    except ImportError as e:
        print("Import failed ({0}). Install project deps, e.g.:".format(e))
        print("  py -3 -m pip install numpy rasterio")
        raise


if __name__ == "__main__":
    main()
