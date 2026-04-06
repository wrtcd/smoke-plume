"""
Build committed comparison figures for docs/pipeline_layman_guide.md from the study batch
numbers in results/study_batch/*/pipeline_summary.json when present; else use embedded defaults.

Run from repo root:
  py -3 scripts/render_case_study_comparison.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "docs" / "images"
STUDY_ROOT = REPO_ROOT / "results" / "study_batch"

# Fallback if local pipeline outputs are missing (matches STUDY_BATCH_RESULTS.md study batch).
DEFAULT_CASES: list[tuple[str, float, int, int]] = [
    # id, total_enhancement_no2_kg, pixels_plume_fp_gt_0.01, pixels_tempo
    ("airport", 1515.4887188151129, 467, 9640800),
    ("bridge", 3986.600514391332, 534, 8874000),
    ("eaton", 1957.2485020409267, 845, 8035200),
    ("line", 2831.6592858738013, 433, 8222400),
    ("palisades", 1375.0102636471495, 73, 2096220),
    ("park", 1237.5454116133928, 649, 9309600),
]


def _load_from_disk() -> list[tuple[str, float, int, int]] | None:
    if not STUDY_ROOT.is_dir():
        return None
    rows: list[tuple[str, float, int, int]] = []
    for sub in sorted(STUDY_ROOT.iterdir()):
        if not sub.is_dir():
            continue
        p = sub / "pipeline_summary.json"
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "total_enhancement_no2_kg" in data:
            mass = float(data["total_enhancement_no2_kg"])
        elif "total_excess_no2_kg" in data:
            mass = float(data["total_excess_no2_kg"])
        else:
            # Back-compat: if only signed anomaly exists, plot its magnitude.
            mass = abs(float(data.get("total_excess_no2_kg_signed", 0.0)))
        np_p = int(data["pixels_plume_fp_gt_0.01"])
        np_t = int(data["pixels_tempo"])
        rows.append((sub.name, mass, np_p, np_t))
    if len(rows) < 3:
        return None
    rows.sort(key=lambda x: x[0])
    return rows


def _plot(rows: list[tuple[str, float, int, int]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    names = [r[0] for r in rows]
    mass = np.array([r[1] for r in rows], dtype=np.float64)
    plume_px = np.array([r[2] for r in rows], dtype=np.float64)
    tempo_px = np.array([r[3] for r in rows], dtype=np.float64)
    colors = plt.cm.tab10(np.linspace(0, 0.85, len(names)))

    # --- Figure 1: three horizontal bar charts (same order: alphabetical by region)
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=False)
    y = np.arange(len(names))

    axes[0].barh(y, mass, color=colors, edgecolor="white", linewidth=0.8)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(names)
    axes[0].set_xlabel("Total excess NO₂ (kg)")
    axes[0].set_title("A) Integrated plume-weighted excess mass\n(same mask + background rules for all six)")
    for i, v in enumerate(mass):
        axes[0].text(v + max(mass) * 0.01, i, f"{v:.0f}", va="center", fontsize=9)

    axes[1].barh(y, plume_px, color=colors, edgecolor="white", linewidth=0.8)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels(names)
    axes[1].set_xlabel("Count of TEMPO pixels with f_p > 0.01")
    axes[1].set_title("B) How many coarse pixels look “smoky” enough to count as plume")
    for i, v in enumerate(plume_px):
        axes[1].text(v + max(plume_px) * 0.02, i, f"{int(v)}", va="center", fontsize=9)

    tempo_m = tempo_px / 1e6
    axes[2].barh(y, tempo_m, color=colors, edgecolor="white", linewidth=0.8)
    axes[2].set_yticks(y)
    axes[2].set_yticklabels(names)
    axes[2].set_xlabel("TEMPO grid size (million pixels in the GeoTIFF)")
    axes[2].set_title("C) Size of the domain the mass sum runs over\n(bigger swath ≠ worse fire—just more cells)")
    for i, v in enumerate(tempo_px):
        axes[2].text(v / 1e6 + max(tempo_m) * 0.01, i, f"{v/1e6:.2f}M", va="center", fontsize=9)

    fig.suptitle("Six study regions — apples use the same peeler, oranges differ by the fruit", fontsize=11, y=1.01)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "case_study_six_way_bars.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # --- Figure 2: scatter mass vs plume pixels (intuition: not a straight line)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(plume_px, mass, s=120, c=colors, edgecolors="black", linewidths=0.8, zorder=3)
    for i, nm in enumerate(names):
        ax.annotate(nm, (plume_px[i], mass[i]), textcoords="offset points", xytext=(6, 4), fontsize=9)
    ax.set_xlabel("Plume pixels (f_p > 0.01)")
    ax.set_ylabel("Total excess NO₂ (kg)")
    ax.set_title("Mass vs. “how many plume-ish cells” — not a simple scoreboard\n(high kg can be few cells with huge columns, or many cells with modest columns)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "case_study_mass_vs_plume_scatter.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # --- Figure 3: “kg per plume pixel” (rough intensity — only among flagged plume pixels)
    with np.errstate(divide="ignore", invalid="ignore"):
        kpp = mass / np.maximum(plume_px, 1.0)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    order = np.argsort(kpp)[::-1]
    xo = np.arange(len(names))
    ax.bar(xo, kpp[order], color=colors[order], edgecolor="white")
    ax.set_xticks(xo)
    ax.set_xticklabels([names[i] for i in order], rotation=25, ha="right")
    ax.set_ylabel("kg / plume pixel (very rough)")
    ax.set_title(
        "D) “Typical strength per smoky cell” (total kg ÷ plume-pixel count)\n"
        "Palisades jumps here: fewer cells, but each can carry a lot of signal"
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "case_study_kg_per_plume_pixel.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    rows = _load_from_disk()
    if rows is None:
        rows = DEFAULT_CASES
        print("Using embedded default numbers (run pipeline batch locally for live JSON).", file=sys.stderr)
    else:
        print(f"Loaded {len(rows)} cases from {STUDY_ROOT}", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _plot(rows)
    print(f"Wrote docs/images/case_study_six_way_bars.png")
    print(f"Wrote docs/images/case_study_mass_vs_plume_scatter.png")
    print(f"Wrote docs/images/case_study_kg_per_plume_pixel.png")


if __name__ == "__main__":
    main()
