"""
Copy study-batch map PNGs into docs/images/cases/ so pipeline_layman_guide.md
can embed real previews without relying on gitignored results/.

Run from repo root after generating maps:
  py -3 scripts/study_batch_visuals.py --results-root results/study_batch
  py -3 scripts/sync_guide_case_images.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STUDY = REPO_ROOT / "results" / "study_batch"
OUT = REPO_ROOT / "docs" / "images" / "cases"

FILES = (
    ("f_p_preview.png", "_f_p_preview.png"),
    ("delta_vcd_plume_preview.png", "_delta_vcd_plume_preview.png"),
    ("histograms.png", "_histograms.png"),
)


def main() -> int:
    if not STUDY.is_dir():
        print(f"Missing {STUDY} — run study_batch_visuals.py first.", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    copied = 0
    missing: list[str] = []
    for region_dir in sorted(p for p in STUDY.iterdir() if p.is_dir()):
        region = region_dir.name
        maps = region_dir / "maps"
        if not maps.is_dir():
            missing.append(f"{region}/maps/")
            continue
        for src_name, suffix in FILES:
            src = maps / src_name
            if not src.is_file():
                missing.append(str(src.relative_to(REPO_ROOT)))
                continue
            dst = OUT / f"{region}{suffix}"
            shutil.copy2(src, dst)
            copied += 1
    print(f"Copied {copied} file(s) -> {OUT.relative_to(REPO_ROOT)}")
    if missing:
        print("Missing (skipped):", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 1 if copied == 0 else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
