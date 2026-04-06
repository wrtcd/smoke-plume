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
    --nc smoke-plume-data/palisades/tempo/TEMPO_NO2_L2_V03_20250110T184529Z_S008G09.nc \\
    -o smoke-plume-data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif \\
    --stack --amf-plume-adjust --plume-height-agl-m 1000

QA: by default, mask VCD where main_data_quality_flag != 0. Optional --no-qa, --ground-qa-zero.
Cloud: by default, mask where eff_cloud_fraction > 0.2; use --no-cloud-mask to skip.
--amf-plume-adjust: optional VCD rescaling for plume height (default 1000 m AGL); see tempo_amf_plume_adjust.py
and results/step_03_tempo_qa/README.md.

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
        "  python scripts/tempo_l2_to_4326.py --nc smoke-plume-data/<region>/tempo/<your>.nc\n",
        file=sys.stderr,
    )
    sys.exit(1)

import numpy as np
import rasterio
from rasterio.crs import CRS
from scipy.interpolate import LinearNDInterpolator

from tempo_amf_plume_adjust import adjust_troposphere_vcd

FILL = -1e30


def valid_pixels_mask_vcd(lat: np.ndarray, lon: np.ndarray, vcd: np.ndarray) -> np.ndarray:
    # Negative VCD is valid for TEMPO (differential retrieval); exclude fill / huge sentinels only.
    return (
        np.isfinite(lat)
        & np.isfinite(lon)
        & np.isfinite(vcd)
        & (vcd > FILL / 2)
        & (vcd < 1e30)
    )


def valid_pixels_mask_generic(lat: np.ndarray, lon: np.ndarray, z: np.ndarray) -> np.ndarray:
    return np.isfinite(lat) & np.isfinite(lon) & np.isfinite(z)


def swath_extent_wsen(lat: np.ndarray, lon: np.ndarray, vcd: np.ndarray) -> tuple[float, float, float, float]:
    vm = valid_pixels_mask_vcd(lat, lon, vcd)
    if np.sum(vm) < 10:
        raise ValueError("Too few valid pixels in swath; check QA / file.")
    return (
        float(np.min(lon[vm])),
        float(np.min(lat[vm])),
        float(np.max(lon[vm])),
        float(np.max(lat[vm])),
    )


def read_swath(
    nc_path: Path,
    *,
    use_main_qa: bool,
    max_cloud_fraction: float | None,
    use_ground_qa_zero: bool,
    amf_plume_adjust: bool,
    plume_height_agl_m: float,
    plume_fwhm_m: float,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    str,
    dict[str, np.ndarray],
]:
    """
    Read TEMPO L2 swath. Returns lat, lon, masked VCD, VCD units, and ancillary 2D arrays
    (amf_troposphere, amf_total, eff_cloud_fraction, main_data_quality_flag, ground_pixel_quality_flag)
    for gridding when --stack is used. Ancillary arrays are not masked (inspect in QGIS); VCD is masked.

    Optional --amf-plume-adjust: rescale tropospheric VCD using scattering_weights and retrieval prior
    (gas_profile) vs a Gaussian plume in height AGL (see tempo_amf_plume_adjust.py), then QA/cloud masks.
    """
    ancillary: dict[str, np.ndarray] = {}
    with nc.Dataset(nc_path) as ds:
        lat = np.asarray(ds.groups["geolocation"].variables["latitude"][:], dtype=np.float64)
        lon = np.asarray(ds.groups["geolocation"].variables["longitude"][:], dtype=np.float64)
        vcd = np.asarray(ds.groups["product"].variables["vertical_column_troposphere"][:], dtype=np.float64)
        v = ds.groups["product"].variables["vertical_column_troposphere"]
        units = str(getattr(v, "units", "molecules/cm^2") or "molecules/cm^2")

        main_qa = None
        if "main_data_quality_flag" in ds.groups["product"].variables:
            main_qa = np.asarray(ds.groups["product"].variables["main_data_quality_flag"][:], dtype=np.int32)
        ground_qa = None
        if "ground_pixel_quality_flag" in ds.groups["support_data"].variables:
            ground_qa = np.asarray(ds.groups["support_data"].variables["ground_pixel_quality_flag"][:], dtype=np.int32)
        eff_cloud = None
        if "eff_cloud_fraction" in ds.groups["support_data"].variables:
            eff_cloud = np.asarray(ds.groups["support_data"].variables["eff_cloud_fraction"][:], dtype=np.float64)
        amf_trop = None
        if "amf_troposphere" in ds.groups["support_data"].variables:
            amf_trop = np.asarray(ds.groups["support_data"].variables["amf_troposphere"][:], dtype=np.float64)
        amf_tot = None
        if "amf_total" in ds.groups["support_data"].variables:
            amf_tot = np.asarray(ds.groups["support_data"].variables["amf_total"][:], dtype=np.float64)

        if amf_plume_adjust and amf_trop is not None:
            sw = np.asarray(ds.groups["support_data"].variables["scattering_weights"][:], dtype=np.float64)
            gas = np.asarray(ds.groups["support_data"].variables["gas_profile"][:], dtype=np.float64)
            ps = np.asarray(ds.groups["support_data"].variables["surface_pressure"][:], dtype=np.float64)
            vcd, amf_adj, _ = adjust_troposphere_vcd(
                vcd,
                amf_trop,
                sw,
                gas,
                ps,
                plume_height_agl_m=plume_height_agl_m,
                plume_fwhm_m=plume_fwhm_m,
            )
            ancillary["amf_troposphere_plume_adjusted"] = amf_adj.astype(np.float64)

        if use_main_qa and main_qa is not None:
            vcd = np.where(main_qa == 0, vcd, np.nan)
        if max_cloud_fraction is not None and eff_cloud is not None:
            bad = np.isfinite(eff_cloud) & (eff_cloud > max_cloud_fraction)
            vcd = np.where(bad, np.nan, vcd)
        if use_ground_qa_zero and ground_qa is not None:
            vcd = np.where(ground_qa == 0, vcd, np.nan)

        if amf_trop is not None:
            ancillary["amf_troposphere"] = amf_trop
        if amf_tot is not None:
            ancillary["amf_total"] = amf_tot
        if eff_cloud is not None:
            ancillary["eff_cloud_fraction"] = eff_cloud
        if main_qa is not None:
            ancillary["main_data_quality_flag"] = main_qa.astype(np.float64)
        if ground_qa is not None:
            ancillary["ground_pixel_quality_flag"] = ground_qa.astype(np.float64)

    return lat, lon, vcd, units, ancillary


def warp_to_4326(
    lat: np.ndarray,
    lon: np.ndarray,
    z: np.ndarray,
    west: float,
    south: float,
    east: float,
    north: float,
    res_deg: float,
    *,
    valid_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, rasterio.Affine]:
    if valid_mask is None:
        valid_mask = valid_pixels_mask_vcd(lat, lon, z)
    valid = (
        valid_mask
        & (lon >= west)
        & (lon <= east)
        & (lat >= south)
        & (lat <= north)
    )
    pts = np.column_stack([lon[valid], lat[valid]])
    vals = z[valid]
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


def warp_ancillary(
    lat: np.ndarray,
    lon: np.ndarray,
    z: np.ndarray,
    west: float,
    south: float,
    east: float,
    north: float,
    res_deg: float,
) -> tuple[np.ndarray, rasterio.Affine]:
    """Grid a swath field using finite z samples (AMF, cloud, flags)."""
    valid = valid_pixels_mask_generic(lat, lon, z) & (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)
    return warp_to_4326(lat, lon, z, west, south, east, north, res_deg, valid_mask=valid)


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
        help="Do not mask pixels with main_data_quality_flag != 0 before gridding",
    )
    p.add_argument(
        "--max-cloud",
        type=float,
        default=0.2,
        metavar="FRACTION",
        help="Mask VCD where eff_cloud_fraction > FRACTION (default 0.2 per TEMPO trace-gas user guide).",
    )
    p.add_argument(
        "--no-cloud-mask",
        action="store_true",
        help="Do not mask by eff_cloud_fraction (ignores --max-cloud).",
    )
    p.add_argument(
        "--ground-qa-zero",
        action="store_true",
        help="Also require ground_pixel_quality_flag == 0 (verify flag semantics in ATBD before using).",
    )
    p.add_argument(
        "--stack",
        action="store_true",
        help="Write multi-band GeoTIFF: band1 VCD, then amf_troposphere, amf_total, eff_cloud, main QA, ground QA (when present).",
    )
    p.add_argument(
        "--amf-plume-adjust",
        action="store_true",
        help="Rescale tropospheric VCD for assumed plume height (scattering_weights + gas_profile); see tempo_amf_plume_adjust.py",
    )
    p.add_argument(
        "--plume-height-agl-m",
        type=float,
        default=1000.0,
        metavar="M",
        help="Plume center height above ground level (m). Default 1000 (~1 km).",
    )
    p.add_argument(
        "--plume-fwhm-m",
        type=float,
        default=500.0,
        metavar="M",
        help="Vertical FWHM of Gaussian plume shape in height (m). Default 500.",
    )
    args = p.parse_args()

    out = args.output
    if out is None:
        out = args.nc.parent / "TEMPO_NO2_trop_warped_4326.tif"

    max_cloud_fraction = None if args.no_cloud_mask else args.max_cloud
    lat, lon, vcd, units, ancillary = read_swath(
        args.nc,
        use_main_qa=not args.no_qa,
        max_cloud_fraction=max_cloud_fraction,
        use_ground_qa_zero=args.ground_qa_zero,
        amf_plume_adjust=args.amf_plume_adjust,
        plume_height_agl_m=args.plume_height_agl_m,
        plume_fwhm_m=args.plume_fwhm_m,
    )
    if args.bbox is None:
        west, south, east, north = swath_extent_wsen(lat, lon, vcd)
    else:
        west, south, east, north = args.bbox

    if args.res is None:
        span = max(east - west, north - south)
        res_used = max(span / 3600.0, 0.005)
    else:
        res_used = args.res

    grid_vcd, transform = warp_to_4326(lat, lon, vcd, west, south, east, north, res_used)

    band_order: list[tuple[str, np.ndarray | None]] = [
        ("vertical_column_troposphere", None),
    ]
    if args.stack:
        for key in (
            "amf_troposphere_plume_adjusted",
            "amf_troposphere",
            "amf_total",
            "eff_cloud_fraction",
            "main_data_quality_flag",
            "ground_pixel_quality_flag",
        ):
            if key in ancillary:
                band_order.append((key, ancillary[key]))

    layers: list[np.ndarray] = [grid_vcd]
    if args.stack:
        for name, arr in band_order[1:]:
            assert arr is not None
            g, _t = warp_ancillary(lat, lon, arr, west, south, east, north, res_used)
            if g.shape != grid_vcd.shape:
                raise RuntimeError(f"Band {name} shape mismatch vs VCD")
            layers.append(g)

    profile = {
        "driver": "GTiff",
        "dtype": rasterio.float32,
        "width": grid_vcd.shape[1],
        "height": grid_vcd.shape[0],
        "count": len(layers),
        "crs": CRS.from_epsg(4326),
        "transform": transform,
        "compress": "deflate",
        "predictor": 3,
        "nodata": np.nan,
    }
    vcd_band_desc = "Tropospheric NO2 VCD"
    if args.amf_plume_adjust:
        vcd_band_desc += f" (AMF plume-adjusted, z={args.plume_height_agl_m:.0f}m AGL)"
    vcd_band_desc += " (masked per QA/cloud flags)"
    descriptions = [vcd_band_desc]
    if args.stack:
        desc_map = {
            "amf_troposphere_plume_adjusted": "AMF troposphere after plume-profile adjustment",
            "amf_troposphere": "AMF troposphere (L2 operational)",
            "amf_total": "AMF total (support_data)",
            "eff_cloud_fraction": "Effective cloud fraction",
            "main_data_quality_flag": "main_data_quality_flag (float copy)",
            "ground_pixel_quality_flag": "ground_pixel_quality_flag (float copy)",
        }
        descriptions.extend([desc_map.get(name, name) for name, _ in band_order[1:]])

    with rasterio.open(out, "w", **profile) as dst:
        for i, layer in enumerate(layers, start=1):
            dst.write(layer, i)
            if i <= len(descriptions):
                d = descriptions[i - 1]
                dst.set_band_description(i, d if len(d) <= 256 else d[:253] + "...")
        tag_qa = (
            f"main_qa={'off' if args.no_qa else 'mask nonzero'}; "
            f"cloud={'off' if max_cloud_fraction is None else f'mask eff_cloud > {max_cloud_fraction}'}; "
            f"ground_qa_zero={args.ground_qa_zero}"
        )
        dst.update_tags(
            UNITS=units,
            DESCRIPTION="Tropospheric NO2 vertical column (warped from L2 swath)",
            SOURCE_NC=str(args.nc.resolve()),
            EXTENT=f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}",
            RES_DEG=str(res_used),
            QA_POLICY=tag_qa,
            STACK=str(args.stack),
            AMF_PLUME_ADJUST=str(args.amf_plume_adjust),
            PLUME_HEIGHT_AGL_M=str(args.plume_height_agl_m),
            PLUME_FWHM_M=str(args.plume_fwhm_m),
        )

    print(f"Wrote {out.resolve()}")
    print(f"  extent W,S,E,N: {west:.4f}, {south:.4f}, {east:.4f}, {north:.4f}")
    print(f"  res_deg: {res_used:.6f}")
    print(f"  shape: {grid_vcd.shape[1]} x {grid_vcd.shape[0]}  CRS: EPSG:4326  units: {units}")
    print(f"  bands: {len(layers)}  stack={args.stack}  amf_plume_adjust={args.amf_plume_adjust}  {tag_qa}")


if __name__ == "__main__":
    main()
