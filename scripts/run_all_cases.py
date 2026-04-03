"""
Run smoke_plume_pipeline.run() for every study region under a data folder.

The core pipeline is single-scene; this script loops cases with distinct inputs/output dirs.

Discovery (each case is one subdirectory of --cases-root):

  1) case.json in the subfolder (paths relative to that folder), e.g.:
     {"id": "my_region", "planet": "scene_SR_8b.tif", "tempo": "TEMPO_NO2_trop_warped_4326.tif",
      "time_match": {"tempo_granule_utc": "...", "planet_acquired_utc": "...", "note": "..."}}

  2) Else if planet.tif and tempo.tif exist in the subfolder, use those names.

  3) Optional globs in case.json (single match each):
     "planet_glob": "*_SR_8b.tif", "tempo_glob": "TEMPO*.tif"

Or pass --manifest pointing at a JSON file listing cases (see cases_manifest.example.json).

Run from repo root:
  .\\.venv\\Scripts\\python.exe scripts/run_all_cases.py --cases-root smoke-plume-data --out-root results/study_batch --write-maps
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from smoke_plume_pipeline import run  # noqa: E402


def _resolve_glob(case_dir: Path, pattern: str, label: str) -> Path:
    matches = sorted(case_dir.glob(pattern))
    if len(matches) == 0:
        raise FileNotFoundError(f"{case_dir}: {label} glob {pattern!r} matched no files")
    if len(matches) > 1:
        raise ValueError(
            f"{case_dir}: {label} glob {pattern!r} matched multiple files: "
            + ", ".join(m.name for m in matches[:5])
        )
    return matches[0]


def _load_case_json(case_dir: Path) -> dict[str, Any]:
    path = case_dir / "case.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _paths_from_case_json(case_dir: Path, data: dict[str, Any]) -> tuple[str, Path, Path, dict | None]:
    case_id = str(data.get("id") or case_dir.name)
    tm = data.get("time_match")
    if tm is not None and not isinstance(tm, dict):
        raise ValueError(f"{case_dir}: time_match must be an object or omitted")

    if data.get("planet_glob") or data.get("tempo_glob"):
        pg = data.get("planet_glob") or "*_SR_8b.tif"
        tg = data.get("tempo_glob") or "TEMPO*.tif"
        planet = _resolve_glob(case_dir, pg, "planet")
        tempo = _resolve_glob(case_dir, tg, "tempo")
        return case_id, planet, tempo, tm

    ps = data.get("planet")
    ts = data.get("tempo")
    if not ps or not ts:
        raise ValueError(
            f"{case_dir}: case.json needs planet + tempo paths, or planet_glob + tempo_glob"
        )
    planet = (case_dir / ps).resolve()
    tempo = (case_dir / ts).resolve()
    return case_id, planet, tempo, tm


def discover_cases_from_root(cases_root: Path) -> list[tuple[str, Path, Path, dict | None]]:
    if not cases_root.is_dir():
        raise FileNotFoundError(f"Not a directory: {cases_root}")
    out: list[tuple[str, Path, Path, dict | None]] = []
    for sub in sorted(cases_root.iterdir()):
        if not sub.is_dir():
            continue
        case_json = sub / "case.json"
        if case_json.is_file():
            data = _load_case_json(sub)
            out.append(_paths_from_case_json(sub, data))
            continue
        p = sub / "planet.tif"
        t = sub / "tempo.tif"
        if p.is_file() and t.is_file():
            out.append((sub.name, p.resolve(), t.resolve(), None))
    return out


def load_cases_from_manifest(manifest_path: Path) -> list[tuple[str, Path, Path, dict | None]]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    if "base_dir" in raw:
        base = (base / raw["base_dir"]).resolve()
    cases = raw.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Manifest must contain a 'cases' array")
    out: list[tuple[str, Path, Path, dict | None]] = []
    for c in cases:
        if not isinstance(c, dict):
            raise ValueError("Each case must be an object")
        cid = str(c["id"])
        tm = c.get("time_match")
        if tm is not None and not isinstance(tm, dict):
            raise ValueError(f"Case {cid}: time_match must be object or omitted")
        if c.get("planet_glob") or c.get("tempo_glob"):
            cdir = (base / cid).resolve() if (base / cid).is_dir() else base
            pg = c.get("planet_glob") or "*_SR_8b.tif"
            tg = c.get("tempo_glob") or "TEMPO*.tif"
            planet = _resolve_glob(cdir, pg, "planet")
            tempo = _resolve_glob(cdir, tg, "tempo")
            out.append((cid, planet, tempo, tm))
            continue
        planet = Path(c["planet"])
        tempo = Path(c["tempo"])
        if not planet.is_absolute():
            planet = (base / planet).resolve()
        if not tempo.is_absolute():
            tempo = (base / tempo).resolve()
        out.append((cid, planet, tempo, tm))
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run smoke-plume pipeline for all cases under a folder or manifest."
    )
    p.add_argument(
        "--cases-root",
        type=Path,
        help="Directory containing one subfolder per region (case.json or planet.tif+tempo.tif).",
    )
    p.add_argument(
        "--manifest",
        type=Path,
        help="JSON manifest of cases (see scripts/cases_manifest.example.json).",
    )
    p.add_argument(
        "--out-root",
        type=Path,
        required=True,
        help="Base output directory; each case writes to out-root/<case_id>/",
    )
    p.add_argument("--dry-run", action="store_true", help="List cases only; do not run pipeline.")
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failed case (default: run all cases and report errors in batch_summary.json).",
    )
    p.add_argument(
        "--vcd-units",
        choices=("molec_cm2", "mol_m2"),
        default="molec_cm2",
    )
    p.add_argument("--blue-nir-max", type=float, default=0.42)
    p.add_argument("--fp-bg-max", type=float, default=0.02)
    p.add_argument("--write-maps", action="store_true")
    p.add_argument("--blue-band", type=int, default=2)
    p.add_argument("--nir-band", type=int, default=8)
    p.add_argument("--green-band", type=int, default=3)
    p.add_argument("--tempo-vcd-band", type=int, default=1)
    p.add_argument(
        "--mask-method",
        choices=("blue_nir", "ndhi", "ndhi_bnir"),
        default="blue_nir",
    )
    p.add_argument("--ndhi-smoke-below", type=float, default=0.0)
    p.add_argument("--ndhi-bnir-smoke-above", type=float, default=-0.15)
    p.add_argument("--mask-nodata", type=float, default=-9999.0)
    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.manifest:
        cases = load_cases_from_manifest(args.manifest.resolve())
    elif args.cases_root:
        cases = discover_cases_from_root(args.cases_root.resolve())
    else:
        print("Provide --cases-root or --manifest.", file=sys.stderr)
        sys.exit(2)

    if not cases:
        print("No cases found. Check folder layout or manifest.", file=sys.stderr)
        sys.exit(1)

    out_root = args.out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    batch_started = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []

    for case_id, planet, tempo, time_match in cases:
        row: dict[str, Any] = {
            "id": case_id,
            "planet": str(planet),
            "tempo": str(tempo),
            "out_dir": str(out_root / case_id),
        }
        case_out = out_root / case_id
        print(f"\n=== Case {case_id} ===", flush=True)
        print(f"  planet: {planet}", flush=True)
        print(f"  tempo:  {tempo}", flush=True)
        print(f"  out:    {case_out}", flush=True)

        if args.dry_run:
            row["status"] = "dry_run"
            results.append(row)
            continue

        try:
            summary = run(
                planet,
                tempo,
                case_out,
                args.vcd_units,
                args.blue_nir_max,
                args.fp_bg_max,
                args.write_maps,
                args.blue_band,
                args.nir_band,
                args.tempo_vcd_band,
                mask_method=args.mask_method,
                band_green=args.green_band,
                ndhi_smoke_below=args.ndhi_smoke_below,
                ndhi_bnir_smoke_above=args.ndhi_bnir_smoke_above,
                mask_nodata=args.mask_nodata,
                time_match=time_match,
            )
            row["status"] = "ok"
            row["total_excess_no2_kg"] = summary.get("total_excess_no2_kg")
            row["vcd_background_median"] = summary.get("vcd_background_median")
        except Exception as e:
            row["status"] = "error"
            row["error"] = f"{type(e).__name__}: {e}"
            row["traceback"] = traceback.format_exc()
            print(row["error"], file=sys.stderr)
            if args.fail_fast:
                results.append(row)
                index = {
                    "started_utc": batch_started,
                    "finished_utc": datetime.now(timezone.utc).isoformat(),
                    "out_root": str(out_root),
                    "cases": results,
                }
                (out_root / "batch_summary.json").write_text(
                    json.dumps(index, indent=2), encoding="utf-8"
                )
                sys.exit(1)
        results.append(row)

    index = {
        "started_utc": batch_started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "out_root": str(out_root),
        "cases": results,
    }
    (out_root / "batch_summary.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\nWrote {out_root / 'batch_summary.json'}", flush=True)

    n_err = sum(1 for r in results if r.get("status") == "error")
    if n_err:
        sys.exit(1)


if __name__ == "__main__":
    main()
