"""
Generate simple schematic PNGs for docs/pipeline_layman_guide.md (committed in repo).

Run from repo root:
  py -3 scripts/render_pipeline_guide_assets.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "docs" / "images"


def fig_fine_vs_coarse() -> None:
    """Conceptual: high-res mask vs coarse TEMPO cell with overlap fraction f_p."""
    rng = np.random.default_rng(0)
    fine = np.zeros((48, 48))
    # blob of "smoke" in fine grid
    yy, xx = np.ogrid[:48, :48]
    cy, cx = 22, 28
    fine = np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / 80.0)
    fine = (fine > 0.35).astype(float)
    fine += rng.normal(0, 0.03, fine.shape)
    fine = np.clip(fine, 0, 1)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4))

    axes[0].imshow(fine, cmap="Greys_r", vmin=0, vmax=1)
    axes[0].set_title("Planet (fine): smoke mask\n(each tiny square ≈ a few meters)")
    axes[0].axis("off")

    coarse_h, coarse_w = 6, 6
    coarse = np.zeros((coarse_h, coarse_w))
    for i in range(coarse_h):
        for j in range(coarse_w):
            r0, r1 = i * 8, (i + 1) * 8
            c0, c1 = j * 8, (j + 1) * 8
            coarse[i, j] = float(np.mean(fine[r0:r1, c0:c1]))
    im = axes[1].imshow(coarse, cmap="magma", vmin=0, vmax=1)
    axes[1].set_title("TEMPO (coarse): overlap fraction f_p\n(each big square ≈ a few km)")
    axes[1].axis("off")
    plt.colorbar(im, ax=axes[1], fraction=0.046, label="f_p (0 = no smoke, 1 = all smoke)")
    fig.suptitle(
        "Same plume, two scales: we average the fine mask into each big weather pixel.",
        fontsize=11,
        y=1.02,
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "schematic_fine_vs_coarse.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def fig_background_subtraction() -> None:
    """Bars: total column minus background equals excess (conceptual)."""
    fig, ax = plt.subplots(figsize=(7, 4))
    total, bg = 10.0, 7.0
    excess = total - bg
    x = np.arange(3)
    labels = ["Total NO₂\ncolumn\n(satellite)", "Background\n(clean air\nreference)", "Excess\n(smoke-related\nsignal)"]
    colors = ["#4a90d9", "#95a5a6", "#e67e22"]
    heights = [total, bg, excess]
    ax.bar(x, heights, color=colors, edgecolor="white", linewidth=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Strength (cartoon units — not real numbers)")
    ax.set_title("Background subtraction (idea)\nWe only count NO₂ above the “usual” level.")
    for i, h in enumerate(heights):
        ax.text(i, h + 0.2, f"{h:.1f}", ha="center", fontsize=10)
    ax.set_ylim(0, 12)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "schematic_background_subtraction.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def fig_end_to_end_strip() -> None:
    """Horizontal strip: inputs → mask → combine → mass."""
    fig, ax = plt.subplots(figsize=(10, 2.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 1)
    ax.axis("off")
    boxes = [
        (0.2, 0.2, 1.4, 0.6, "Planet\nphoto\n(fine)"),
        (2.0, 0.2, 1.4, 0.6, "Smoke\nmask"),
        (3.8, 0.2, 1.4, 0.6, "TEMPO\nNO₂ map\n(coarse)"),
        (5.6, 0.2, 1.4, 0.6, "Blend with\nf_p &\nsubtract\nbackground"),
        (7.4, 0.2, 1.4, 0.6, "Total\nsmoke NO₂\n(kg)"),
    ]
    for x, y, w, h, txt in boxes:
        ax.add_patch(
            plt.Rectangle(
                (x, y),
                w,
                h,
                fill=True,
                facecolor="#ecf0f1",
                edgecolor="#2c3e50",
                linewidth=2,
            )
        )
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=9)
    for i in range(len(boxes) - 1):
        ax.annotate(
            "",
            xy=(boxes[i + 1][0], 0.5),
            xytext=(boxes[i][0] + boxes[i][2], 0.5),
            arrowprops=dict(arrowstyle="->", color="#34495e", lw=2),
        )
    ax.set_title("End-to-end (cartoon)", fontsize=12, pad=12)
    fig.savefig(OUT_DIR / "schematic_pipeline_strip.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig_fine_vs_coarse()
    fig_background_subtraction()
    fig_end_to_end_strip()
    print(f"Wrote PNGs under {OUT_DIR}")


if __name__ == "__main__":
    main()
