## Step 4 — Isolate plume NO₂ enhancement (background + excess)

### Script

`scripts/smoke_plume_pipeline.py` (same run as mass; Step 4 is the **background subtraction + plume weighting** block).

### Methodology mapping

| Concept | Implementation |
|--------|------------------|
| Background \(VCD_{bg}\) | **Median** of tropospheric VCD over TEMPO pixels with **low plume overlap**: \(f_p \le\) `--fp-bg-max` (default **0.02**). If too few pixels: relax \(f_p\) slightly; if still too few: **15th percentile** of valid VCD. |
| Excess column | \(\Delta VCD = VCD - VCD_{bg}\) on each valid TEMPO pixel. |
| Plume-attributed excess | \(\Delta VCD_{plume} = f_p \times \Delta VCD\) (same \(f_p\) as Step 2). |

This is a **practical** background (clean-ish footprint in the scene), not a separate hand-drawn upwind polygon. For strict “upwind only,” you would replace `bg_sel` with a geographic mask (future work).

### Outputs

Run:

```text
python scripts/smoke_plume_pipeline.py --out results/step_04_plume_enhancement --write-maps
```

Writes:

| File | Content |
|------|---------|
| `pipeline_summary.json` | `vcd_background_median`, `total_excess_no2_kg`, parameters |
| `pipeline_table.csv` | Same quantities for spreadsheets |
| `f_p.tif` | Sub-pixel smoke fraction on TEMPO grid |
| `delta_vcd.tif` | \(\Delta VCD = VCD - VCD_{bg}\) (full swath grid) |
| `delta_vcd_plume.tif` | \(f_p \times \Delta VCD\) (plume-weighted excess column) |

Mass in the summary uses **`delta_vcd_plume` × pixel area** (see Step 5 in `PROJECT.md`).

### QGIS

Load **`delta_vcd.tif`** to see regional enhancement; load **`delta_vcd_plume.tif`** to see what enters the mass integral.
