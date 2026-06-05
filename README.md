# Deuterium Plasma Modeling Workflow Dashboard

This workspace contains a local Streamlit dashboard for presenting the workflow:

`LXCat cross sections -> BOLSIG+ electron kinetics -> EEDF + transport coefficients -> rate coefficients -> ZDPlasKin plasma chemistry -> species density evolution`

The dashboard is designed to work immediately as a polished demo using an LXCat `.txt` file. When BOLSIG+ or ZDPlasKin executable paths are not configured, the app generates clearly labeled `demo output until executable paths are configured` data so the full workflow can still be presented.

## Install

From this repository root:

```powershell
python -m pip install -r requirements.txt
```

If a local virtual environment is configured, run the same command through that environment's Python. The launcher checks the local venv first and falls back to system Python when the venv is incomplete.

## Run

```powershell
streamlit run dashboard/app.py
```

or use:

```powershell
.\open-dashboard.cmd
```

Streamlit will print a local URL, usually `http://localhost:8501`.

## Folder Structure

- `dashboard/app.py` - the presentation-ready Streamlit dashboard.
- `data/lxcat/` - LXCat `.txt` cross-section files. The attached `Cross section.txt` should live here.
- `data/bolsig_inputs/` - generated or copied inputs for configured BOLSIG+ runs.
- `data/bolsig_outputs/` - demo or parsed BOLSIG+ EEDF, transport, and rate CSV outputs.
- `data/zdplaskin_inputs/` - optional ZDPlasKin input staging area.
- `data/zdplaskin_outputs/` - demo or parsed species-density CSV outputs.
- `plots/` - reserved for exported figures.
- `scripts/parse_lxcat.py` - parses LXCat collision blocks and process metadata.
- `scripts/demo_bolsig_outputs.py` - generates clearly labeled demo EEDF, transport, and rates.
- `scripts/parse_bolsig_output.py` - parser for real BOLSIG+ text output.
- `scripts/demo_zdplaskin_outputs.py` - generates clearly labeled demo species-density evolution.
- `scripts/parse_zdplaskin_output.py` - parser for real ZDPlasKin tabular output.

## LXCat Files

Place LXCat `.txt` files in:

```text
data/lxcat/
```

The dashboard sidebar lets you select an existing file or upload a new one. The parser identifies collision processes, target states, threshold energies, row counts, and energy/cross-section ranges.

## BOLSIG+ Configuration

The dashboard always shows a demo EEDF, transport table, and rate-coefficient table. To attempt a real BOLSIG+ run:

1. Enter the full path to `bolsigplus.exe` in the sidebar.
2. Click `Run configured BOLSIG+`.
3. If the executable or output is not available, the dashboard keeps showing the clearly labeled demo output.

## ZDPlasKin Configuration

The dashboard always shows demo species-density evolution for:

`e`, `D2`, `D`, `D+`, `D2+`, `D3+`

To attempt a real ZDPlasKin run:

1. Enter the full path to the ZDPlasKin executable in the sidebar.
2. Enter a case folder or `kinet.inp` path.
3. Click `Run configured ZDPlasKin`.

The dashboard does not delete or overwrite the bundled `ZDPlasKin_2.0a_Windows/`, `ZDPlasKin_Work/`, or `QtPlaskin/` directories.

## Physical Meaning

Step 1, LXCat Cross Sections: LXCat supplies energy-dependent collision cross sections, sigma(E), which describe microscopic electron-impact probabilities.

Step 2, BOLSIG+ Electron Kinetics: BOLSIG+ solves for the electron energy distribution function, balancing electric-field heating and collisional losses.

Step 3, Transport and Rates: Transport coefficients describe electron swarm behavior, while rate coefficients connect electron kinetics to plasma chemistry through `k_i = integral sigma_i(E) v(E) f(E) dE`.

Step 4, ZDPlasKin Plasma Chemistry: ZDPlasKin uses the rates in time-dependent species-balance equations.

Step 5, Interpretation: For a spherical neutron generator, `D+`, `D2+`, and `D3+` influence ion production, extraction, beam formation, and neutron yield.
