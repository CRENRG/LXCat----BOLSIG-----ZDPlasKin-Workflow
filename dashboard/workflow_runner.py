import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.demo_bolsig_outputs import DEMO_LABEL, generate_demo_bolsig_outputs
from scripts.demo_zdplaskin_outputs import generate_demo_species_density
from scripts.parse_bolsig_output import parse_bolsig_output
from scripts.parse_lxcat import parse_lxcat_file, process_summary_dataframe
from scripts.parse_zdplaskin_output import parse_zdplaskin_output
from scripts.run_bolsig import make_bolsig_script, run_bolsig, write_bolsig_collision_table


DATA_DIR = ROOT_DIR / "data"
LXCAT_DIR = DATA_DIR / "lxcat"
BOLSIG_RUNS_DIR = DATA_DIR / "bolsig_runs"
BOLSIG_OUTPUT_DIR = DATA_DIR / "bolsig_outputs"
ZDPLASKIN_OUTPUT_DIR = DATA_DIR / "zdplaskin_outputs"

for directory in [LXCAT_DIR, BOLSIG_RUNS_DIR, BOLSIG_OUTPUT_DIR, ZDPLASKIN_OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

DEFAULT_BOLSIG = ROOT_DIR / "ZDPlasKin_Work" / "tools" / "bolsig_dashboard" / "bolsig_bin" / "bolsigminus.exe"
BUNDLED_BOLSIG_DB = ROOT_DIR / "ZDPlasKin_Work" / "tools" / "bolsig_dashboard" / "bolsig_bin" / "SigloDataBase-LXCat-04Jun2013.txt"
DEFAULT_ZD_EXE = ROOT_DIR / "ZDPlasKin_Work" / "cases" / "two-reaction-example" / "output" / "two-reaction-example.exe"
DEFAULT_ZD_CASE = ROOT_DIR / "ZDPlasKin_Work" / "cases" / "two-reaction-example"


st.set_page_config(
    page_title="Local LXCat -> BOLSIG+ -> ZDPlasKin Runner",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
<style>
    .stApp { background: #f7f9fb; color: #0f172a; }
    .block-container { max-width: 1440px; padding-top: 1.4rem; }
    [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #dbe3ea; }
    .runner-hero {
        background: #ffffff;
        border: 1px solid #dbe3ea;
        border-left: 7px solid #2563eb;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.07);
        margin-bottom: 1rem;
    }
    .runner-hero h1 { margin: 0 0 0.35rem; font-size: 2rem; letter-spacing: 0; }
    .runner-hero p { margin: 0; color: #475569; line-height: 1.45; }
    .status-box {
        background: #ffffff;
        border: 1px solid #dbe3ea;
        border-radius: 8px;
        padding: 0.8rem 0.95rem;
        min-height: 92px;
    }
    .status-box b { display: block; margin-bottom: 0.25rem; color: #0f172a; }
    .status-box span { color: #475569; }
    .real-note {
        border-left: 4px solid #0f766e;
        background: #ffffff;
        border-radius: 8px;
        padding: 0.75rem 0.9rem;
        margin: 0.5rem 0 1rem;
        color: #334155;
    }
</style>
    """,
    unsafe_allow_html=True,
)


def note(text):
    st.markdown(f'<div class="real-note">{text}</div>', unsafe_allow_html=True)


def status_card(title, value):
    st.markdown(f'<div class="status-box"><b>{title}</b><span>{value}</span></div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def parse_lxcat_cached(path_text, modified_time):
    return parse_lxcat_file(path_text)


def plot_lxcat_blocks(blocks):
    fig = go.Figure()
    for block in blocks:
        df = block["data_frame"]
        fig.add_trace(
            go.Scatter(
                x=df["energy"],
                y=df["cross_section"],
                mode="lines",
                name=block["label"][:80],
            )
        )
    fig.update_layout(
        title="LXCat Cross Sections",
        template="plotly_white",
        height=430,
        margin=dict(l=10, r=10, t=55, b=15),
        legend=dict(orientation="h", y=-0.24),
    )
    fig.update_xaxes(title="Energy (eV)", type="log")
    fig.update_yaxes(title="Cross section (m2)", type="log")
    return fig


def plot_eedf(parsed):
    eedf = parsed.get("eedf", pd.DataFrame())
    fig = go.Figure()
    if isinstance(eedf, pd.DataFrame) and not eedf.empty:
        energy_col = "energy_eV" if "energy_eV" in eedf.columns else "energy"
        fig.add_trace(go.Scatter(x=eedf[energy_col], y=eedf["eedf"], mode="lines", name="EEDF"))
    fig.update_layout(
        title="BOLSIG+ EEDF",
        template="plotly_white",
        height=380,
        margin=dict(l=10, r=10, t=55, b=15),
    )
    fig.update_xaxes(title="Energy (eV)", type="log")
    fig.update_yaxes(title="f(E)")
    return fig


def with_demo_eedf_if_missing(parsed, demo_bolsig):
    if not isinstance(parsed, dict):
        return parsed
    eedf = parsed.get("eedf", pd.DataFrame())
    if isinstance(eedf, pd.DataFrame) and eedf.empty:
        merged = parsed.copy()
        merged["eedf"] = demo_bolsig["eedf"]
        return merged
    return parsed


def plot_species(parsed):
    selected = parsed["selected"].copy()
    time_col = parsed["time_column"]
    fig = go.Figure()
    for column in selected.columns:
        if column == time_col:
            continue
        fig.add_trace(go.Scatter(x=selected[time_col], y=selected[column], mode="lines", name=str(column)))
    fig.update_layout(
        title="ZDPlasKin Species Densities",
        template="plotly_white",
        height=430,
        margin=dict(l=10, r=10, t=55, b=15),
        legend=dict(orientation="h", y=-0.22),
    )
    fig.update_xaxes(title=str(time_col), type="log")
    fig.update_yaxes(title="Density", type="log")
    return fig


def make_demo_zdplaskin_parsed(rates=None, gas_temperature_k=300.0, pressure_torr=5.0):
    species_df = generate_demo_species_density(
        rates=rates,
        gas_temperature_k=gas_temperature_k,
        pressure_torr=pressure_torr,
    )
    species_columns = ["e", "D2", "D", "D+", "D2+", "D3+"]
    return {
        "data_frame": species_df,
        "selected": species_df[["time_s"] + species_columns],
        "time_column": "time_s",
        "species_columns": species_columns,
        "source": DEMO_LABEL,
    }


def demo_status(text):
    st.info(f"{text} Showing demo output until a real executable output is parsed.")


def make_run_dir():
    run_dir = BOLSIG_RUNS_DIR / time.strftime("run_%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def run_existing_zdplaskin_executable(executable_path, work_dir, pass_case_argument=False, case_argument="", timeout=300):
    executable = Path(executable_path)
    if not executable.exists():
        raise FileNotFoundError(f"ZDPlasKin executable not found: {executable}")
    cwd = Path(work_dir) if str(work_dir).strip() else executable.parent
    if not cwd.exists():
        raise FileNotFoundError(f"ZDPlasKin working folder not found: {cwd}")
    cmd = [str(executable)]
    if pass_case_argument and str(case_argument).strip():
        cmd.append(str(case_argument))
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, input="\n", timeout=timeout)
    return result, cwd, cmd


def possible_output_files(folder):
    folder = Path(folder)
    if not folder.exists():
        return []
    patterns = ["*.txt", "*.dat", "*.csv", "*.out"]
    files = []
    for pattern in patterns:
        files.extend(folder.glob(pattern))
    return sorted(set(files), key=lambda path: path.stat().st_mtime, reverse=True)


def parse_newest_zdplaskin_output(folder):
    errors = []
    for output_file in possible_output_files(folder):
        try:
            return output_file, parse_zdplaskin_output(output_file), errors
        except Exception as exc:
            errors.append(f"{output_file.name}: {exc}")
    return None, None, errors


st.markdown(
    """
<div class="runner-hero">
    <h1>Local Plasma Workflow Runner</h1>
    <p>Upload LXCat data, run BOLSIG+ from a local executable, inspect parsed outputs, and run or parse a ZDPlasKin case. This is the hands-on version, not the pre-made presentation demo.</p>
</div>
    """,
    unsafe_allow_html=True,
)

note(
    "Local execution mode is active. This dashboard can use executable paths and case folders on this laptop."
)

with st.sidebar:
    st.header("1. LXCat Input")
    uploaded_lxcat = st.file_uploader("Upload LXCat .txt", type=["txt"])
    if uploaded_lxcat is not None:
        destination = LXCAT_DIR / uploaded_lxcat.name
        destination.write_bytes(uploaded_lxcat.getbuffer())
        st.success(f"Saved {uploaded_lxcat.name}")

    lxcat_files = sorted(LXCAT_DIR.glob("*.txt"), key=lambda path: path.name.lower())
    if not lxcat_files:
        st.warning("Upload an LXCat .txt file first.")
        st.stop()
    selected_lxcat_name = st.selectbox("LXCat file", [path.name for path in lxcat_files])
    selected_lxcat = LXCAT_DIR / selected_lxcat_name

    st.divider()
    st.header("2. Conditions")
    gas = st.text_input("Gas species for BOLSIG+", value="D2")
    gas_temperature_k = st.number_input("Gas temperature (K)", min_value=100.0, max_value=2000.0, value=300.0, step=25.0)
    pressure_torr = st.number_input("Pressure (torr)", min_value=0.001, max_value=1000.0, value=5.0, step=0.5, format="%.3f")
    reduced_field_td = st.number_input("E/N (Td)", min_value=0.1, max_value=1000.0, value=150.0, step=10.0)

    st.divider()
    st.header("3. Executables")
    bolsig_path = st.text_input("BOLSIG+ executable", value=str(DEFAULT_BOLSIG if DEFAULT_BOLSIG.exists() else ""))
    zdplaskin_exe = st.text_input("ZDPlasKin/case executable", value=str(DEFAULT_ZD_EXE if DEFAULT_ZD_EXE.exists() else ""))
    zdplaskin_work_dir = st.text_input("ZDPlasKin working folder", value=str(DEFAULT_ZD_CASE if DEFAULT_ZD_CASE.exists() else ""))
    pass_case_argument = st.checkbox("Pass a case/input argument to ZDPlasKin executable", value=False)
    zd_case_argument = st.text_input("Optional ZDPlasKin argument", value="")


try:
    lxcat_summary = parse_lxcat_cached(str(selected_lxcat), selected_lxcat.stat().st_mtime)
except Exception as exc:
    st.error(f"Could not parse LXCat file: {exc}")
    st.stop()

process_df = process_summary_dataframe(lxcat_summary)
blocks = lxcat_summary["blocks"]

status_cols = st.columns(4)
with status_cols[0]:
    status_card("LXCat file", selected_lxcat.name)
with status_cols[1]:
    status_card("Detected processes", f"{len(blocks):,}")
with status_cols[2]:
    status_card("BOLSIG+ path", "found" if Path(bolsig_path).exists() else "not found")
with status_cols[3]:
    status_card("ZDPlasKin executable", "found" if Path(zdplaskin_exe).exists() else "not found")

tab_lxcat, tab_bolsig, tab_zd, tab_outputs = st.tabs(
    ["LXCat", "BOLSIG+ Run", "ZDPlasKin Run", "Outputs / Logs"]
)

with tab_lxcat:
    st.subheader("Parsed LXCat Processes")
    display_df = process_df.copy()
    for column in ["threshold_eV", "energy_min_eV", "energy_max_eV", "max_cross_section_m2"]:
        if column in display_df.columns:
            display_df[column] = display_df[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.4g}")
    st.dataframe(display_df, width="stretch", hide_index=True, height=320)

    labels = {f"{block['index']:03d} | {block['label'][:100]}": block["index"] for block in blocks}
    defaults = list(labels.keys())[:6]
    chosen_labels = st.multiselect("Plot processes", list(labels.keys()), default=defaults)
    chosen_indices = {labels[label] for label in chosen_labels}
    chosen_blocks = [block for block in blocks if block["index"] in chosen_indices]
    if chosen_blocks:
        st.plotly_chart(plot_lxcat_blocks(chosen_blocks), width="stretch")

with tab_bolsig:
    st.subheader("Run BOLSIG+ Locally")
    note("This step runs the executable path shown in the sidebar. It copies the selected LXCat file into a timestamped run folder and creates a BOLSIG input file.")

    demo_bolsig = generate_demo_bolsig_outputs(
        blocks,
        gas=gas,
        gas_temperature_k=gas_temperature_k,
        pressure_torr=pressure_torr,
        reduced_field_td=reduced_field_td,
    )
    bolsig_source_mode = st.radio(
        "BOLSIG+ collision source",
        options=[
            "Bundled complete SIGLO/LXCat database (reliable executable test)",
            "Selected uploaded LXCat process block (experimental)",
        ],
        index=0,
    )
    collision_types = {str(block.get("collision_type", "")).lower() for block in blocks}
    if not ({"elastic", "effective", "momentum"} & collision_types):
        st.warning(
            "The selected LXCat file does not include an elastic/effective momentum-transfer collision set. "
            "BOLSIG+ needs that for a complete swarm solve, so use the bundled database mode to prove the executable runs."
        )
    selected_bolsig_block = None
    if bolsig_source_mode.startswith("Bundled"):
        st.caption("Uses the bundled complete Ar collision set. This is the reliable mode for proving BOLSIG+ runs locally.")
    else:
        bolsig_block_labels = {f"{block['index']:03d} | {block['label'][:100]}": block for block in blocks}
        selected_bolsig_block_label = st.selectbox(
            "LXCat process block to convert for BOLSIG+",
            options=list(bolsig_block_labels.keys()),
            index=0,
        )
        selected_bolsig_block = bolsig_block_labels[selected_bolsig_block_label]
        st.caption("Your attached D2 Laporta file is not a complete Boltzmann collision set, so this mode may fall back to demo plots.")
    run_bolsig_button = st.button("Create input and run BOLSIG+", type="primary")

    if run_bolsig_button:
        try:
            run_dir = make_run_dir()
            if bolsig_source_mode.startswith("Bundled"):
                if not BUNDLED_BOLSIG_DB.exists():
                    raise FileNotFoundError(f"Bundled BOLSIG database not found: {BUNDLED_BOLSIG_DB}")
                collision_file = run_dir / BUNDLED_BOLSIG_DB.name
                shutil.copy2(BUNDLED_BOLSIG_DB, collision_file)
                run_species = "Ar"
            else:
                collision_file = run_dir / "cross_section.dat"
                write_bolsig_collision_table(
                    selected_bolsig_block["data_frame"][["energy", "cross_section"]].itertuples(index=False, name=None),
                    collision_file,
                    species=gas,
                    collision_type="EFFECTIVE",
                )
                run_species = gas
            script_path = run_dir / "bolsig_input.dat"
            output_name = "bolsig_output.dat"
            make_bolsig_script(
                collision_file.name,
                script_path,
                output_name=output_name,
                species=run_species,
                reduced_field_td=reduced_field_td,
                gas_temperature_k=gas_temperature_k,
                pressure_torr=pressure_torr,
            )
            code, stdout, stderr = run_bolsig(bolsig_path, script_path, work_dir=run_dir, timeout=180)
            output_file = run_dir / output_name
            st.session_state["bolsig_run_dir"] = str(run_dir)
            st.session_state["bolsig_stdout"] = stdout
            st.session_state["bolsig_stderr"] = stderr
            st.session_state["bolsig_code"] = code
            st.session_state["bolsig_input"] = str(script_path)
            st.session_state["bolsig_output"] = str(output_file)
            if code == 0 and output_file.exists():
                parsed = parse_bolsig_output(output_file)
                st.session_state["bolsig_parsed"] = parsed
                st.session_state["bolsig_is_demo"] = False
                st.success(f"BOLSIG+ finished and output was parsed: {output_file}")
            else:
                st.warning("BOLSIG+ did not produce a parsed output file. Check the logs in Outputs / Logs.")
                st.session_state["bolsig_parsed"] = demo_bolsig
                st.session_state["bolsig_is_demo"] = True
        except Exception as exc:
            st.error(f"BOLSIG+ run failed: {exc}")
            st.session_state["bolsig_parsed"] = demo_bolsig
            st.session_state["bolsig_is_demo"] = True

    uploaded_bolsig_output = st.file_uploader("Or upload an existing BOLSIG+ output file to parse", type=["txt", "dat"], key="bolsig_output_upload")
    if uploaded_bolsig_output is not None:
        out_path = BOLSIG_OUTPUT_DIR / uploaded_bolsig_output.name
        out_path.write_bytes(uploaded_bolsig_output.getbuffer())
        st.session_state["bolsig_parsed"] = parse_bolsig_output(out_path)
        st.session_state["bolsig_is_demo"] = False
        st.success(f"Parsed uploaded BOLSIG+ output: {out_path.name}")

    parsed = st.session_state.get("bolsig_parsed", demo_bolsig)
    if st.session_state.get("bolsig_is_demo", True):
        demo_status("BOLSIG+ executable output is not active.")
    eedf_parsed = with_demo_eedf_if_missing(parsed, demo_bolsig)
    if not st.session_state.get("bolsig_is_demo", True) and parsed.get("eedf", pd.DataFrame()).empty:
        st.info("BOLSIG+ ran and produced transport/rate tables. Its saved output did not include an EEDF table, so the EEDF plot below uses the demo curve.")
    st.plotly_chart(plot_eedf(eedf_parsed), width="stretch")
    cols = st.columns(2)
    with cols[0]:
        st.subheader("Transport")
        transport = parsed.get("transport", pd.DataFrame())
        st.dataframe(transport, width="stretch", hide_index=True)
    with cols[1]:
        st.subheader("Rate Coefficients")
        rates = parsed.get("rates", pd.DataFrame())
        st.dataframe(rates.head(30) if isinstance(rates, pd.DataFrame) else rates, width="stretch", hide_index=True)

with tab_zd:
    st.subheader("Run Or Parse ZDPlasKin")
    note("This does not invent a chemistry file. It runs an existing ZDPlasKin/case executable or parses an output file you already produced.")
    bolsig_for_demo = st.session_state.get("bolsig_parsed", demo_bolsig)
    demo_rates = bolsig_for_demo.get("rates", pd.DataFrame()) if isinstance(bolsig_for_demo, dict) else pd.DataFrame()
    demo_zd = make_demo_zdplaskin_parsed(
        rates=demo_rates,
        gas_temperature_k=gas_temperature_k,
        pressure_torr=pressure_torr,
    )

    run_zd_button = st.button("Run selected ZDPlasKin executable", type="primary")
    if run_zd_button:
        try:
            result, cwd, cmd = run_existing_zdplaskin_executable(
                zdplaskin_exe,
                zdplaskin_work_dir,
                pass_case_argument=pass_case_argument,
                case_argument=zd_case_argument,
                timeout=300,
            )
            st.session_state["zd_cmd"] = " ".join(cmd)
            st.session_state["zd_cwd"] = str(cwd)
            st.session_state["zd_stdout"] = result.stdout
            st.session_state["zd_stderr"] = result.stderr
            st.session_state["zd_code"] = result.returncode
            output_file, parsed_zd, parse_errors = parse_newest_zdplaskin_output(cwd)
            st.session_state["zd_parse_errors"] = "\n".join(parse_errors)
            if parsed_zd is not None:
                st.session_state["zd_output"] = str(output_file)
                st.session_state["zd_parsed"] = parsed_zd
                st.session_state["zd_is_demo"] = False
                st.success(
                    f"ZDPlasKin finished with exit code {result.returncode} and parsed {output_file.name}."
                )
            else:
                st.warning(
                    f"ZDPlasKin finished with exit code {result.returncode}, but no parseable output file was found."
                )
                st.session_state["zd_output"] = "not parsed"
                st.session_state["zd_parsed"] = demo_zd
                st.session_state["zd_is_demo"] = True
        except Exception as exc:
            st.error(f"ZDPlasKin run failed: {exc}")
            st.session_state["zd_parsed"] = demo_zd
            st.session_state["zd_is_demo"] = True

    output_candidates = possible_output_files(zdplaskin_work_dir)
    if output_candidates:
        candidate_names = [str(path) for path in output_candidates[:20]]
        selected_output = st.selectbox("Parse a detected output file", candidate_names)
        if st.button("Parse selected ZDPlasKin output"):
            try:
                parsed_zd = parse_zdplaskin_output(selected_output)
                st.session_state["zd_parsed"] = parsed_zd
                st.session_state["zd_is_demo"] = False
                st.success("Parsed selected ZDPlasKin output.")
            except Exception as exc:
                st.error(f"Could not parse selected output: {exc}")
                st.session_state["zd_parsed"] = demo_zd
                st.session_state["zd_is_demo"] = True

    uploaded_zd_output = st.file_uploader("Or upload a ZDPlasKin output table", type=["txt", "dat", "csv", "out"], key="zd_output_upload")
    if uploaded_zd_output is not None:
        out_path = ZDPLASKIN_OUTPUT_DIR / uploaded_zd_output.name
        out_path.write_bytes(uploaded_zd_output.getbuffer())
        try:
            st.session_state["zd_parsed"] = parse_zdplaskin_output(out_path)
            st.session_state["zd_is_demo"] = False
            st.success(f"Parsed uploaded ZDPlasKin output: {out_path.name}")
        except Exception as exc:
            st.error(f"Could not parse uploaded ZDPlasKin output: {exc}")
            st.session_state["zd_parsed"] = demo_zd
            st.session_state["zd_is_demo"] = True

    zd_parsed = st.session_state.get("zd_parsed", demo_zd)
    if st.session_state.get("zd_is_demo", True):
        demo_status("ZDPlasKin executable output is not active.")
    st.plotly_chart(plot_species(zd_parsed), width="stretch")
    st.dataframe(zd_parsed["selected"], width="stretch", hide_index=True, height=260)

with tab_outputs:
    st.subheader("Run Folders And Logs")
    log_cols = st.columns(2)
    with log_cols[0]:
        st.write("BOLSIG+")
        st.code(f"Run folder: {st.session_state.get('bolsig_run_dir', 'not run yet')}")
        st.code(f"Input: {st.session_state.get('bolsig_input', 'not created yet')}")
        st.code(f"Output: {st.session_state.get('bolsig_output', 'not created yet')}")
        st.code(f"Exit code: {st.session_state.get('bolsig_code', 'not run yet')}")
        st.text_area("BOLSIG+ stdout", st.session_state.get("bolsig_stdout", ""), height=160)
        st.text_area("BOLSIG+ stderr", st.session_state.get("bolsig_stderr", ""), height=160)
    with log_cols[1]:
        st.write("ZDPlasKin")
        st.code(f"Command: {st.session_state.get('zd_cmd', 'not run yet')}")
        st.code(f"Working folder: {st.session_state.get('zd_cwd', 'not run yet')}")
        st.code(f"Parsed output: {st.session_state.get('zd_output', 'not parsed yet')}")
        st.code(f"Exit code: {st.session_state.get('zd_code', 'not run yet')}")
        st.text_area("ZDPlasKin stdout", st.session_state.get("zd_stdout", ""), height=160)
        st.text_area("ZDPlasKin stderr", st.session_state.get("zd_stderr", ""), height=160)
        st.text_area("ZDPlasKin parse notes", st.session_state.get("zd_parse_errors", ""), height=120)
