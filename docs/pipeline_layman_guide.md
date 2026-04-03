# Smoke plume NO₂ pipeline — a plain-English guide

This page explains **what the code is doing** and **why**, without assuming you speak remote-sensing jargon. For math and symbols, see [PROJECT.md](../PROJECT.md). For knob-by-knob tuning, see [pipeline_tuning_parameters.md](pipeline_tuning_parameters.md).

---

## The one-sentence version

We combine a **sharp photo of smoke** (Planet) with a **coarse map of air pollution** (TEMPO NO₂) to estimate how much **extra nitrogen dioxide** is sitting in the plume—stated as a **mass in kilograms**—after subtracting a “normal clean air” level.

---

## Two satellites, two jobs

| | **Planet (PlanetScope)** | **TEMPO** (NASA, geostationary) |
|---|---------------------------|----------------------------------|
| **What it’s good at** | Seeing **where smoke is** on the ground (meters-scale). | Measuring **NO₂ in the column of air** above the ground (kilometers-scale “pixels”). |
| **Analogy** | A detailed **photo** of the smoke plume. | A **low-resolution weather-style grid** of pollution over a huge area. |
| **Catch** | Planet doesn’t directly give you “kg of NO₂.” | TEMPO doesn’t see smoke shape at fence-line detail. |

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

![Cartoon: fine Planet grid vs coarse TEMPO grid](images/schematic_fine_vs_coarse.png)

If **f_p = 0**, that TEMPO pixel has essentially **no smoke** in it (according to Planet). If **f_p = 0.3**, roughly **30%** of that cell “looks like smoke” at Planet resolution.

### Step 4 — Subtract “normal” NO₂ (**background**)

The atmosphere always has some NO₂ (cities, chemistry, etc.). We estimate a **background** column using TEMPO pixels that are **clean in the Planet sense** (low **f_p**). Then:

**excess column ≈ total column − background**

So we focus on **extra** NO₂, not the absolute number on a smoggy day.

![Cartoon: background subtraction](images/schematic_background_subtraction.png)

### Step 5 — Combine and add up to **kilograms**

For each TEMPO pixel we combine:

**plume-weighted excess ≈ f_p × (excess NO₂ column)**

Then we **multiply by the geographic size** of each TEMPO pixel and sum over the grid. Unit conversions turn **molecules per cm²** into **kilograms of NO₂**—that’s the **total excess NO₂ (kg)** in `pipeline_summary.json`.

![Cartoon: boxes in a row](images/schematic_pipeline_strip.png)

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

## Where this lives in your repo (outputs)

After you run the pipeline (and optionally map exports), each case folder has:

| File | Plain English |
|------|----------------|
| `pipeline_summary.json` | Numbers: background, pixel counts, **total kg**. |
| `pipeline_table.csv` | Same headline numbers in a tiny table. |
| `f_p.tif` | Map of **overlap fractions** on the TEMPO grid. |
| `delta_vcd.tif` | Map of **excess column** before smoke weighting. |
| `delta_vcd_plume.tif` | Map of **f_p × excess** (what gets integrated to mass). |

Preview PNGs (from `smoke_plume_sanity_check.py` / `study_batch_visuals.py`) live under `maps/`:

- **`f_p_preview.png`** — quick look at where the plume overlaps TEMPO (cropped).
- **`delta_vcd_plume_preview.png`** — where the **weighted** excess is strongest (cropped).
- **`histograms.png`** — how **f_p** and plume ΔVCD are distributed.

> **Note:** Large rasters and PNGs under `results/` are usually **gitignored**. Generate them locally with `scripts/study_batch_visuals.py` (see [STUDY_BATCH_RESULTS.md](../results/study_batch/STUDY_BATCH_RESULTS.md)).

---

## Example: Palisades previews (open these files on your machine)

If you have run the batch visuals step, you can open:

- `results/study_batch/palisades/maps/f_p_preview.png`
- `results/study_batch/palisades/maps/delta_vcd_plume_preview.png`
- `results/study_batch/palisades/maps/histograms.png`

Other regions (`airport`, `bridge`, `eaton`, `line`, `park`) have the **same file names** under their own folders.

---

## What the numbers do *not* automatically mean

- **Not a legal emissions inventory.** The mask is heuristic; the domain is often a **whole TEMPO swath**, not a tiny fire perimeter unless you clip.
- **Not “only the fire.”** Any smoke-like pixel **anywhere** in the grid contributes.
- **Cross-fire comparisons are delicate.** Different dates, granules, and scene sizes change the story.

---

## Glossary (quick)

| Term | Meaning |
|------|---------|
| **VCD (vertical column density)** | Total NO₂ integrated through the air column above a spot, reported per unit ground area (e.g. molecules per cm²). |
| **f_p** | Fraction of a **TEMPO** pixel that Planet-classified as smoke (0–1). |
| **Background** | Typical “clean-ish” column estimated from **low-f_p** TEMPO pixels. |
| **ΔVCD / excess column** | Column minus background. |
| **Surface reflectance (SR)** | Planet product where lighting is partly normalized so spectra are comparable—use **SR** for the mask unless you know what you’re doing. |

---

## Commands (if you want to reproduce visuals)

```powershell
# Regenerate GeoTIFF maps + PNG previews for every study case
py -3 scripts/study_batch_visuals.py --results-root results/study_batch

# Rebuild only the small schematic images in this guide
py -3 scripts/render_pipeline_guide_assets.py
```

---

## Where to go next

| Goal | Document |
|------|----------|
| Deeper methodology + pilot metadata | [PROJECT.md](../PROJECT.md) |
| Lab notebook style, step checkpoints | [results/walkthrough.md](../results/walkthrough.md) |
| Mask pitfalls and naming | [smoke_mask_challenges.md](smoke_mask_challenges.md) |
| CLI parameters explained | [pipeline_tuning_parameters.md](pipeline_tuning_parameters.md) |
| Batch study table + visual paths | [STUDY_BATCH_RESULTS.md](../results/study_batch/STUDY_BATCH_RESULTS.md) |
