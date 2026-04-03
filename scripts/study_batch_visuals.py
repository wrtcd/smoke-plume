"""
For each case under results/study_batch/<id>/ with pipeline_summary.json:

1) Re-run smoke_plume_pipeline.run(..., write_maps=True) using parameters stored in
   pipeline_summary.json (writes f_p.tif, delta_vcd.tif, delta_vcd_plume.tif).
2) Run smoke_plume_sanity_check.py on that folder (writes maps/*.png, sanity_report.json).

Run from repo root:
  py -3 scripts/study_batch_visuals.py
  py -3 scripts/study_batch_visuals.py --results-root results/study_batch --only bridge
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from smoke_plume_pipeline import run  # noqa: E402


def _resolve_input(p: str) -> Path:
    path = Path(p)
    if path.is_file():
        return path.resolve()
    alt = (REPO_ROOT / path).resolve()
    if alt.is_file():
        return alt
    return path.resolve()


def _run_case(case_dir: Path) -> None:
    summary_path = case_dir / "pipeline_summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"Missing {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    inputs = summary.get("inputs") or {}
    planet = _resolve_input(inputs["planet"])
    tempo = _resolve_input(inputs["tempo"])
    par = summary.get("parameters") or {}
    bands = par.get("bands") or {}
    tm = summary.get("time_match")
    if tm is not None and not isinstance(tm, dict):
        tm = None

    run(
        planet,
        tempo,
        case_dir.resolve(),
        str(par.get("vcd_units", "molec_cm2")),
        float(par.get("blue_nir_max", 0.42)),
        float(par.get("fp_background_max", 0.02)),
        True,
        int(bands.get("blue", 2)),
        int(bands.get("nir", 8)),
        int(par.get("tempo_vcd_band", 1)),
        mask_method=str(par.get("mask_method", "blue_nir")),
        band_green=int(bands.get("green", 3)),
        ndhi_smoke_below=float(par.get("ndhi_smoke_below", 0.0)),
        ndhi_bnir_smoke_above=float(par.get("ndhi_bnir_smoke_above", -0.15)),
        mask_nodata=float(par.get("mask_nodata", -9999.0)),
        time_match=tm,
    )

    check = REPO_ROOT / "scripts" / "smoke_plume_sanity_check.py"
    subprocess.run(
        [sys.executable, str(check), "--results-dir", str(case_dir.resolve())],
        cwd=str(REPO_ROOT),
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="GeoTIFF maps + PNG previews for study_batch cases.")
    ap.add_argument(
        "--results-root",
        type=Path,
        default=REPO_ROOT / "results/study_batch",
        help="Folder containing per-case subdirs (e.g. airport, bridge, …).",
    )
    ap.add_argument(
        "--only",
        nargs="*",
        metavar="CASE_ID",
        help="If set, only these case folder names (e.g. palisades bridge).",
    )
    args = ap.parse_args()
    root = args.results_root.resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        sys.exit(1)

    allow = {x.strip() for x in (args.only or []) if x.strip()}
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        if sub.name.startswith("."):
            continue
        if allow and sub.name not in allow:
            continue
        if not (sub / "pipeline_summary.json").is_file():
            continue
        print(f"\n=== {sub.name} ===", flush=True)
        _run_case(sub)

    print(f"\nDone. PNG previews under each case: <case>/maps/*.png", flush=True)


if __name__ == "__main__":
    main()
