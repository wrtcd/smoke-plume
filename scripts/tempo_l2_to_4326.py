"""
Warp TEMPO NO2 L2 NetCDF (swath) to a regular lon/lat GeoTIFF in EPSG:4326.

Uses scipy LinearNDInterpolator (same idea as gdalwarp -geoloc: scatter
lat/lon + values -> regular grid). **Do not** `pip install gdal` into the
project `.venv`; use OSGeo4W/QGIS `gdalwarp` on PATH if you prefer CLI, or this script.

Optional GDAL (OSGeo4W / QGIS - not in venv), for reference:

  gdalinfo "HDF5:path/to/file.nc"   # or NETCDF:... depending on driver

  # If your build exposes geolocation arrays to gdalwarp -geoloc:
  gdalwarp -geoloc -t_srs EPSG:4326 -of GTiff \\
    'NETCDF:in.nc:vertical_column_troposphere' out.tif

Python is more portable on Windows; tune --res. Optional --bbox clips to an AOI.

Example:

  python scripts/tempo_l2_to_4326.py \\
    --nc data/palisades/tempo/TEMPO_NO2_L2_V03_20250110T184529Z_S008G09.nc \\
    -o data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif

Default: full extent of valid swath pixels (no AOI clip). Use --bbox to clip.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import netCDF4 as nc
except ModuleNotFoundError:  # pragma: no cover
    _root = Path(__file__).resolve().parents[1]
    print(
        "Missing netCDF4 (and likely other deps). Use the project venv, not system Python:\n"
        f"  cd {_root}\n"
        "  .\\.venv\\Scripts\\Activate.ps1\n"
        "  python scripts/tempo_l2_to_4326.py --nc data/palisades/tempo/<your>.nc\n",
        file=sys.stderr,
    )
    sys.exit(1)

import numpy as np
import rasterio
from rasterio.crs import CRS
from scipy.interpolate import LinearNDInterpolator

FILL = -1e30


def valid_pixels_mask(lat: np.ndarray, lon: np.ndarray, vcd: np.ndarray) -> np.ndarray:
    return (
        np.isfinite(lat)
        & np.isfinite(lon)
        & np.isfinite(vcd)
        & (vcd > FILL / 2)
        & (vcd < 1e30)
        & (vcd >= 0)
    )


def swath_extent_wsen(lat: np.ndarray, lon: np.ndarray, vcd: np.ndarray) -> tuple[float, float, float, float]:
    vm = valid_pixels_mask(lat, lon, vcd)
    if np.sum(vm) < 10:
        raise ValueError("Too few valid pixels in swath; check QA / file.")
    return (
        float(np.min(lon[vm])),
        float(np.min(lat[vm])),
        float(np.max(lon[vm])),
        float(np.max(lat[vm])),
    )


def read_swath(nc_path: Path, use_qa: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    with nc.Dataset(nc_path) as ds:
        lat = np.asarray(ds.groups["geolocation"].variables["latitude"][:], dtype=np.float64)
        lon = np.asarray(ds.groups["geolocation"].variables["longitude"][:], dtype=np.float64)
        vcd = np.asarray(ds.groups["product"].variables["vertical_column_troposphere"][:], dtype=np.float64)
        v = ds.groups["product"].variables["vertical_column_troposphere"]
        units = str(getattr(v, "units", "molecules/cm^2") or "molecules/cm^2")
        qa = None
        if use_qa and "main_data_quality_flag" in ds.groups["product"].variables:
            qa = np.asarray(ds.groups["product"].variables["main_data_quality_flag"][:], dtype=np.int32)
    if use_qa and qa is not None:
        vcd = np.where(qa == 0, vcd, np.nan)
    return lat, lon, vcd, units


def warp_to_4326(
    lat: np.ndarray,
    lon: np.ndarray,
    vcd: np.ndarray,
    west: float,
    south: float,
    east: float,
    north: float,
    res_deg: float,
) -> tuple[np.ndarray, rasterio.Affine]:
    valid = valid_pixels_mask(lat, lon, vcd) & (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)
    pts = np.column_stack([lon[valid], lat[valid]])
    vals = vcd[valid]
    if pts.shape[0] < 10:
        raise ValueError("Too few valid pixels in extent; widen area or check the file.")

    width = max(2, int(np.ceil((east - west) / res_deg)))
    height = max(2, int(np.ceil((north - south) / res_deg)))
    # Adjust res to fit exact bounds
    res_x = (east - west) / width
    res_y = (north - south) / height

    lon_1d = west + (np.arange(width) + 0.5) * res_x
    lat_1d = north - (np.arange(height) + 0.5) * res_y
    grid_x, grid_y = np.meshgrid(lon_1d, lat_1d)

    interp = LinearNDInterpolator(pts, vals, fill_value=np.nan)
    out = interp(grid_x, grid_y).astype(np.float32)

    transform = rasterio.transform.from_bounds(west, south, east, north, width, height)
    return out, transform


def main() -> None:
    p = argparse.ArgumentParser(description="TEMPO L2 NO2 swath -> EPSG:4326 GeoTIFF")
    p.add_argument("--nc", type=Path, required=True, help="TEMPO L2 NetCDF path")
    p.add_argument("-o", "--output", type=Path, help="Output GeoTIFF (default next to .nc)")
    p.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        default=None,
        help="Optional WGS84 clip. Omit to use full extent of valid swath pixels.",
    )
    p.add_argument(
        "--res",
        type=float,
        default=None,
        help="Output resolution in degrees. Default: ~3600 px on the long side of the extent (set explicitly for finer/coarser).",
    )
    p.add_argument(
        "--no-qa",
        action="store_true",
        help="Do not zero-fill pixels with main_data_quality_flag != 0 before gridding",
    )
    args = p.parse_args()

    out = args.output
    if out is None:
        out = args.nc.parent / "TEMPO_NO2_trop_warped_4326.tif"

    lat, lon, vcd, units = read_swath(args.nc, use_qa=not args.no_qa)
    if args.bbox is None:
        west, south, east, north = swath_extent_wsen(lat, lon, vcd)
    else:
        west, south, east, north = args.bbox

    if args.res is None:
        span = max(east - west, north - south)
        res_used = max(span / 3600.0, 0.005)
    else:
        res_used = args.res

    grid, transform = warp_to_4326(lat, lon, vcd, west, south, east, north, res_used)

    profile = {
        "driver": "GTiff",
        "dtype": rasterio.float32,
        "width": grid.shape[1],
        "height": grid.shape[0],
        "count": 1,
        "crs": CRS.from_epsg(4326),
        "transform": transform,
        "compress": "deflate",
        "predictor": 3,
        "nodata": np.nan,
    }
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(grid, 1)
        dst.update_tags(
            UNITS=units,
            DESCRIPTION="Tropospheric NO2 vertical column (warped from L2 swath)",
            SOURCE_NC=str(args.nc.resolve()),
            EXTENT=f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}",
            RES_DEG=str(res_used),
        )

    print(f"Wrote {out.resolve()}")
    print(f"  extent W,S,E,N: {west:.4f}, {south:.4f}, {east:.4f}, {north:.4f}")
    print(f"  res_deg: {res_used:.6f}")
    print(f"  shape: {grid.shape[1]} x {grid.shape[0]}  CRS: EPSG:4326  units: {units}")


if __name__ == "__main__":
    main()
