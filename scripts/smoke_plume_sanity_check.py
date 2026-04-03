"""
Sanity-check pipeline results; save preview maps and a results table.

Reads pipeline_summary.json and GeoTIFFs f_p.tif, delta_vcd_plume.tif when present.
Run after smoke_plume_pipeline.py --write-maps.

  .venv\\Scripts\\python.exe scripts/smoke_plume_sanity_check.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = REPO_ROOT / "results/smoke_plume"


def _crop_slices(f_p: np.ndarray, thresh: float, margin: int) -> tuple[slice, slice]:
    hit = f_p > thresh
    ys, xs = np.where(hit)
    if ys.size == 0:
        return slice(None), slice(None)
    h, w = f_p.shape
    r0 = max(0, int(ys.min()) - margin)
    r1 = min(h, int(ys.max()) + margin + 1)
    c0 = max(0, int(xs.min()) - margin)
    c1 = min(w, int(xs.max()) + margin + 1)
    return slice(r0, r1), slice(c0, c1)


def _downsample(a: np.ndarray, max_side: int = 2000) -> np.ndarray:
    h, w = a.shape
    m = max(h, w)
    if m <= max_side:
        return a
    step = int(np.ceil(m / max_side))
    return a[::step, ::step]


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    p = argparse.ArgumentParser(description="Sanity checks + maps for smoke plume pipeline outputs.")
    p.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    args = p.parse_args()
    rd = args.results_dir
    summary_path = rd / "pipeline_summary.json"
    if not summary_path.is_file():
        print(f"Missing {summary_path}; run scripts/smoke_plume_pipeline.py first.", file=sys.stderr)
        sys.exit(1)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    fp_tif = rd / "f_p.tif"
    dv_tif = rd / "delta_vcd_plume.tif"
    maps_dir = rd / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)

    checks: dict[str, bool | str] = {}

    mass = summary.get("total_excess_no2_kg")
    vcd_bg = summary.get("vcd_background_median")
    n_plume = summary.get("pixels_plume_fp_gt_0.01")
    n_pix = summary.get("pixels_tempo")

    checks["total_mass_finite"] = bool(mass is not None and np.isfinite(mass))
    checks["total_mass_non_negative"] = bool(mass is not None and mass >= 0)
    checks["plume_pixels_gt_0"] = bool(n_plume is not None and n_plume > 0)

    # molec/cm^2: typical ambient NO2 columns often ~1e15 +/-; flag only extreme orders
    if vcd_bg is not None:
        checks["vcd_bg_plausible_order"] = bool(1e12 < vcd_bg < 1e19)
    else:
        checks["vcd_bg_plausible_order"] = False

    if n_pix and n_pix > 5_000_000:
        checks["note"] = "Large TEMPO grid (full swath?): consider clipped GeoTIFF for local analysis."

    fp_data: np.ndarray | None = None
    dv_data: np.ndarray | None = None
    nan_frac = float("nan")
    if fp_tif.is_file():
        with rasterio.open(fp_tif) as ds:
            fp_data = ds.read(1).astype(np.float64)
        nan_frac = float(np.mean(~np.isfinite(fp_data)))
        checks["f_p_low_nan"] = bool(nan_frac < 0.99)

    if dv_tif.is_file():
        with rasterio.open(dv_tif) as ds:
            dv_data = ds.read(1).astype(np.float64)
        dv_data = np.where(dv_data < -1e29, np.nan, dv_data)
        pos = dv_data[np.isfinite(dv_data) & (dv_data > 0)]
        if pos.size:
            checks["delta_vcd_plume_max"] = float(np.max(pos))
            checks["delta_vcd_plume_p95"] = float(np.percentile(pos, 95))

    # Figures (crop to plume neighborhood; downsample if still huge)
    if fp_data is not None:
        rs, cs = _crop_slices(fp_data, 0.01, margin=80)
        if rs == slice(None):
            fpc = _downsample(fp_data)
            dvc = _downsample(dv_data) if dv_data is not None else None
        else:
            fpc = fp_data[rs, cs]
            dvc = dv_data[rs, cs] if dv_data is not None else None
        fpc = _downsample(fpc)
        if dvc is not None:
            dvc = _downsample(dvc)

        fig, ax = plt.subplots(figsize=(8, 7))
        im = ax.imshow(fpc, vmin=0, vmax=max(0.05, float(np.nanpercentile(fpc, 99)) or 0.05), cmap="magma")
        ax.set_title("Plume overlap fraction f_p (cropped to plume extent)")
        ax.set_xlabel("column")
        ax.set_ylabel("row")
        plt.colorbar(im, ax=ax, fraction=0.046, label="f_p")
        fig.tight_layout()
        fig.savefig(maps_dir / "f_p_preview.png", dpi=120)
        plt.close(fig)

        if dvc is not None:
            fig, ax = plt.subplots(figsize=(8, 7))
            vmax = float(np.nanpercentile(dvc[np.isfinite(dvc) & (dvc > 0)], 99)) if np.any(dvc > 0) else 1.0
            im = ax.imshow(np.ma.masked_invalid(dvc), vmin=0, vmax=max(vmax, 1e10), cmap="viridis")
            ax.set_title("Delta VCD plume (cropped)")
            plt.colorbar(im, ax=ax, fraction=0.046, label="molec/cm2")
            fig.tight_layout()
            fig.savefig(maps_dir / "delta_vcd_plume_preview.png", dpi=120)
            plt.close(fig)

        if dv_data is not None and fp_data is not None:
            m = (fp_data > 0.01) & np.isfinite(dv_data)
            if np.any(m):
                fig, axes = plt.subplots(1, 2, figsize=(9, 4))
                axes[0].hist(fp_data[m].ravel(), bins=40, color="steelblue", edgecolor="white")
                axes[0].set_xlabel("f_p")
                axes[0].set_title("f_p where plume & valid delta")
                dvsub = dv_data[m]
                axes[1].hist(np.log10(np.maximum(dvsub, 1e10)), bins=40, color="darkgreen", edgecolor="white")
                axes[1].set_xlabel("log10(delta VCD plume)")
                axes[1].set_title("Distribution of excess column (plume pixels)")
                fig.tight_layout()
                fig.savefig(maps_dir / "histograms.png", dpi=120)
                plt.close(fig)

    # Extended table (CSV)
    table_path = rd / "sanity_table.csv"
    with table_path.open("w", encoding="utf-8") as f:
        f.write("key,value,units_or_note\n")
        f.write(f"total_excess_no2_kg,{mass},kg\n")
        f.write(f"vcd_background_median,{vcd_bg},molec_cm2\n")
        f.write(f"pixels_plume_fp_gt_0.01,{n_plume},count\n")
        f.write(f"pixels_tempo,{n_pix},count\n")
        if fp_data is not None:
            f.write(f"f_p_nan_fraction,{nan_frac:.6f},fraction\n")
        for k, v in checks.items():
            if k != "note":
                f.write(f"check_{k},{v},\n")
            else:
                f.write(f"note,{v},\n")

    report = {
        "summary_from_pipeline": summary,
        "checks": checks,
        "artifacts": {
            "maps": str(maps_dir),
            "sanity_table": str(table_path),
            "pipeline_table": str(rd / "pipeline_table.csv"),
        },
    }
    (rd / "sanity_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(checks, indent=2))
    print(f"Wrote {table_path.name}, sanity_report.json, maps under {maps_dir}")


if __name__ == "__main__":
    main()
