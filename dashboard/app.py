import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.demo_bolsig_outputs import DEMO_LABEL, generate_demo_bolsig_outputs, save_demo_bolsig_outputs
from scripts.demo_zdplaskin_outputs import generate_demo_species_density, save_demo_zdplaskin_outputs
from scripts.parse_bolsig_output import parse_bolsig_output
from scripts.parse_lxcat import export_block_for_bolsig, parse_lxcat_file, process_summary_dataframe
from scripts.parse_zdplaskin_output import parse_zdplaskin_output, save_csv as save_zdplaskin_csv
from scripts.run_bolsig import make_bolsig_script, run_bolsig
from scripts.run_zdplaskin import run_zdplaskin


DATA_DIR = ROOT_DIR / "data"
LXCAT_DIR = DATA_DIR / "lxcat"
BOLSIG_INPUT_DIR = DATA_DIR / "bolsig_inputs"
BOLSIG_OUTPUT_DIR = DATA_DIR / "bolsig_outputs"
ZDPLASKIN_INPUT_DIR = DATA_DIR / "zdplaskin_inputs"
ZDPLASKIN_OUTPUT_DIR = DATA_DIR / "zdplaskin_outputs"
PLOTS_DIR = ROOT_DIR / "plots"

for directory in [
    LXCAT_DIR,
    BOLSIG_INPUT_DIR,
    BOLSIG_OUTPUT_DIR,
    ZDPLASKIN_INPUT_DIR,
    ZDPLASKIN_OUTPUT_DIR,
    PLOTS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)


PAGE_TITLE = "Deuterium Plasma Modeling Workflow: LXCat \u2192 BOLSIG+ \u2192 ZDPlasKin"
PAGE_SUBTITLE = (
    "Collision cross sections, electron energy distributions, transport coefficients, reaction rates, "
    "and species-density evolution for a spherical neutron generator workflow."
)
PLOT_COLORS = [
    "#0f766e",
    "#b7791f",
    "#2563eb",
    "#be123c",
    "#475569",
    "#15803d",
    "#0e7490",
    "#a16207",
    "#db2777",
    "#334155",
]


st.set_page_config(
    page_title="Deuterium Plasma Workflow Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css():
    st.markdown(
        """
<style>
    :root {
        color-scheme: light;
    }
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background: #f6f8fb;
        color: #0f172a;
    }
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4,
    [data-testid="stMarkdownContainer"] h5,
    [data-testid="stMarkdownContainer"] h6,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] label,
    [data-testid="stCaptionContainer"],
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p {
        color: #0f172a;
    }
    .stApp {
        background: #f6f8fb;
        color: #17202a;
    }
    .block-container {
        max-width: 1480px;
        padding-top: 1.7rem;
        padding-bottom: 3rem;
    }
    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #dbe3ea;
    }
    .hero-panel {
        background: #ffffff;
        border: 1px solid #dbe3ea;
        border-left: 7px solid #0f766e;
        border-radius: 8px;
        padding: 1.15rem 1.35rem 1.1rem;
        box-shadow: 0 14px 34px rgba(15, 23, 42, 0.07);
    }
    .hero-panel h1 {
        color: #0f172a;
        font-size: 2.25rem;
        line-height: 1.12;
        margin: 0 0 0.45rem 0;
        letter-spacing: 0;
    }
    .hero-panel p {
        color: #475569;
        font-size: 1.02rem;
        line-height: 1.5;
        margin: 0;
        max-width: 1020px;
    }
    .workflow {
        display: flex;
        align-items: stretch;
        gap: 0.45rem;
        margin: 1rem 0 1.35rem;
        overflow-x: auto;
        padding-bottom: 0.15rem;
    }
    .workflow-step {
        min-width: 150px;
        flex: 1;
        background: #ffffff;
        border: 1px solid #d7e0e7;
        border-radius: 8px;
        padding: 0.8rem 0.85rem;
    }
    .workflow-step span {
        display: block;
        color: #0f766e;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.2rem;
    }
    .workflow-step strong {
        display: block;
        color: #17202a;
        font-size: 0.94rem;
        line-height: 1.25;
    }
    .workflow-arrow {
        color: #b7791f;
        align-self: center;
        font-size: 1.35rem;
        font-weight: 700;
        min-width: 1.2rem;
        text-align: center;
    }
    .section-rule {
        height: 1px;
        background: #dbe3ea;
        margin: 1.45rem 0 1rem;
    }
    .section-heading {
        display: flex;
        align-items: baseline;
        gap: 0.75rem;
        margin-bottom: 0.55rem;
    }
    .section-heading span {
        color: #0f766e;
        font-weight: 800;
        font-size: 0.88rem;
        letter-spacing: 0.08em;
    }
    .section-heading h2 {
        color: #0f172a;
        font-size: 1.42rem;
        line-height: 1.25;
        margin: 0;
        letter-spacing: 0;
    }
    .metric-card {
        background: #ffffff;
        border: 1px solid #dbe3ea;
        border-radius: 8px;
        padding: 0.9rem 1rem;
        min-height: 90px;
    }
    .metric-card .label {
        color: #64748b;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }
    .metric-card .value {
        color: #0f172a;
        font-size: 1.28rem;
        line-height: 1.2;
        font-weight: 780;
        overflow-wrap: anywhere;
    }
    .status-demo, .status-real {
        display: inline-block;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 760;
        letter-spacing: 0.02em;
        padding: 0.28rem 0.62rem;
        margin: 0.2rem 0 0.55rem;
    }
    .status-demo {
        color: #9a3412;
        background: #fff7ed;
        border: 1px solid #fed7aa;
    }
    .status-real {
        color: #065f46;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
    }
    .science-note {
        background: #ffffff;
        border-left: 4px solid #2563eb;
        border-radius: 8px;
        padding: 0.85rem 1rem;
        color: #334155;
        line-height: 1.48;
        margin: 0.45rem 0 0.85rem;
    }
    .interpretation-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.75rem;
        margin-top: 0.6rem;
    }
    .interpretation-item {
        background: #ffffff;
        border: 1px solid #dbe3ea;
        border-radius: 8px;
        padding: 0.9rem 1rem;
        min-height: 132px;
    }
    .interpretation-item strong {
        color: #0f172a;
        display: block;
        margin-bottom: 0.35rem;
    }
    .interpretation-item p {
        color: #475569;
        line-height: 1.45;
        margin: 0;
    }
    .species-chip {
        display: inline-block;
        border: 1px solid #cbd5e1;
        background: #ffffff;
        border-radius: 999px;
        color: #334155;
        font-size: 0.85rem;
        font-weight: 700;
        padding: 0.25rem 0.58rem;
        margin: 0 0.28rem 0.35rem 0;
    }
    @media (max-width: 900px) {
        .hero-panel h1 { font-size: 1.75rem; }
        .interpretation-grid { grid-template-columns: 1fr; }
        .workflow-step { min-width: 170px; }
    }
</style>
        """,
        unsafe_allow_html=True,
    )


def section_heading(step, title):
    st.markdown(
        f"""
<div class="section-rule"></div>
<div class="section-heading"><span>STEP {step}</span><h2>{title}</h2></div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(text, is_demo=True):
    klass = "status-demo" if is_demo else "status-real"
    st.markdown(f'<span class="{klass}">{text}</span>', unsafe_allow_html=True)


def metric_card(label, value):
    st.markdown(
        f"""
<div class="metric-card">
    <div class="label">{label}</div>
    <div class="value">{value}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def science_note(text):
    st.markdown(f'<div class="science-note">{text}</div>', unsafe_allow_html=True)


def format_sci(value, digits=2):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    return f"{float(value):.{digits}e}"


def format_float(value, digits=2):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    return f"{float(value):,.{digits}f}"


@st.cache_data(show_spinner=False)
def cached_lxcat_parse(path_text, modified_time):
    return parse_lxcat_file(path_text)


def available_lxcat_files():
    return sorted(LXCAT_DIR.glob("*.txt"), key=lambda item: item.name.lower())


def default_lxcat_index(files):
    for i, path in enumerate(files):
        if path.name.lower() == "cross section.txt":
            return i
    return 0


def selected_blocks_from_indices(summary, indices):
    index_set = set(indices)
    return [block for block in summary["blocks"] if block["index"] in index_set]


def plot_cross_sections(blocks, log_x=True, log_y=True):
    fig = go.Figure()
    for i, block in enumerate(blocks):
        df = block["data_frame"]
        fig.add_trace(
            go.Scatter(
                x=df["energy"],
                y=df["cross_section"],
                mode="lines",
                name=block["label"],
                line=dict(width=2.2, color=PLOT_COLORS[i % len(PLOT_COLORS)]),
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "Energy: %{x:.3e} eV<br>"
                    "Cross section: %{y:.3e} m2<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        title="LXCat electron-impact cross sections",
        template="plotly_white",
        height=520,
        margin=dict(l=10, r=20, t=70, b=20),
        legend=dict(orientation="h", y=-0.28, x=0, font=dict(size=11)),
        font=dict(family="Arial", size=13, color="#17202a"),
    )
    fig.update_xaxes(title_text="Electron energy (eV)", type="log" if log_x else "linear", gridcolor="#e2e8f0")
    fig.update_yaxes(title_text="Cross section (m2)", type="log" if log_y else "linear", gridcolor="#e2e8f0")
    return fig


def plot_eedf(eedf_df, log_x=True):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=eedf_df["energy_eV"],
            y=eedf_df["eedf"],
            mode="lines",
            line=dict(width=3, color="#0f766e"),
            fill="tozeroy",
            fillcolor="rgba(15, 118, 110, 0.15)",
            name="EEDF",
            hovertemplate="Energy: %{x:.3e} eV<br>f(E): %{y:.3e}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Electron energy distribution function",
        template="plotly_white",
        height=430,
        margin=dict(l=10, r=20, t=70, b=15),
        font=dict(family="Arial", size=13, color="#17202a"),
        showlegend=False,
    )
    fig.update_xaxes(title_text="Electron energy (eV)", type="log" if log_x else "linear", gridcolor="#e2e8f0")
    fig.update_yaxes(title_text="f(E), normalized", gridcolor="#e2e8f0")
    return fig


def plot_species(species_df):
    fig = go.Figure()
    species_columns = [column for column in ["e", "D2", "D", "D+", "D2+", "D3+"] if column in species_df.columns]
    for i, species in enumerate(species_columns):
        fig.add_trace(
            go.Scatter(
                x=species_df["time_s"],
                y=species_df[species],
                mode="lines",
                name=species,
                line=dict(width=2.6, color=PLOT_COLORS[i % len(PLOT_COLORS)]),
                hovertemplate=f"<b>{species}</b><br>Time: %{{x:.3e}} s<br>Density: %{{y:.3e}} m-3<extra></extra>",
            )
        )
    fig.update_layout(
        title="ZDPlasKin species-density evolution",
        template="plotly_white",
        height=520,
        margin=dict(l=10, r=20, t=70, b=20),
        legend=dict(orientation="h", y=-0.22, x=0),
        font=dict(family="Arial", size=13, color="#17202a"),
    )
    fig.update_xaxes(title_text="Time (s)", type="log", gridcolor="#e2e8f0")
    fig.update_yaxes(title_text="Species density (m-3)", type="log", gridcolor="#e2e8f0")
    return fig


def normalize_real_bolsig(parsed):
    eedf = parsed.get("eedf", pd.DataFrame()).copy()
    if not eedf.empty:
        eedf = eedf.rename(columns={"energy": "energy_eV"})
        eedf["source"] = "configured BOLSIG+ output"
    transport = parsed.get("transport", pd.DataFrame()).copy()
    if not transport.empty:
        transport = transport.rename(columns={"parameter": "coefficient"})
        transport["unit"] = ""
        transport["source"] = "configured BOLSIG+ output"
    rates = parsed.get("rates", pd.DataFrame()).copy()
    if not rates.empty:
        rates = rates.rename(columns={"parameter": "process", "value": "rate_coefficient_m3_s"})
        rates["source"] = "configured BOLSIG+ output"
    return {"source": "configured BOLSIG+ output", "eedf": eedf, "transport": transport, "rates": rates}


def normalize_real_zdplaskin(parsed):
    selected = parsed["selected"].copy()
    time_column = parsed["time_column"]
    if time_column != "time_s":
        selected = selected.rename(columns={time_column: "time_s"})
    return selected


def run_configured_bolsig(lxcat_path, executable_path, gas, block_index=0):
    if not str(executable_path).strip():
        raise FileNotFoundError("No BOLSIG+ executable path was supplied.")
    executable = Path(executable_path)
    if not executable.exists() or not executable.is_file():
        raise FileNotFoundError(f"BOLSIG+ executable not found: {executable}")

    collision_file = BOLSIG_INPUT_DIR / f"{lxcat_path.stem}_block{block_index}.dat"
    export_block_for_bolsig(lxcat_path, block_index, collision_file)
    script_path = BOLSIG_INPUT_DIR / "bolsig_input.dat"
    output_name = "bolsig_output.dat"
    make_bolsig_script(collision_file.name, script_path, output_name=output_name, species=gas)
    code, stdout, stderr = run_bolsig(executable, script_path, work_dir=BOLSIG_INPUT_DIR)
    output_file = BOLSIG_INPUT_DIR / output_name
    if code != 0 or not output_file.exists():
        detail = stderr or stdout or "BOLSIG+ did not produce a parseable output file."
        raise RuntimeError(detail)
    return normalize_real_bolsig(parse_bolsig_output(output_file)), stdout, stderr


def run_configured_zdplaskin(executable_path, case_path):
    if not str(executable_path).strip():
        raise FileNotFoundError("No ZDPlasKin executable path was supplied.")
    executable = Path(executable_path)
    if not executable.exists() or not executable.is_file():
        raise FileNotFoundError(f"ZDPlasKin executable not found: {executable}")
    if not case_path:
        raise FileNotFoundError("No ZDPlasKin case path was supplied.")
    code, stdout, stderr, cwd = run_zdplaskin(executable, case_path)
    if code != 0:
        raise RuntimeError(stderr or stdout or "ZDPlasKin returned a nonzero exit code.")
    possible_outputs = sorted(Path(cwd).glob("*.txt"), key=lambda item: item.stat().st_mtime)
    if not possible_outputs:
        raise FileNotFoundError(f"No text output files were found in {cwd}")
    parsed = parse_zdplaskin_output(possible_outputs[-1])
    csv_path = ZDPLASKIN_OUTPUT_DIR / f"{possible_outputs[-1].stem}_species_density.csv"
    save_zdplaskin_csv(parsed, csv_path)
    return normalize_real_zdplaskin(parsed), stdout, stderr


inject_css()

with st.sidebar:
    st.header("Inputs")
    uploaded_file = st.file_uploader("LXCat .txt cross-section file", type=["txt"])
    if uploaded_file is not None:
        destination = LXCAT_DIR / uploaded_file.name
        destination.write_bytes(uploaded_file.getbuffer())
        st.success(f"Saved {uploaded_file.name}")

    files = available_lxcat_files()
    if not files:
        st.warning("Place an LXCat .txt file in data/lxcat/.")
        st.stop()

    selected_name = st.selectbox(
        "Select LXCat file",
        options=[path.name for path in files],
        index=default_lxcat_index(files),
    )
    selected_path = LXCAT_DIR / selected_name

    st.divider()
    st.header("Gas and Field")
    gas = st.selectbox("Gas", options=["D2"], index=0)
    gas_temperature_k = st.number_input("Gas temperature (K)", min_value=100.0, max_value=2000.0, value=300.0, step=25.0)
    pressure_torr = st.number_input("Pressure (torr)", min_value=0.001, max_value=1000.0, value=5.0, step=0.5, format="%.3f")
    reduced_field_td = st.slider("Reduced electric field E/N (Td)", min_value=1.0, max_value=500.0, value=150.0, step=1.0)

    st.divider()
    st.header("Plot Controls")
    log_energy = st.toggle("Log energy axis", value=True)
    log_cross_section = st.toggle("Log cross-section axis", value=True)
    max_curves = st.slider("Max plotted cross-section curves", min_value=1, max_value=20, value=8)

    st.divider()
    st.header("Executables")
    bolsig_executable = st.text_input("BOLSIG+ executable path", value="")
    run_bolsig_button = st.button("Run configured BOLSIG+", width="stretch")
    zdplaskin_executable = st.text_input("ZDPlasKin executable path", value="")
    zdplaskin_case = st.text_input("ZDPlasKin case folder or kinet.inp path", value="")
    run_zdplaskin_button = st.button("Run configured ZDPlasKin", width="stretch")


try:
    summary = cached_lxcat_parse(str(selected_path), selected_path.stat().st_mtime)
except Exception as exc:
    st.error(f"Could not parse the selected LXCat file: {exc}")
    st.stop()

process_df = process_summary_dataframe(summary)
all_blocks = summary["blocks"]
default_process_indices = process_df["index"].head(max_curves).tolist()

st.markdown(
    f"""
<div class="hero-panel">
    <h1>{PAGE_TITLE}</h1>
    <p>{PAGE_SUBTITLE}</p>
</div>
    """,
    unsafe_allow_html=True,
)

workflow_steps = [
    ("01", "LXCat<br>Cross Sections"),
    ("02", "BOLSIG+"),
    ("03", "EEDF + Transport<br>Coefficients"),
    ("04", "Rate<br>Coefficients"),
    ("05", "ZDPlasKin"),
    ("06", "Species<br>Densities"),
]
workflow_html = ['<div class="workflow">']
for i, (number, label) in enumerate(workflow_steps):
    workflow_html.append(f'<div class="workflow-step"><span>{number}</span><strong>{label}</strong></div>')
    if i < len(workflow_steps) - 1:
        workflow_html.append('<div class="workflow-arrow">&rarr;</div>')
workflow_html.append("</div>")
st.markdown("".join(workflow_html), unsafe_allow_html=True)

section_heading("1", "LXCat Cross Sections")
science_note(
    "LXCat supplies energy-dependent electron collision cross sections &sigma;(E), which define how likely each "
    "electron-impact process is as a function of electron energy."
)

meta = summary.get("metadata", {})
energy_min = process_df["energy_min_eV"].min()
energy_max = process_df["energy_max_eV"].max()
max_sigma = process_df["max_cross_section_m2"].max()

metric_cols = st.columns(4)
with metric_cols[0]:
    metric_card("Selected file", selected_path.name)
with metric_cols[1]:
    metric_card("Collision processes", f"{len(all_blocks):,}")
with metric_cols[2]:
    metric_card("Energy range", f"{format_float(energy_min)}-{format_float(energy_max)} eV")
with metric_cols[3]:
    metric_card("Max cross section", f"{format_sci(max_sigma)} m2")

if meta:
    database = meta.get("database", "LXCat")
    permlink = meta.get("permlink", "")
    st.caption(f"Source metadata: {database}" + (f" | {permlink}" if permlink else ""))

process_labels = {}
for _, row in process_df.iterrows():
    process_index = int(row["index"])
    process_labels[f"{process_index:03d} | {str(row['process'])[:110]}"] = process_index
default_labels = [label for label, idx in process_labels.items() if idx in default_process_indices]
selected_labels = st.multiselect(
    "Processes to plot",
    options=list(process_labels.keys()),
    default=default_labels,
)
selected_indices = [process_labels[label] for label in selected_labels][:max_curves]
if not selected_indices:
    selected_indices = default_process_indices
selected_blocks = selected_blocks_from_indices(summary, selected_indices)
selected_bolsig_index = selected_indices[0] if selected_indices else 0
selected_bolsig_label = next((label for label, idx in process_labels.items() if idx == selected_bolsig_index), None)
if selected_bolsig_label:
    st.caption(f"BOLSIG+ will run on the selected process block: {selected_bolsig_label}")

table_df = process_df.copy()
table_df["threshold_eV"] = table_df["threshold_eV"].map(lambda value: "" if pd.isna(value) else f"{value:.4g}")
table_df["energy_min_eV"] = table_df["energy_min_eV"].map(lambda value: f"{value:.4g}")
table_df["energy_max_eV"] = table_df["energy_max_eV"].map(lambda value: f"{value:.4g}")
table_df["max_cross_section_m2"] = table_df["max_cross_section_m2"].map(lambda value: f"{value:.3e}")
st.dataframe(
    table_df,
    width="stretch",
    hide_index=True,
    height=310,
    column_order=[
        "index",
        "type",
        "target",
        "process",
        "threshold_eV",
        "rows",
        "energy_min_eV",
        "energy_max_eV",
        "max_cross_section_m2",
    ],
)

st.plotly_chart(plot_cross_sections(selected_blocks, log_x=log_energy, log_y=log_cross_section), width="stretch")

section_heading("2", "BOLSIG+ Electron Kinetics")
science_note(
    "BOLSIG+ solves the Boltzmann equation for the electron energy distribution function f(E), balancing "
    "electric-field heating against collisional energy losses."
)

demo_bolsig = generate_demo_bolsig_outputs(
    all_blocks,
    gas=gas,
    gas_temperature_k=gas_temperature_k,
    pressure_torr=pressure_torr,
    reduced_field_td=reduced_field_td,
)
save_demo_bolsig_outputs(demo_bolsig, BOLSIG_OUTPUT_DIR)

if run_bolsig_button:
    try:
        result, stdout, stderr = run_configured_bolsig(selected_path, bolsig_executable, gas, selected_bolsig_index)
        st.session_state["bolsig_outputs"] = result
        st.session_state["bolsig_message"] = "Configured BOLSIG+ output parsed successfully."
    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
        st.session_state["bolsig_outputs"] = None
        st.session_state["bolsig_message"] = f"BOLSIG+ run was not available; showing demo output. Details: {exc}"

bolsig_outputs = st.session_state.get("bolsig_outputs") or demo_bolsig
bolsig_is_demo = bolsig_outputs.get("source") == DEMO_LABEL
status_badge(DEMO_LABEL if bolsig_is_demo else "configured BOLSIG+ output", is_demo=bolsig_is_demo)
if st.session_state.get("bolsig_message"):
    st.info(st.session_state["bolsig_message"])

conditions = pd.DataFrame(
    [
        {"input": "gas", "value": gas, "unit": ""},
        {"input": "gas temperature", "value": f"{gas_temperature_k:.0f}", "unit": "K"},
        {"input": "pressure", "value": f"{pressure_torr:.3f}", "unit": "torr"},
        {"input": "reduced electric field E/N", "value": f"{reduced_field_td:.0f}", "unit": "Td"},
    ]
)
left_col, right_col = st.columns([0.34, 0.66])
with left_col:
    st.dataframe(conditions, width="stretch", hide_index=True, height=178)
    mean_energy = bolsig_outputs.get("mean_energy_eV")
    if mean_energy is not None:
        metric_card("Demo mean electron energy", f"{mean_energy:.2f} eV")
with right_col:
    eedf_df = bolsig_outputs["eedf"].copy()
    if "energy" in eedf_df.columns:
        eedf_df = eedf_df.rename(columns={"energy": "energy_eV"})
    st.plotly_chart(plot_eedf(eedf_df, log_x=log_energy), width="stretch")

section_heading("3", "Transport and Rate Coefficients")
st.latex(r"k_i = \int \sigma_i(E)\,v(E)\,f(E)\,dE")

transport_df = bolsig_outputs["transport"].copy()
rates_df = bolsig_outputs["rates"].copy()
transport_display = transport_df.copy()
if "value" in transport_display.columns:
    transport_display["value"] = transport_display["value"].map(
        lambda value: f"{float(value):.4g}" if isinstance(value, (int, float, np.number)) else str(value)
    )
if "rate_coefficient_m3_s" in rates_df.columns:
    rates_display = rates_df.head(18).copy()
    rates_display["rate_coefficient_m3_s"] = rates_display["rate_coefficient_m3_s"].map(lambda value: f"{float(value):.3e}")
else:
    rates_display = rates_df.head(18)

transport_col, rates_col = st.columns([0.38, 0.62])
with transport_col:
    st.subheader("Transport Coefficients")
    st.dataframe(transport_display, width="stretch", hide_index=True, height=245)
with rates_col:
    st.subheader("Reaction Rate Coefficients")
    st.dataframe(rates_display, width="stretch", hide_index=True, height=245)

section_heading("4", "ZDPlasKin Plasma Chemistry")
science_note(
    "ZDPlasKin uses reaction rates to solve time-dependent species balance equations, converting electron kinetics "
    "into density histories for charged and neutral deuterium species."
)

demo_species_df = generate_demo_species_density(
    rates=rates_df,
    gas_temperature_k=gas_temperature_k,
    pressure_torr=pressure_torr,
)
save_demo_zdplaskin_outputs(demo_species_df, ZDPLASKIN_OUTPUT_DIR)

if run_zdplaskin_button:
    try:
        species_result, stdout, stderr = run_configured_zdplaskin(zdplaskin_executable, zdplaskin_case)
        st.session_state["zdplaskin_species"] = species_result
        st.session_state["zdplaskin_message"] = "Configured ZDPlasKin output parsed successfully."
    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
        st.session_state["zdplaskin_species"] = None
        st.session_state["zdplaskin_message"] = f"ZDPlasKin run was not available; showing demo output. Details: {exc}"

species_df = st.session_state.get("zdplaskin_species")
species_is_demo = species_df is None
if species_is_demo:
    species_df = demo_species_df
status_badge(DEMO_LABEL if species_is_demo else "configured ZDPlasKin output", is_demo=species_is_demo)
if st.session_state.get("zdplaskin_message"):
    st.info(st.session_state["zdplaskin_message"])

st.markdown(
    "".join([f'<span class="species-chip">{species}</span>' for species in ["e", "D2", "D", "D+", "D2+", "D3+"]]),
    unsafe_allow_html=True,
)
st.plotly_chart(plot_species(species_df), width="stretch")

section_heading("5", "Interpretation Panel")
st.markdown(
    """
<div class="interpretation-grid">
    <div class="interpretation-item">
        <strong>LXCat</strong>
        <p>Microscopic collision probabilities enter as cross sections that vary with electron energy.</p>
    </div>
    <div class="interpretation-item">
        <strong>BOLSIG+</strong>
        <p>The Boltzmann solver converts those cross sections into electron-population behavior and transport response.</p>
    </div>
    <div class="interpretation-item">
        <strong>Rate Coefficients</strong>
        <p>Energy-dependent cross sections become reaction rates that can drive plasma chemistry source terms.</p>
    </div>
    <div class="interpretation-item">
        <strong>ZDPlasKin</strong>
        <p>Species-balance equations evolve e, D2, D, D+, D2+, and D3+ densities over time.</p>
    </div>
</div>
    """,
    unsafe_allow_html=True,
)
science_note(
    "In a spherical neutron generator, D+, D2+, and D3+ matter because ion production and extraction influence "
    "beam formation and neutron yield."
)

