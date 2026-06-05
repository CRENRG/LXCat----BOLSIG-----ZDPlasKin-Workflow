import argparse
from pathlib import Path

import numpy as np
import pandas as pd


E_CHARGE_C = 1.602176634e-19
ELECTRON_MASS_KG = 9.1093837015e-31
KB_J_PER_K = 1.380649e-23
TORR_TO_PA = 133.322368
DEMO_LABEL = "demo output until executable paths are configured"


def _trapz(y, x):
    if hasattr(np, "trapezoid"):
        return np.trapezoid(y, x)
    return np.trapz(y, x)


def estimate_mean_energy_eV(reduced_field_td=150.0, gas_temperature_k=300.0, pressure_torr=5.0):
    reduced_field_td = max(float(reduced_field_td), 1.0)
    gas_temperature_k = max(float(gas_temperature_k), 1.0)
    pressure_torr = max(float(pressure_torr), 0.01)
    field_term = 0.045 * reduced_field_td**0.85
    temperature_term = 0.18 * np.log1p(gas_temperature_k / 300.0)
    pressure_term = 0.12 * np.log1p(pressure_torr)
    return float(np.clip(1.2 + field_term + temperature_term - pressure_term, 1.0, 18.0))


def make_energy_grid(blocks, points=260):
    minima = []
    maxima = []
    for block in blocks:
        df = block.get("data_frame")
        if df is None or df.empty:
            continue
        positive_energy = df.loc[df["energy"] > 0, "energy"]
        if not positive_energy.empty:
            minima.append(float(positive_energy.min()))
            maxima.append(float(positive_energy.max()))

    min_energy = max(0.02, min(minima) if minima else 0.02)
    max_energy = min(250.0, max(maxima) if maxima else 80.0)
    max_energy = max(max_energy, min_energy * 10.0)
    return np.logspace(np.log10(min_energy), np.log10(max_energy), points)


def generate_demo_eedf(energy_eV, mean_energy_eV):
    temperature_like = max(mean_energy_eV / 1.5, 0.15)
    raw = np.sqrt(np.maximum(energy_eV, 1e-9)) * np.exp(-energy_eV / temperature_like)
    area = _trapz(raw, energy_eV)
    if area <= 0:
        return np.zeros_like(energy_eV)
    return raw / area


def _interpolate_sigma(block, energy_grid):
    df = block["data_frame"].sort_values("energy")
    return np.interp(
        energy_grid,
        df["energy"].to_numpy(dtype=float),
        df["cross_section"].to_numpy(dtype=float),
        left=0.0,
        right=0.0,
    )


def compute_demo_rate_coefficients(blocks, energy_grid, eedf, max_processes=24):
    electron_speed = np.sqrt(2.0 * np.maximum(energy_grid, 0.0) * E_CHARGE_C / ELECTRON_MASS_KG)
    rows = []
    for block in blocks[:max_processes]:
        sigma = _interpolate_sigma(block, energy_grid)
        rate = float(_trapz(sigma * electron_speed * eedf, energy_grid))
        rows.append(
            {
                "process": block.get("label", f"Process {block.get('index', 0) + 1}"),
                "type": block.get("collision_type", "").title(),
                "threshold_eV": block.get("threshold_eV"),
                "rate_coefficient_m3_s": rate,
                "source": DEMO_LABEL,
            }
        )
    return pd.DataFrame(rows).sort_values("rate_coefficient_m3_s", ascending=False).reset_index(drop=True)


def compute_demo_transport(mean_energy_eV, reduced_field_td=150.0, gas_temperature_k=300.0, pressure_torr=5.0):
    gas_density_m3 = pressure_torr * TORR_TO_PA / (KB_J_PER_K * gas_temperature_k)
    electric_field_v_m = reduced_field_td * 1e-21 * gas_density_m3
    mobility = 0.18 * (100.0 / max(reduced_field_td, 1.0)) ** 0.32 * (300.0 / gas_temperature_k) ** 0.1
    diffusion = mobility * max(mean_energy_eV, 0.1) * 2.0 / 3.0
    drift_velocity = mobility * electric_field_v_m
    return pd.DataFrame(
        [
            {"coefficient": "mean electron energy", "value": mean_energy_eV, "unit": "eV", "source": DEMO_LABEL},
            {"coefficient": "mobility", "value": mobility, "unit": "m2 V-1 s-1", "source": DEMO_LABEL},
            {"coefficient": "diffusion coefficient", "value": diffusion, "unit": "m2 s-1", "source": DEMO_LABEL},
            {"coefficient": "drift velocity", "value": drift_velocity, "unit": "m s-1", "source": DEMO_LABEL},
        ]
    )


def generate_demo_bolsig_outputs(
    blocks,
    gas="D2",
    gas_temperature_k=300.0,
    pressure_torr=5.0,
    reduced_field_td=150.0,
    max_processes=24,
):
    blocks = [block for block in blocks if block.get("data_frame") is not None and not block["data_frame"].empty]
    if not blocks:
        raise ValueError("No LXCat process blocks were available for demo BOLSIG+ output generation.")

    mean_energy = estimate_mean_energy_eV(reduced_field_td, gas_temperature_k, pressure_torr)
    energy_grid = make_energy_grid(blocks)
    eedf = generate_demo_eedf(energy_grid, mean_energy)
    eedf_df = pd.DataFrame(
        {
            "energy_eV": energy_grid,
            "eedf": eedf,
            "gas": gas,
            "source": DEMO_LABEL,
        }
    )
    transport_df = compute_demo_transport(mean_energy, reduced_field_td, gas_temperature_k, pressure_torr)
    rates_df = compute_demo_rate_coefficients(blocks, energy_grid, eedf, max_processes=max_processes)
    return {
        "source": DEMO_LABEL,
        "mean_energy_eV": mean_energy,
        "eedf": eedf_df,
        "transport": transport_df,
        "rates": rates_df,
    }


def save_demo_bolsig_outputs(outputs, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "eedf": output_dir / "demo_eedf.csv",
        "transport": output_dir / "demo_transport_coefficients.csv",
        "rates": output_dir / "demo_rate_coefficients.csv",
    }
    outputs["eedf"].to_csv(paths["eedf"], index=False)
    outputs["transport"].to_csv(paths["transport"], index=False)
    outputs["rates"].to_csv(paths["rates"], index=False)
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate clearly labeled demo BOLSIG+ outputs.")
    parser.add_argument("lxcat_file", help="Path to an LXCat .txt file")
    parser.add_argument("--output-dir", default="data/bolsig_outputs", help="Directory for demo CSV files")
    parser.add_argument("--reduced-field-td", type=float, default=150.0)
    parser.add_argument("--pressure-torr", type=float, default=5.0)
    parser.add_argument("--gas-temperature-k", type=float, default=300.0)
    args = parser.parse_args()

    import sys

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from scripts.parse_lxcat import parse_lxcat_file

    summary = parse_lxcat_file(args.lxcat_file)
    demo = generate_demo_bolsig_outputs(
        summary["blocks"],
        gas_temperature_k=args.gas_temperature_k,
        pressure_torr=args.pressure_torr,
        reduced_field_td=args.reduced_field_td,
    )
    saved = save_demo_bolsig_outputs(demo, args.output_dir)
    for name, path in saved.items():
        print(f"{name}: {path}")
