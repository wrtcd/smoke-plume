## Step 5 — Column to mass

### Formula

For **ΔVCD_plume** in **molecules/cm²** (TEMPO L2 tropospheric column scale):

\[
M_{\mathrm{NO_2}} = \frac{1}{N_A} M_{\mathrm{NO_2}} \sum_i \Delta VCD_i \cdot A_i \cdot 10^4
\]

- \(A_i\): pixel area (**m²**) from the GeoTIFF geotransform (latitude-dependent degree spacing).
- Factor **10⁴**: m² → cm² for the column unit.
- \(N_A = 6.02214076 \times 10^{23}\) mol⁻¹, \(M_{\mathrm{NO_2}} = 0.046\) kg/mol.

Same logic as `excess_mass_molec_cm2` in `scripts/palisades_pipeline.py`.

### Script

```text
python scripts/column_to_mass.py
python scripts/column_to_mass.py --raster results/step_04_plume_enhancement/delta_vcd_plume.tif
```

Writes **`results/step_05_mass/column_mass.json`** (override with **`--out-json`**).

### Pipeline

`scripts/palisades_pipeline.py` computes the **same** total as **`total_excess_no2_kg`** in `pipeline_summary.json` when you run the full pipeline; Step 5 here is the **standalone check** from **`delta_vcd_plume.tif`**.

### Relation to `masscal.pdf` (and `PROJECT.md` §5)

The scanned **`masscal.pdf`** “column → mass” worked example is the **same physics** as above: **molecules in column = VCD × area (cm²)**, then **kg = (molecules / *N*ₐ) × 46 g/mol**. That is what Step 5 implements (summed over all plume-weighted pixels). The numeric example in **`PROJECT.md`** (single pixel ≈ 3.4 kg) matches that recipe.

There is **no second mass conversion** hidden in `masscal.pdf` beyond §5 — once you have **kg NO₂**, that step is complete unless you add **optional** follow-ons.

### After mass (`PROJECT.md` §6 — optional)

Not part of Step 5: **emission-style** metrics such as **E ≈ M_total / τ** (NO₂ lifetime τ, order **1–6 h**) or a **flux** through a transect. Those need extra assumptions (τ, winds, geometry). Say if you want a small helper script for **E = M / τ** only.
