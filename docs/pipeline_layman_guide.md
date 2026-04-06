# Smoke plume NO₂ pipeline — a plain-English guide

This page explains **what the code is doing** and **why**, without assuming you speak remote-sensing jargon. **Figures below are stored under `[docs/images/](images/)`** (committed in git) so they show in GitHub, VS Code / Cursor Markdown Preview, and other renderers—open this file from the repo so relative image paths resolve.

For math and symbols, see [PROJECT.md](../PROJECT.md). **Every tunable knob** (CLI flags and defaults across the pipeline scripts) lives in [pipeline_tuning_parameters.md](pipeline_tuning_parameters.md). A **single PDF or HTML** that merges this guide with that full tuning reference is built by `[scripts/build_pipeline_guide_pdf.py](../scripts/build_pipeline_guide_pdf.py)` (outputs `docs/pipeline_layman_guide.pdf` and `docs/pipeline_layman_guide.html`).

---

## The one-sentence version

We combine a **sharp photo of smoke** (Planet) with a **coarse map of air pollution** (TEMPO NO₂) to estimate how much **extra nitrogen dioxide** is sitting in the plume—stated as a **mass in kilograms**—after subtracting a “normal clean air” level.

---

## Two satellites, two jobs


|                       | **Planet (PlanetScope)**                                | **TEMPO** (NASA, geostationary)                                                      |
| --------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **What it’s good at** | Seeing **where smoke is** on the ground (meters-scale). | Measuring **NO₂ in the column of air** above the ground (kilometers-scale “pixels”). |
| **Analogy**           | A detailed **photo** of the smoke plume.                | A **low-resolution weather-style grid** of pollution over a huge area.               |
| **Catch**             | Planet doesn’t directly give you “kg of NO₂.”           | TEMPO doesn’t see smoke shape at fence-line detail.                                  |


The pipeline’s trick is to **merge** them: use Planet to say *how much of each big TEMPO pixel is covered by smoke*, then weight the NO₂ signal accordingly.

---

## The story in five steps (ELI5)

### Step 1 — Line up the moment in time

Wildfires move. Satellites pass at different times. We pick a Planet scene and a TEMPO granule that are **close in time** so we’re not comparing lunch to dinner. Your `case.json` can record those times under `time_match` (see [PROJECT.md](../PROJECT.md)).

### Step 2 — Paint “smoke” on the Planet image

The computer doesn’t “see” smoke the way humans do. It uses **simple spectral rules** on surface reflectance—for example, a **blue vs near-infrared** test— to mark pixels that look like smoke. That produces a **mask**: each Planet pixel is “smoke” or “not smoke” (with invalid areas masked out).

*Nothing here is perfect:* thin cloud, haze, bright dirt, and real smoke can get confused. That’s why there are tuning docs like [smoke_mask_challenges.md](smoke_mask_challenges.md).

### Step 3 — Pour the fine mask into big TEMPO “bins” (**f_p**)

Imagine pouring sand through a sieve:

- Planet pixels are **tiny**.
- TEMPO pixels are **huge**.

For each big TEMPO cell, we ask: *of the tiny Planet pixels inside, what fraction looked like smoke?* That fraction is called **f_p** (overlap fraction). It’s always between **0** and **1**.

If **f_p = 0**, that TEMPO pixel has essentially **no smoke** in it (according to Planet). If **f_p = 0.3**, roughly **30%** of that cell “looks like smoke” at Planet resolution.

Schematic: fine Planet grid averaged into coarse TEMPO cells (f_p)

*Figure: same idea at two scales—the fine “smoke” map is averaged into each big TEMPO pixel to get **f_p**.*

![](images/schematic_fine_vs_coarse.png)

### Step 4 — Subtract “normal” NO₂ (**background**)

The atmosphere always has some NO₂ (cities, chemistry, etc.). We estimate a **background** column using TEMPO pixels that are **clean in the Planet sense** (low **f_p**). Then:

**excess column ≈ total column − background**

So we focus on **extra** NO₂, not the absolute number on a smoggy day.

Schematic: total column, background, and excess

*Figure: we only keep the **excess** above a background estimated from low-**f_p** pixels.*

![](images/schematic_background_subtraction.png)

### Step 5 — Combine and add up to **kilograms**

For each TEMPO pixel we combine:

**plume-weighted excess ≈ f_p × (excess NO₂ column)**

Then we **multiply by the geographic size** of each TEMPO pixel and sum over the grid. Unit conversions turn **molecules per cm²** into **kilograms of NO₂**—that’s the **total excess NO₂ (kg)** in `pipeline_summary.json`.

Schematic: f_p, excess column, and integration to kg

*Figure: multiply overlap by excess column, then sum over the grid with pixel area to get **kg**.*

![](images/schematic_pipeline_strip.png)

---

## Flowchart (technical but readable)

```mermaid
flowchart LR
  P[Planet SR GeoTIFF] --> M[Smoke mask on Planet grid]
  T[TEMPO VCD GeoTIFF] --> B[Background VCD from low f_p pixels]
  M --> F[f_p: warp mask to TEMPO grid]
  T --> D[Delta VCD = VCD - VCD_bg]
  F --> X[f_p × Delta VCD per pixel]
  D --> X
  X --> S[Sum × pixel area → kg NO₂]
```



---

## Six case studies — same pipeline, six real fires

You have **six folders** under `smoke-plume-data/` (airport, bridge, eaton, line, palisades, park). Think of them as **six homework problems with the same instructions**: same mask recipe, same background rule, same mass recipe—but **different days, fires, scenes, and TEMPO granules**.

### The mental model (so it “sticks”)


| Layer         | Plain English                                                           | What varies across the six                                                                             |
| ------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Planet**    | “Where does it *look* smoky at fine scale?”                             | Scene extent, sun angle, haze, terrain—mask is never identical.                                        |
| **TEMPO**     | “How much NO₂ is in the air column above each big pixel?”               | Chemistry, transport, granule time, and **how huge the warped grid is**.                               |
| **f_p**       | “When we pour Planet into TEMPO, how smoky is each big pixel?”          | Same math; different overlap patterns.                                                                 |
| **Mass (kg)** | Sum of **f_p × excess column × pixel area** over the **whole GeoTIFF**. | **Not** “tons from the fire engine”—it’s **integrated over the entire raster domain** unless you clip. |


So: treat this as *one consistent measurement machine pointed at six different worlds*, not six guaranteed-comparable “fire scores.”

### Numbers for all six (one batch, same defaults)

These match the study batch documented in [STUDY_BATCH_RESULTS.md](../results/study_batch/STUDY_BATCH_RESULTS.md).


| Region    | Total enhancement NO₂ (kg) | “Smoky” TEMPO pixels (f_p > 0.01) | TEMPO grid (pixels) | VCD background median (molec/cm²) |
| --------- | --------------------- | --------------------------------- | ------------------- | --------------------------------- |
| airport   | ~789                  | 470                               | ~1,066              | ~4.9 × 10¹⁵                       |
| bridge    | ~1,509                | 536                               | ~912                | ~7.4 × 10¹⁵                       |
| eaton     | ~496                  | 840                               | ~1,470              | ~9.2 × 10¹⁵                       |
| line      | ~1,239                | 433                               | ~1,170              | ~7.0 × 10¹⁵                       |
| palisades | ~380                  | 901                               | ~1,440              | ~4.3 × 10¹⁵                       |
| park      | ~1,176                | 662                               | ~1,008              | ~1.1 × 10¹⁵                       |


**Notice:** In the current pipeline, TEMPO is **subset to the Planet scene bounds**, so the “TEMPO grid” in this table is a **small window** of the full warped TEMPO GeoTIFF. Mass always runs over **whatever pixels exist in that window**.

### Cross-region comparison plots (from the batch summaries)

These charts are built by `scripts/render_case_study_comparison.py` and saved next to this guide as PNGs. They help you compare regions **without** treating the table as a simple leaderboard.

**1 — Total kg, plume-pixel count, and grid size**

![](images/case_study_six_way_bars.png)

**2 — Mass vs. count of “plume-ish” pixels**

If high mass always came from “more plume pixels,” points would hug a neat line. They don’t—**a few pixels with huge excess column** can rival **many pixels with modest excess**.

![](images/case_study_mass_vs_plume_scatter.png)

**3 — Rough “kg per plume-ish pixel” (ranked)**

This is **not** a physical emission factor—it’s a **cartoon ratio** for intuition (Palisades often stands out when **few** cells carry **most** of the signal).

![](images/case_study_kg_per_plume_pixel.png)

### Case-by-case maps (cropped previews)

For **each** study region, the pipeline exports **cropped** PNGs next to the plume: **f_p** (how smoky each big TEMPO cell is) and **f_p × ΔNO₂** (plume-weighted excess). Below that, **histograms** show how **f_p** and plume ΔNO₂ are distributed when **f_p > 0.01**. These copies live under `[docs/images/cases/](images/cases/)` so you can read this guide offline or on GitHub; refresh them after regenerating maps (see [Commands](#commands-if-you-want-to-reproduce-visuals)).

#### Airport


| Plume overlap **f_p** | Plume-weighted excess **f_p × ΔNO₂** |
| --------------------- | ------------------------------------ |
| ![](images/cases/airport_f_p_preview.png) | ![](images/cases/airport_delta_vcd_plume_preview.png) |


![](images/cases/airport_histograms.png)

*~789 kg total enhancement NO₂; 470 coarse pixels with f_p > 0.01 (see table above).*

#### Bridge

**Note:** Bridge needed **Planet surface reflectance (SR)** in `case.json`; the wrong product can drive **f_p** (and mass) to ~0 even when the atmosphere isn’t clean—see [STUDY_BATCH_RESULTS.md](../results/study_batch/STUDY_BATCH_RESULTS.md).


| Plume overlap **f_p** | Plume-weighted excess **f_p × ΔNO₂** |
| --------------------- | ------------------------------------ |
| ![](images/cases/bridge_f_p_preview.png) | ![](images/cases/bridge_delta_vcd_plume_preview.png) |


![](images/cases/bridge_histograms.png)

*~1,509 kg; 536 plume-ish pixels after the SR fix.*

#### Eaton


| Plume overlap **f_p** | Plume-weighted excess **f_p × ΔNO₂** |
| --------------------- | ------------------------------------ |
| ![](images/cases/eaton_f_p_preview.png) | ![](images/cases/eaton_delta_vcd_plume_preview.png) |


![](images/cases/eaton_histograms.png)

*~496 kg; **840** plume-ish pixels (this is enhancement-only; signed anomaly can still be negative).*

#### Line


| Plume overlap **f_p** | Plume-weighted excess **f_p × ΔNO₂** |
| --------------------- | ------------------------------------ |
| ![](images/cases/line_f_p_preview.png) | ![](images/cases/line_delta_vcd_plume_preview.png) |


![](images/cases/line_histograms.png)

*~1,239 kg with **433** plume-ish pixels—**column strength** can outweigh raw pixel count.*

#### Palisades


| Plume overlap **f_p** | Plume-weighted excess **f_p × ΔNO₂** |
| --------------------- | ------------------------------------ |
| ![](images/cases/palisades_f_p_preview.png) | ![](images/cases/palisades_delta_vcd_plume_preview.png) |


![](images/cases/palisades_histograms.png)

*~380 kg with **901** plume-ish pixels (enhancement-only; signed anomaly can still be negative).*

#### Park


| Plume overlap **f_p** | Plume-weighted excess **f_p × ΔNO₂** |
| --------------------- | ------------------------------------ |
| ![](images/cases/park_f_p_preview.png) | ![](images/cases/park_delta_vcd_plume_preview.png) |


![](images/cases/park_histograms.png)

*~1,176 kg; 662 plume-ish pixels.*

### ELI5 contrasts (scientifically honest)

- **Line vs. eaton:** Line can show **higher total kg** with **fewer** “smoky” coarse pixels than eaton—because **column strength** matters as much as **how many** cells pass the f_p threshold.
- **Palisades vs. park:** Total kg can differ in **sign and magnitude** depending on the window and background—this is why it’s important to keep the **domain policy** consistent when comparing cases.
- **Bridge:** After switching to **surface reflectance**, the mask finally “sees” smoke on the TEMPO grid; before that, the pipeline could report **~0** not because the atmosphere was clean, but because **the wrong Planet product** broke the mask.

### Statistical-ish vocabulary in human language

- **Central tendency:** Across these six, totals span **roughly -1.6k to +1.1k kg** in this batch (with the Planet-bounded window policy). That’s a useful “family” for sanity checks, not a universal law.
- **Outlier sensitivity:** One bad asset (wrong Planet type) can move a case from **~0** to **thousands of kg**—always check **inputs** before interpreting **outputs**.
- **Correlation ≠ causation:** Higher kg does **not** mean “worse fire” in any moral or regulatory sense; it means **this integrated model** assigned more plume-weighted excess column **inside that GeoTIFF**.

---

## Where this lives in your repo (outputs)

After you run the pipeline (and optionally map exports), each case folder has:


| File                    | Plain English                                           |
| ----------------------- | ------------------------------------------------------- |
| `pipeline_summary.json` | Numbers: background, pixel counts, **total kg**.        |
| `pipeline_table.csv`    | Same headline numbers in a tiny table.                  |
| `f_p.tif`               | Map of **overlap fractions** on the TEMPO grid.         |
| `delta_vcd.tif`         | Map of **excess column** before smoke weighting.        |
| `delta_vcd_plume.tif`   | Map of **f_p × excess** (what gets integrated to mass). |


Preview PNGs (from `smoke_plume_sanity_check.py` / `study_batch_visuals.py`) live under `maps/`:

- `**f_p_preview.png`** — quick look at where the plume overlaps TEMPO (cropped).
- `**delta_vcd_plume_preview.png**` — where the **weighted** excess is strongest (cropped).
- `**histograms.png`** — how **f_p** and plume ΔVCD are distributed.

Full-resolution GeoTIFFs under `results/` are often **gitignored**. Generate them locally with `scripts/study_batch_visuals.py` (see [STUDY_BATCH_RESULTS.md](../results/study_batch/STUDY_BATCH_RESULTS.md)); use `**scripts/sync_guide_case_images.py`** to refresh the **committed** copies in `docs/images/cases/` for this guide.

---

## What the numbers do *not* automatically mean

- **Not a legal emissions inventory.** The mask is heuristic; and the reported mass depends on the **chosen domain** (in this repo: TEMPO subset to Planet scene bounds, not a fire perimeter).
- **Not “only the fire.”** Any smoke-like pixel **anywhere** in the grid contributes.
- **Cross-fire comparisons are delicate.** Different dates, granules, and scene sizes change the story.

---

## Glossary (quick)


| Term                              | Meaning                                                                                                                                 |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **VCD (vertical column density)** | Total NO₂ integrated through the air column above a spot, reported per unit ground area (e.g. molecules per cm²).                       |
| **f_p**                           | Fraction of a **TEMPO** pixel that Planet-classified as smoke (0–1).                                                                    |
| **Background**                    | Typical “clean-ish” column estimated from **low-f_p** TEMPO pixels.                                                                     |
| **ΔVCD / excess column**          | Column minus background.                                                                                                                |
| **Surface reflectance (SR)**      | Planet product where lighting is partly normalized so spectra are comparable—use **SR** for the mask unless you know what you’re doing. |


---

## Commands (if you want to reproduce visuals)

```powershell
# Regenerate GeoTIFF maps + PNG previews for every study case
py -3 scripts/study_batch_visuals.py --results-root results/study_batch

# Copy map PNGs into docs/images/cases/ for this guide (committed assets)
py -3 scripts/sync_guide_case_images.py

# Rebuild only the small schematic images in this guide
py -3 scripts/render_pipeline_guide_assets.py

# Rebuild the six-case comparison bar/scatter figures (reads pipeline_summary.json when present)
py -3 scripts/render_case_study_comparison.py

# Combined HTML + PDF: this guide + full pipeline_tuning_parameters.md appendix (needs pandoc; PDF via Chrome headless or --pdf-engine)
py -3 scripts/build_pipeline_guide_pdf.py
```

---

## Where to go next


| Goal                                 | Document                                                                |
| ------------------------------------ | ----------------------------------------------------------------------- |
| Deeper methodology + pilot metadata  | [PROJECT.md](../PROJECT.md)                                             |
| Lab notebook style, step checkpoints | [results/walkthrough.md](../results/walkthrough.md)                     |
| Mask pitfalls and naming             | [smoke_mask_challenges.md](smoke_mask_challenges.md)                    |
| CLI parameters explained             | [pipeline_tuning_parameters.md](pipeline_tuning_parameters.md)          |
| Batch study table + visual paths     | [STUDY_BATCH_RESULTS.md](../results/study_batch/STUDY_BATCH_RESULTS.md) |


