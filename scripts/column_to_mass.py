"""
Step 5 — Convert plume-weighted excess column (ΔVCD_plume) to total NO2 mass (kg).

  Mass = sum over pixels ( ΔVCD_plume × A ) in molecules → mol → kg

  ΔVCD_plume: molecules/cm² (or mol/m² with --vcd-units mol_m2)
  A: pixel area (m²), from geotransform (same as palisades_pipeline)

Run from repo root:
  python scripts/column_to_mass.py --raster results/step_04_plume_enhancement/delta_vcd_plume.tif
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

from palisades_pipeline import (
    REPO_ROOT,
    excess_mass_molec_cm2,
    excess_mass_mol_m2,
    _pixel_areas_m2,
    AVOGADRO,
    M_NO2_KG_PER_MOL,
)


def main() -> None:
    p = argparse.ArgumentParser(description="Step 5: column integral to NO2 mass (kg)")
    p.add_argument(
        "--raster",
        type=Path,
        default=REPO_ROOT / "results/step_04_plume_enhancement/delta_vcd_plume.tif",
        help="Single-band GeoTIFF: f_p × (VCD - VCD_bg), same units as TEMPO VCD",
    )
    p.add_argument(
        "--vcd-units",
        choices=("molec_cm2", "mol_m2"),
        default="molec_cm2",
        help="Vertical column units in the raster (default: NASA L2 trop VCD).",
    )
    p.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Write summary JSON (default: results/step_05_mass/column_mass.json)",
    )
    args = p.parse_args()

    if not args.raster.is_file():
        print(f"Missing raster: {args.raster}", file=sys.stderr)
        sys.exit(1)

    out_json = args.out_json
    if out_json is None:
        out_dir = REPO_ROOT / "results/step_05_mass"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_json = out_dir / "column_mass.json"

    with rasterio.open(args.raster) as ds:
        arr = ds.read(1).astype(np.float64)
        nodata = ds.nodata
        if nodata is not None:
            arr = np.where(arr == nodata, np.nan, arr)
        h, w = arr.shape
        area = _pixel_areas_m2(ds.transform, h, w)

    if args.vcd_units == "molec_cm2":
        mass_kg = excess_mass_molec_cm2(arr, area)
        formula = "kg = sum(ΔVCD_plume[molec/cm²] × area[cm²]) / N_A × M_NO2; area_cm2 = area_m2 × 1e4"
    else:
        mass_kg = excess_mass_mol_m2(arr, area)
        formula = "kg = sum(ΔVCD_plume[mol/m²] × area[m²]) × M_NO2"

    summary = {
        "step": "05_column_to_mass",
        "input_raster": str(args.raster.resolve()),
        "vcd_units": args.vcd_units,
        "formula": formula,
        "constants": {
            "N_A": AVOGADRO,
            "M_NO2_kg_per_mol": M_NO2_KG_PER_MOL,
        },
        "total_excess_no2_kg": mass_kg,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {out_json.resolve()}")


if __name__ == "__main__":
    main()
