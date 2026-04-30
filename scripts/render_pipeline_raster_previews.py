"""
PNG previews for pipeline Step-4 GeoTIFFs.

Enhancement rasters (ΔΩ_enh, f_p×ΔΩ_enh) are mostly zeros; linear percentile stretch
often hides the plume. This script uses log scaling on strictly positive pixels for those.

Outputs:
  - Per-case 2×2: ``<case>_pipeline_rasters.png``
  - Focus (enhancement): ``<case>_plume_enhancement_LOG.png`` — large 1×2 log-scale panels
  - All cases: ``ALL_CASES_plume_enhancement_LOG.png``
  - Browser gallery: ``index.html``

Run from repo root:
  py -3 scripts/render_pipeline_raster_previews.py --batch-root results/study_batch_plume_enhancement
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_masked(path: Path) -> tuple[np.ma.MaskedArray, object]:
    import rasterio

    with rasterio.open(path) as ds:
        arr = ds.read(1).astype(np.float64)
        nodata = ds.nodata
        if nodata is not None:
            arr = np.ma.masked_where(arr == nodata, arr)
        arr = np.ma.masked_where(~np.isfinite(arr), arr)
        return arr, ds.transform


def _finite_max(data: np.ma.MaskedArray) -> float:
    if data.count() == 0:
        return float("nan")
    return float(np.max(data.compressed()))


def _imshow_log_positive(
    ax,
    data: np.ma.MaskedArray,
    *,
    cmap: str = "inferno",
    title: str,
    subtitle: str = "",
) -> None:
    """Show positive values on log scale; zero/negative masked (transparent in overlay sense — shows bg)."""
    from matplotlib.colors import LogNorm

    pos = np.ma.masked_where(~np.isfinite(data) | (data <= 0), data)
    if pos.count() == 0:
        ax.set_facecolor("#e8e8e8")
        ax.text(
            0.5,
            0.5,
            "No positive\npixels",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=11,
        )
        ax.set_axis_off()
        ax.set_title(title)
        return

    pv = pos.compressed().astype(np.float64)
    vmin = float(np.percentile(pv, 5))
    vmax = float(np.percentile(pv, 99.9))
    vmin = max(vmin, 1e10)
    if vmax <= vmin * 1.05:
        vmax = vmin * 50
    im = ax.imshow(pos, origin="upper", cmap=cmap, norm=LogNorm(vmin=vmin, vmax=vmax))
    import matplotlib.pyplot as plt

    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, extend="max")
    ttl = title if not subtitle else f"{title}\n{subtitle}"
    ax.set_title(ttl, fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])


def _render_four_panel(case_dir: Path, cid: str, out_dir: Path) -> Path | None:
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    names = ("f_p.tif", "delta_vcd.tif", "delta_vcd_enh.tif", "delta_vcd_plume.tif")
    titles = (
        "f_p",
        "ΔVCD signed",
        "ΔΩ_enh\n(log₁₀, Δ>0)",
        "f_p×ΔΩ_enh\n(log₁₀, Δ>0)",
    )
    paths = [case_dir / n for n in names]
    if not all(p.is_file() for p in paths):
        return None

    fig, axes = plt.subplots(2, 2, figsize=(11, 10), sharex=True, sharey=True)
    axes_flat = axes.ravel()

    for ax, rel, title, p in zip(axes_flat, names, titles, paths):
        data, _ = _read_masked(p)
        if data.count() == 0:
            ax.set_title(f"{title}\n(no data)")
            ax.set_axis_off()
            continue
        if rel == "f_p.tif":
            im = ax.imshow(data, origin="upper", cmap="viridis", vmin=0, vmax=1)
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        elif rel == "delta_vcd.tif":
            mm = float(np.nanpercentile(np.abs(data.compressed()), 98))
            if mm <= 0:
                mm = 1.0
            im = ax.imshow(data, origin="upper", cmap="RdBu_r", vmin=-mm, vmax=mm)
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        elif rel in ("delta_vcd_enh.tif", "delta_vcd_plume.tif"):
            pos = np.ma.masked_where(~np.isfinite(data) | (data <= 0), data)
            if pos.count() == 0:
                ax.set_facecolor("#eee")
                ax.text(0.5, 0.5, "no Δ>0", ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
                ax.set_title(title)
                continue
            pv = pos.compressed()
            vmin = max(float(np.percentile(pv, 5)), 1e10)
            vmax = max(float(np.percentile(pv, 99.9)), vmin * 10)
            im = ax.imshow(pos, origin="upper", cmap="inferno", norm=LogNorm(vmin=vmin, vmax=vmax))
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            ax.set_title(title + "\n(log₁₀ positive)")
        ax.set_xticks([])
        ax.set_yticks([])

    fig.suptitle(f"{cid} — full pipeline window", fontsize=12)
    fig.tight_layout()
    outp = out_dir / f"{cid}_pipeline_rasters.png"
    fig.savefig(outp, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return outp


def _render_enhancement_focus(case_dir: Path, cid: str, out_dir: Path) -> Path | None:
    """Large log-scale enhancement panels with numeric max in title."""
    import matplotlib.pyplot as plt

    enh_p = case_dir / "delta_vcd_enh.tif"
    plm_p = case_dir / "delta_vcd_plume.tif"
    fp_p = case_dir / "f_p.tif"
    if not enh_p.is_file() or not plm_p.is_file():
        return None

    enh, _ = _read_masked(enh_p)
    plm, _ = _read_masked(plm_p)
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))

    if fp_p.is_file():
        fp, _ = _read_masked(fp_p)
        if fp.count():
            im0 = axes[0].imshow(fp, origin="upper", cmap="viridis", vmin=0, vmax=1)
            plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
            axes[0].set_title(f"{cid}\nf_p (smoke)")
            axes[0].set_xticks([])
            axes[0].set_yticks([])

    mx_en = _finite_max(enh)
    mx_pl = _finite_max(plm)
    _imshow_log_positive(
        axes[1],
        enh,
        title="ΔΩ_enh = max(VCD−Vbg, 0)",
        subtitle=f"max pixel ≈ {mx_en:.3g} molec/cm²",
    )
    _imshow_log_positive(
        axes[2],
        plm,
        title="f_p × ΔΩ_enh",
        subtitle=f"max pixel ≈ {mx_pl:.3g} molec/cm²",
    )

    fig.suptitle(f"{cid} — plume enhancement (log scale on Δ>0)", fontsize=11, y=1.02)
    fig.tight_layout()
    outp = out_dir / f"{cid}_plume_enhancement_LOG.png"
    fig.savefig(outp, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return outp


def _render_all_cases_grid(case_dirs: list[Path], out_dir: Path) -> Path | None:
    import matplotlib.pyplot as plt

    n = len(case_dirs)
    if n == 0:
        return None

    fig, axes = plt.subplots(n, 3, figsize=(14, 2.8 * n), squeeze=False)

    for row, case_dir in enumerate(case_dirs):
        cid = case_dir.name
        fp_p = case_dir / "f_p.tif"
        enh_p = case_dir / "delta_vcd_enh.tif"
        plm_p = case_dir / "delta_vcd_plume.tif"

        ax0, ax1, ax2 = axes[row]

        if fp_p.is_file():
            fp, _ = _read_masked(fp_p)
            if fp.count():
                im = ax0.imshow(fp, origin="upper", cmap="viridis", vmin=0, vmax=1)
                if row == 0:
                    ax0.set_title("f_p")
                plt.colorbar(im, ax=ax0, fraction=0.055, pad=0.02)

        if enh_p.is_file():
            enh, _ = _read_masked(enh_p)
            mx = _finite_max(enh)
            _imshow_log_positive(
                ax1,
                enh,
                title=("ΔΩ_enh (log)" if row == 0 else ""),
                subtitle=f"max≈{mx:.2g}",
            )
            if row == 0 and not ax1.get_title():
                ax1.set_title("ΔΩ_enh (log)")

        if plm_p.is_file():
            plm, _ = _read_masked(plm_p)
            mx = _finite_max(plm)
            _imshow_log_positive(
                ax2,
                plm,
                title=("f_p×ΔΩ_enh (log)" if row == 0 else ""),
                subtitle=f"max≈{mx:.2g}",
            )
            if row == 0 and not ax2.get_title():
                ax2.set_title("f_p×ΔΩ_enh (log)")

        ax0.set_ylabel(cid, rotation=90, fontsize=10, labelpad=8)
        for ax in (ax0, ax1, ax2):
            ax.set_xticks([])
            ax.set_yticks([])

    fig.suptitle("All cases — smoke mask + plume enhancement (log on positive Δ)", fontsize=12, y=1.002)
    fig.tight_layout()
    outp = out_dir / "ALL_CASES_plume_enhancement_LOG.png"
    fig.savefig(outp, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return outp


def _write_index_html(out_dir: Path, image_paths: list[Path]) -> Path:
    rows = []
    for p in sorted(image_paths, key=lambda x: x.name):
        rel = html.escape(p.name)
        rows.append(f"<section><h2>{rel}</h2><img src=\"{rel}\" loading=\"lazy\"></section>")
    body = "\n".join(rows)
    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Pipeline raster previews</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1rem 2rem; background: #fafafa; }}
section {{ margin-bottom: 2.5rem; background: #fff; padding: 1rem; border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,.12); }}
img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
h1 {{ font-size: 1.25rem; }}
h2 {{ font-size: 0.95rem; color: #444; margin-top: 0; }}
</style></head><body>
<h1>Smoke-plume pipeline — raster previews</h1>
<p>Open this file in a browser. Enhancement panels use <strong>log scale</strong> on pixels with Δ&gt;0.</p>
{body}
</body></html>"""
    outp = out_dir / "index.html"
    outp.write_text(doc, encoding="utf-8")
    return outp


def main() -> None:
    ap = argparse.ArgumentParser(description="PNG previews for pipeline rasters.")
    ap.add_argument(
        "--batch-root",
        type=Path,
        default=REPO_ROOT / "results/study_batch_plume_enhancement",
        help="Folder with per-case subdirs containing f_p.tif etc.",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Default: <batch-root>/figures/raster_previews",
    )
    args = ap.parse_args()

    root = args.batch_root.resolve()
    out_dir = args.out_dir.resolve() if args.out_dir else root / "figures" / "raster_previews"
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = sorted(d for d in root.iterdir() if d.is_dir() and (d / "f_p.tif").is_file())
    if not cases:
        print(f"No case folders with f_p.tif under {root}", file=sys.stderr)
        sys.exit(1)

    written: list[Path] = []
    ok_cases: list[Path] = []

    for case_dir in cases:
        cid = case_dir.name
        p1 = _render_four_panel(case_dir, cid, out_dir)
        if p1:
            written.append(p1)
            ok_cases.append(case_dir)
            print(f"Wrote {p1}")
        p2 = _render_enhancement_focus(case_dir, cid, out_dir)
        if p2:
            written.append(p2)
            print(f"Wrote {p2}")

    grid = _render_all_cases_grid(ok_cases, out_dir)
    if grid:
        written.append(grid)
        print(f"Wrote {grid}")

    html_path = _write_index_html(out_dir, written)
    print(f"Wrote {html_path}")
    print(f"\nOpen in browser: file:///{str(html_path).replace(chr(92), '/')}")
    print(f"All PNGs in: {out_dir}")


if __name__ == "__main__":
    main()
