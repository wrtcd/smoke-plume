"""
Plot plume enhancement (ΔΩ_enh) and optional layer-mean NO₂ proxy (µg/m³) across cases.

Reads each ``pipeline_summary.json`` under ``--study-root/<case_id>/`` (output of
``run_all_cases.py`` with ``--mixing-height-m``).

Run from repo root:
  python scripts/render_plume_enhancement_figures.py --study-root results/study_batch_plume_enhancement
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _p95_conc_um3(pe: dict, fp_stats_min: float) -> tuple[float | None, float | None]:
    ug = pe.get("approx_mean_no2_ug_m3")
    if not isinstance(ug, dict):
        return None, None
    core_key = f"where_fp_ge_{fp_stats_min}"
    s = ug.get("where_fp_gt_0.01")
    c = ug.get(core_key)
    ps = float(s["p95"]) if isinstance(s, dict) and s.get("count", 0) else None
    pc = float(c["p95"]) if isinstance(c, dict) and c.get("count", 0) else None
    return ps, pc


def _p95_col(pe: dict, fp_stats_min: float) -> tuple[float | None, float | None]:
    d = pe.get("delta_vcd_enhancement_molec_cm2")
    if not isinstance(d, dict):
        return None, None
    core_key = f"where_fp_ge_{fp_stats_min}"
    s = d.get("where_fp_gt_0.01")
    c = d.get(core_key)
    ps = float(s["p95"]) if isinstance(s, dict) and s.get("count", 0) else None
    pc = float(c["p95"]) if isinstance(c, dict) and c.get("count", 0) else None
    return ps, pc


def main() -> None:
    ap = argparse.ArgumentParser(description="Figures from plume_enhancement block in pipeline summaries.")
    ap.add_argument(
        "--study-root",
        type=Path,
        default=REPO_ROOT / "results/study_batch_plume_enhancement",
        help="Directory containing one subfolder per case with pipeline_summary.json",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Figure output directory (default: <study-root>/figures)",
    )
    ap.add_argument(
        "--fp-stats-min",
        type=float,
        default=0.1,
        help="Must match fp_stats_min used in the batch run (for dict keys).",
    )
    args = ap.parse_args()

    study_root = args.study_root.resolve()
    if not study_root.is_dir():
        print(f"Missing directory: {study_root}", file=sys.stderr)
        sys.exit(1)

    out_dir = args.out_dir.resolve() if args.out_dir else (study_root / "figures")
    out_dir.mkdir(parents=True, exist_ok=True)

    names: list[str] = []
    col_smoky: list[float] = []
    col_core: list[float] = []
    ug_smoky: list[float] = []
    ug_core: list[float] = []
    H_m: float | None = None

    for sub in sorted(study_root.iterdir()):
        if not sub.is_dir():
            continue
        p = sub / "pipeline_summary.json"
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        pe = data.get("plume_enhancement")
        if not isinstance(pe, dict):
            continue
        names.append(sub.name)
        ps, pc = _p95_col(pe, args.fp_stats_min)
        col_smoky.append(ps if ps is not None else float("nan"))
        col_core.append(pc if pc is not None else float("nan"))
        us, uc = _p95_conc_um3(pe, args.fp_stats_min)
        ug_smoky.append(us if us is not None else float("nan"))
        ug_core.append(uc if uc is not None else float("nan"))
        hm = pe.get("mixing_height_m")
        if isinstance(hm, (int, float)):
            H_m = float(hm)

    if len(names) < 1:
        print(f"No pipeline_summary.json found under {study_root}", file=sys.stderr)
        sys.exit(1)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    y = np.arange(len(names))
    colors = plt.cm.tab10(np.linspace(0, 0.85, len(names)))

    # Figure 1: p95 ΔΩ_enh (column)
    fig, ax = plt.subplots(figsize=(9, max(4.0, 0.35 * len(names) + 2)))
    w = 0.35
    ax.barh(y - w / 2, col_smoky, height=w, label="f_p > 0.01", color=colors, alpha=0.85, edgecolor="white")
    ax.barh(y + w / 2, col_core, height=w, label=f"f_p ≥ {args.fp_stats_min}", color=colors, alpha=0.45, edgecolor="black", linewidth=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlabel("p95 ΔΩ_enh (molecules/cm²)")
    ax.set_title("Plume enhancement column — 95th percentile within smoky pixels\n(ΔΩ_enh = max(VCD − VCD_bg, 0); same QA/mask rules per batch)")
    ax.legend(loc="lower right")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "plume_enhancement_p95_delta_column.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # Figure 2: p95 approximate µg/m³ (if mixing height present)
    if H_m is not None and np.any(np.isfinite(ug_smoky)):
        fig2, ax2 = plt.subplots(figsize=(9, max(4.0, 0.35 * len(names) + 2)))
        ax2.barh(y - w / 2, ug_smoky, height=w, label="f_p > 0.01", color=colors, alpha=0.85, edgecolor="white")
        ax2.barh(y + w / 2, ug_core, height=w, label=f"f_p ≥ {args.fp_stats_min}", color=colors, alpha=0.45, edgecolor="black", linewidth=0.5)
        ax2.set_yticks(y)
        ax2.set_yticklabels(names)
        ax2.set_xlabel("p95 approximate layer-mean NO₂ (µg/m³)")
        ax2.set_title(
            f"Concentration proxy: ΔΩ_enh ÷ H with H = {H_m:.0f} m\n"
            "(uniform slab assumption — illustrative, not in situ)"
        )
        ax2.legend(loc="lower right")
        ax2.grid(True, axis="x", alpha=0.3)
        fig2.tight_layout()
        fig2.savefig(out_dir / "plume_enhancement_p95_ug_m3_proxy.png", dpi=140, bbox_inches="tight")
        plt.close(fig2)

    print(f"Wrote figures under {out_dir}")


if __name__ == "__main__":
    main()
