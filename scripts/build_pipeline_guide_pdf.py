"""
Build a single HTML document and optional PDF from:
  docs/pipeline_layman_guide.md
  + full appendix: docs/pipeline_tuning_parameters.md

Uses Pandoc (required). PDF via:
  - Google Chrome / Chromium --headless --print-to-pdf (default if found), or
  - Pandoc LaTeX engine if --pdf-engine is installed (e.g. pdflatex, typst).

Run from repo root:
  py -3 scripts/build_pipeline_guide_pdf.py

Outputs (by default):
  docs/pipeline_layman_guide.html
  docs/pipeline_layman_guide.pdf   (if Chrome/Chromium or PDF engine available)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
GUIDE = DOCS / "pipeline_layman_guide.md"
TUNING = DOCS / "pipeline_tuning_parameters.md"
OUT_HTML = DOCS / "pipeline_layman_guide.html"
OUT_PDF = DOCS / "pipeline_layman_guide.pdf"
CSS = DOCS / "pipeline_guide_print.css"


def _find_chrome() -> Path | None:
    which = [
        shutil.which("chrome"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    candidates = [Path(w) for w in which if w]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _combine_markdown() -> str:
    main = GUIDE.read_text(encoding="utf-8")
    tuning = TUNING.read_text(encoding="utf-8")
    lines = tuning.splitlines()
    if lines and lines[0].lstrip().startswith("# "):
        # Drop duplicate top-level title; appendix uses its own heading.
        tuning_body = "\n".join(lines[1:]).lstrip()
    else:
        tuning_body = tuning
    return (
        main.rstrip()
        + "\n\n---\n\n"
        + "# Appendix — Pipeline tuning parameters (full reference)\n\n"
        + "*This appendix is the same content as "
        + "`docs/pipeline_tuning_parameters.md` (end-to-end knobs).*\n\n"
        + tuning_body
        + "\n"
    )


def _run_pandoc_html(src: Path, out_html: Path) -> None:
    css_arg: list[str] = []
    if CSS.is_file():
        css_arg = [f"--css={CSS.relative_to(REPO_ROOT).as_posix()}"]
    cmd = [
        "pandoc",
        str(src),
        "-o",
        str(out_html),
        "--standalone",
        "--resource-path",
        str(DOCS),
        "-M",
        "title=Smoke plume NO₂ pipeline — guide and tuning reference",
        *css_arg,
    ]
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)


def _run_pandoc_pdf_engine(src: Path, out_pdf: Path, engine: str) -> None:
    cmd = [
        "pandoc",
        str(src),
        "-o",
        str(out_pdf),
        "--resource-path",
        str(DOCS),
        f"--pdf-engine={engine}",
        "-V",
        "geometry:margin=1in",
    ]
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)


def _chrome_print_pdf(html: Path, pdf: Path, chrome: Path) -> None:
    uri = html.resolve().as_uri()
    cmd = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf.resolve()}",
        uri,
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build combined HTML/PDF for the pipeline layman guide + tuning doc.")
    ap.add_argument(
        "--pdf-engine",
        metavar="ENGINE",
        help="Pandoc PDF engine to try after Chrome (e.g. pdflatex, xelatex, typst). Implies attempting Pandoc PDF.",
    )
    ap.add_argument("--html-only", action="store_true", help="Write HTML only; do not create PDF.")
    ap.add_argument(
        "--no-chrome",
        action="store_true",
        help="Do not use Chrome headless for PDF (use --pdf-engine or skip PDF).",
    )
    args = ap.parse_args()

    if not GUIDE.is_file():
        print(f"Missing {GUIDE}", file=sys.stderr)
        return 1
    if not TUNING.is_file():
        print(f"Missing {TUNING}", file=sys.stderr)
        return 1
    if shutil.which("pandoc") is None:
        print("pandoc not found on PATH. Install from https://pandoc.org/installing.html", file=sys.stderr)
        return 1

    combined = _combine_markdown()
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".md",
        delete=False,
        dir=str(DOCS),
    ) as tmp:
        tmp.write(combined)
        tmp_path = Path(tmp.name)

    try:
        _run_pandoc_html(tmp_path, OUT_HTML)
        print(f"Wrote {OUT_HTML.relative_to(REPO_ROOT)}")
    finally:
        tmp_path.unlink(missing_ok=True)

    if args.html_only:
        print("Done (--html-only). Open the HTML in a browser and use Print → Save as PDF if needed.")
        return 0

    pdf_ok = False
    if not args.no_chrome:
        chrome = _find_chrome()
        if chrome:
            try:
                _chrome_print_pdf(OUT_HTML, OUT_PDF, chrome)
                print(f"Wrote {OUT_PDF.relative_to(REPO_ROOT)} (Chrome headless)")
                pdf_ok = True
            except (subprocess.CalledProcessError, OSError) as e:
                print(f"Chrome PDF failed ({e}); trying other methods.", file=sys.stderr)

    if not pdf_ok and args.pdf_engine:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".md",
            delete=False,
            dir=str(DOCS),
        ) as tmp2:
            tmp2.write(combined)
            tmp2_path = Path(tmp2.name)
        try:
            _run_pandoc_pdf_engine(tmp2_path, OUT_PDF, args.pdf_engine)
            print(f"Wrote {OUT_PDF.relative_to(REPO_ROOT)} (pandoc --pdf-engine={args.pdf_engine})")
            pdf_ok = True
        except subprocess.CalledProcessError as e:
            print(f"Pandoc PDF failed: {e}", file=sys.stderr)
        finally:
            tmp2_path.unlink(missing_ok=True)

    if not pdf_ok:
        print(
            "No PDF written. Install a LaTeX engine (e.g. MiKTeX) and run with "
            "`--pdf-engine=pdflatex`, or open the generated HTML and print to PDF.",
            file=sys.stderr,
        )
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
