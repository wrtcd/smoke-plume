"""
Tropospheric NO2 VCD scaling from an assumed plume height (AMF perturbation).

Uses L2 fields: scattering_weights (vertical sensitivity), gas_profile (retrieval prior shape),
amf_troposphere, surface_pressure. Layer pressures are built from surface pressure to a fixed top
(see layer_pressure_centers_hpa); height AGL per layer uses an isothermal scale height (approximate).

VCD_adj = VCD * (AMF_trop / AMF_adj),  AMF_adj = AMF_trop * R,
R = (sum_l SW_l * w_l) / (sum_l SW_l * a_prior_l),  a_prior = gas / sum(gas).

w_l: Gaussian in height AGL (m) centered at plume_height_agl_m (e.g. 1000 for 1 km per boss note).

Validate sensitivities against the TEMPO ATBD for production use.
"""

from __future__ import annotations

import numpy as np

FILL = -1e30

# Isothermal atmosphere scale height for z = H * ln(Psurf/P) (approximate; ~8.4 km at 288 K)
R_D = 287.05
G = 9.80665
T_REF = 288.0
SCALE_HEIGHT_M = R_D * T_REF / G


def _finite_swath(x: np.ndarray) -> np.ndarray:
    return np.isfinite(x) & (x > FILL / 10) & (x < 1e35)


def layer_pressure_centers_hpa(surface_pressure_hpa: np.ndarray, n_levels: int, p_top_hpa: float = 1.0) -> np.ndarray:
    """P[k] from surface to p_top; index 0 near surface (matches warmest T level in sample granules)."""
    ps = np.maximum(surface_pressure_hpa, 300.0)
    r = np.clip(p_top_hpa / ps, 1e-9, 1.0)
    k = np.arange(n_levels, dtype=np.float64)
    denom = max(n_levels - 1, 1)
    frac = r[..., np.newaxis] ** (k / denom)
    return ps[..., np.newaxis] * frac


def height_agl_m_above_surface_pressure(pressure_hpa: np.ndarray, surface_pressure_hpa: np.ndarray) -> np.ndarray:
    """Approximate height (m) above surface for each layer pressure."""
    ps = np.maximum(surface_pressure_hpa[..., np.newaxis], 1.0)
    p = np.maximum(pressure_hpa, 0.01)
    return SCALE_HEIGHT_M * np.log(ps / p)


def plume_weights_height(
    z_agl_m: np.ndarray,
    plume_height_agl_m: float,
    plume_fwhm_m: float,
) -> np.ndarray:
    """Gaussian in height; normalized to sum 1 along last axis."""
    sigma = plume_fwhm_m / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    sigma = max(sigma, 50.0)
    d = z_agl_m - plume_height_agl_m
    w = np.exp(-0.5 * (d / sigma) ** 2)
    s = np.sum(w, axis=-1, keepdims=True)
    s = np.maximum(s, 1e-30)
    return w / s


def prior_shape_normalized(gas_profile: np.ndarray) -> np.ndarray:
    g = np.where(_finite_swath(gas_profile), gas_profile, 0.0)
    s = np.sum(g, axis=-1, keepdims=True)
    s = np.maximum(s, 1e-30)
    return g / s


def adjust_troposphere_vcd(
    vertical_column_troposphere: np.ndarray,
    amf_troposphere: np.ndarray,
    scattering_weights: np.ndarray,
    gas_profile: np.ndarray,
    surface_pressure_hpa: np.ndarray,
    *,
    plume_height_agl_m: float,
    plume_fwhm_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (vcd_adjusted, amf_adjusted, valid_mask_2d).
    """
    sw = np.where(_finite_swath(scattering_weights), scattering_weights, 0.0)
    ap = prior_shape_normalized(gas_profile)
    nlev = sw.shape[-1]
    p_lev = layer_pressure_centers_hpa(surface_pressure_hpa, nlev)
    z_agl = height_agl_m_above_surface_pressure(p_lev, surface_pressure_hpa)
    w = plume_weights_height(z_agl, plume_height_agl_m, plume_fwhm_m)

    sum_sw_ap = np.sum(sw * ap, axis=-1)
    sum_sw_w = np.sum(sw * w, axis=-1)
    amf = np.where(_finite_swath(amf_troposphere), amf_troposphere, np.nan)

    ok = (sum_sw_ap > 1e-30) & (sum_sw_w > 1e-30) & np.isfinite(amf) & (amf > 1e-6)
    ratio = np.ones_like(sum_sw_ap, dtype=np.float64)
    np.divide(sum_sw_w, sum_sw_ap, out=ratio, where=ok)

    amf_adj = np.where(ok, amf * ratio, amf)
    vcd = np.where(_finite_swath(vertical_column_troposphere), vertical_column_troposphere, np.nan)
    vcd_adj = np.where(ok & np.isfinite(vcd), vcd * (amf / np.maximum(amf_adj, 1e-30)), vcd)

    valid = ok & np.isfinite(vcd)
    return vcd_adj.astype(np.float64), amf_adj.astype(np.float64), valid
