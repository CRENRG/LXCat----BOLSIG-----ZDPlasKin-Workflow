import argparse
from pathlib import Path

import numpy as np
import pandas as pd


KB_J_PER_K = 1.380649e-23
TORR_TO_PA = 133.322368
DEMO_LABEL = "demo output until executable paths are configured"


def _pressure_to_density_m3(pressure_torr, gas_temperature_k):
    return float(pressure_torr) * TORR_TO_PA / (KB_J_PER_K * float(gas_temperature_k))


def _rate_scale(rates):
    if rates is None:
        return 1.0
    try:
        if isinstance(rates, pd.DataFrame) and not rates.empty:
            values = rates.select_dtypes(include=["number"]).to_numpy().ravel()
        else:
            values = np.array([row.get("k", row.get("rate_coefficient_m3_s", 0.0)) for row in rates], dtype=float)
        values = values[np.isfinite(values) & (values > 0)]
        if values.size == 0:
            return 1.0
        return float(np.clip(np.log10(values.max() / 1e-17 + 1.0), 0.7, 2.5))
    except Exception:
        return 1.0


def generate_demo_species_density(
    rates=None,
    gas_temperature_k=300.0,
    pressure_torr=5.0,
    time_start_s=1e-9,
    time_end_s=1e-3,
    points=260,
):
    neutral_density = _pressure_to_density_m3(pressure_torr, gas_temperature_k)
    scale = _rate_scale(rates)
    time_s = np.logspace(np.log10(time_start_s), np.log10(time_end_s), points)
    normalized_time = (np.log10(time_s) - np.log10(time_start_s)) / (np.log10(time_end_s) - np.log10(time_start_s))

    ignition = 1.0 / (1.0 + np.exp(-12.0 * (normalized_time - 0.42)))
    late_loss = np.exp(-0.25 * normalized_time)
    dissociation = 0.06 * ignition * scale / 1.8

    e_density = 5.0e13 + 7.5e15 * ignition * late_loss * scale
    d2_density = neutral_density * np.maximum(0.88, 1.0 - dissociation)
    d_density = neutral_density * (0.006 + 0.035 * ignition * scale / 1.8)
    d2_plus_density = 2.0e13 + 1.8e15 * ignition * np.exp(-0.12 * normalized_time) * scale
    d_plus_density = 8.0e12 + 7.5e14 * ignition**1.2 * scale
    d3_plus_density = 4.0e12 + 5.5e14 * ignition * (1.0 - np.exp(-4.0 * normalized_time)) * scale

    return pd.DataFrame(
        {
            "time_s": time_s,
            "e": e_density,
            "D2": d2_density,
            "D": d_density,
            "D+": d_plus_density,
            "D2+": d2_plus_density,
            "D3+": d3_plus_density,
            "source": DEMO_LABEL,
        }
    )


def save_demo_zdplaskin_outputs(species_df, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "demo_species_density.csv"
    species_df.to_csv(path, index=False)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate clearly labeled demo ZDPlasKin species-density output.")
    parser.add_argument("--output-dir", default="data/zdplaskin_outputs", help="Directory for demo CSV files")
    parser.add_argument("--pressure-torr", type=float, default=5.0)
    parser.add_argument("--gas-temperature-k", type=float, default=300.0)
    args = parser.parse_args()
    demo_df = generate_demo_species_density(
        gas_temperature_k=args.gas_temperature_k,
        pressure_torr=args.pressure_torr,
    )
    print(save_demo_zdplaskin_outputs(demo_df, args.output_dir))
