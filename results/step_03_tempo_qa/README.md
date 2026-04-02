## Step 3 — TEMPO QA + AMF + optional plume AMF adjustment

### Script

`scripts/tempo_l2_to_4326.py`  
`scripts/tempo_amf_plume_adjust.py` (adjustment math)

### VCD masking (on the swath, after optional AMF adjustment)

- **`main_data_quality_flag`**: by default, pixels with **flag != 0** → NaN. **`--no-qa`** disables.
- **`eff_cloud_fraction`**: **`--max-cloud F`** masks where **eff_cloud_fraction > F**.
- **`ground_pixel_quality_flag`**: **`--ground-qa-zero`** — verify ATBD before using.

### Optional plume AMF adjustment (`--amf-plume-adjust`)

Uses L2 **`scattering_weights`** (vertical sensitivity), **`gas_profile`** (prior NO₂ shape, normalized per pixel), **`amf_troposphere`**, **`surface_pressure`**.

- **Plume shape** \(w\): Gaussian in **height AGL (m)** with center **`--plume-height-agl-m`** (default **1000** ≈ 1 km) and **`--plume-fwhm-m`** (default **500** m vertical spread).
- Layer heights from approximate **isothermal** \(z = H\ln(P_{\mathrm{surf}}/P_{\mathrm{layer}})\), \(H \approx 8.4\) km.
- **\(R = (\sum SW \cdot w) / (\sum SW \cdot a_{\mathrm{prior}})\)**, **\( \mathrm{AMF}_{adj} = \mathrm{AMF}_{trop} \cdot R\)**, **\( \mathrm{VCD}_{adj} = \mathrm{VCD} \cdot (\mathrm{AMF}_{trop}/\mathrm{AMF}_{adj})\)**.

Validate against the TEMPO ATBD for publication-quality work.

### Multi-band GeoTIFF (`--stack`)

| Band | Content |
|------|---------|
| 1 | Tropospheric VCD (adjusted if `--amf-plume-adjust`, then QA/cloud masked) |
| 2 | `amf_troposphere_plume_adjusted` (if adjustment on) |
| 3 | `amf_troposphere` (L2) |
| 4 | `amf_total` |
| 5 | `eff_cloud_fraction` |
| 6 | `main_data_quality_flag` |
| 7 | `ground_pixel_quality_flag` |

Without `--amf-plume-adjust`, bands match the 6-band layout (no band 2 `amf_troposphere_plume_adjusted`).

### Pipeline

`palisades_pipeline.py` reads **band 1** as VCD (`--tempo-vcd-band 1`).

### Example (QA + cloud + stack + 1 km plume AMF)

```text
python scripts/tempo_l2_to_4326.py ^
  --nc data/palisades/tempo/TEMPO_NO2_L2_V03_20250110T184529Z_S008G09.nc ^
  -o data/palisades/tempo/TEMPO_NO2_trop_warped_4326.tif ^
  --max-cloud 0.3 --stack ^
  --amf-plume-adjust --plume-height-agl-m 1000 --plume-fwhm-m 500
```
