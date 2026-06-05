from pathlib import Path
import json
import sys

from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.demo_bolsig_outputs import generate_demo_bolsig_outputs
from scripts.demo_zdplaskin_outputs import generate_demo_species_density
from scripts.parse_lxcat import parse_lxcat_file


LXCAT_FILE = ROOT / "data" / "lxcat" / "Cross section.txt"
OUT_DIR = ROOT / "presentation_static"
OUT_FILE = OUT_DIR / "index.html"
PLOTLY_FILE = OUT_DIR / "plotly.min.js"


def downsample_xy(df, max_points=450):
    if len(df) > max_points:
        step = max(1, len(df) // max_points)
        df = df.iloc[::step].copy()
    return {
        "x": [float(value) for value in df["energy"]],
        "y": [float(value) for value in df["cross_section"]],
    }


def dataframe_records(df, limit=None):
    if limit:
        df = df.head(limit)
    records = []
    for record in df.to_dict(orient="records"):
        clean = {}
        for key, value in record.items():
            try:
                if hasattr(value, "item"):
                    value = value.item()
            except Exception:
                pass
            clean[key] = value
        records.append(clean)
    return records


def build_payload():
    summary = parse_lxcat_file(LXCAT_FILE)
    blocks = summary["blocks"]
    demo_bolsig = generate_demo_bolsig_outputs(
        blocks,
        gas="D2",
        gas_temperature_k=300.0,
        pressure_torr=5.0,
        reduced_field_td=150.0,
    )
    species = generate_demo_species_density(
        rates=demo_bolsig["rates"],
        gas_temperature_k=300.0,
        pressure_torr=5.0,
    )
    selected_blocks = blocks[:8]
    return {
        "file": LXCAT_FILE.name,
        "process_count": len(blocks),
        "rows": summary["rows"],
        "database": summary.get("metadata", {}).get("database", "Laporta"),
        "cross_sections": [
            {
                "name": block["label"],
                **downsample_xy(block["data_frame"]),
            }
            for block in selected_blocks
        ],
        "processes": [
            {
                "type": block["collision_type"].title(),
                "process": block["process"],
                "threshold": block.get("threshold_eV"),
                "rows": block["rows"],
            }
            for block in blocks[:16]
        ],
        "eedf": {
            "x": [float(value) for value in demo_bolsig["eedf"]["energy_eV"]],
            "y": [float(value) for value in demo_bolsig["eedf"]["eedf"]],
        },
        "transport": dataframe_records(demo_bolsig["transport"]),
        "rates": dataframe_records(demo_bolsig["rates"], limit=12),
        "species": {
            "time": [float(value) for value in species["time_s"]],
            "series": {
                column: [float(value) for value in species[column]]
                for column in ["e", "D2", "D", "D+", "D2+", "D3+"]
            },
        },
    }


def build_html(payload):
    payload_json = json.dumps(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Deuterium Plasma Modeling Workflow</title>
  <script src="./plotly.min.js"></script>
  <style>
    :root {{
      color-scheme: light;
      --ink: #0f172a;
      --muted: #475569;
      --line: #dbe3ea;
      --panel: #ffffff;
      --bg: #f6f8fb;
      --teal: #0f766e;
      --gold: #b7791f;
      --blue: #2563eb;
      font-family: Inter, Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 56px; }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-left: 7px solid var(--teal);
      border-radius: 8px;
      padding: 24px 28px;
      box-shadow: 0 14px 34px rgba(15, 23, 42, 0.07);
    }}
    h1 {{ margin: 0 0 12px; font-size: clamp(32px, 5vw, 52px); line-height: 1.05; letter-spacing: 0; }}
    h2 {{ margin: 38px 0 14px; font-size: 24px; letter-spacing: 0; }}
    p {{ color: var(--muted); line-height: 1.55; font-size: 17px; }}
    .workflow {{ display: flex; gap: 10px; align-items: stretch; overflow-x: auto; margin: 22px 0 30px; }}
    .step {{ min-width: 160px; flex: 1; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .step small {{ color: var(--teal); display: block; font-weight: 800; letter-spacing: .08em; margin-bottom: 6px; }}
    .arrow {{ align-self: center; color: var(--gold); font-size: 24px; font-weight: 800; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 18px 0; }}
    .metric, .note, .table-wrap {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    .metric b {{ color: #64748b; display: block; font-size: 12px; letter-spacing: .09em; text-transform: uppercase; margin-bottom: 8px; }}
    .metric strong {{ font-size: 24px; }}
    .note {{ border-left: 4px solid var(--blue); color: var(--muted); }}
    .chart {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin: 14px 0 26px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #e5edf3; padding: 9px; text-align: left; vertical-align: top; }}
    th {{ color: #334155; background: #f8fafc; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .interpret {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .interpret div {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    .interpret p {{ font-size: 14px; margin: 8px 0 0; }}
    @media (max-width: 850px) {{
      .metrics, .grid, .interpret {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <h1>Deuterium Plasma Modeling Workflow:<br>LXCat &rarr; BOLSIG+ &rarr; ZDPlasKin</h1>
    <p>Collision cross sections, electron energy distributions, transport coefficients, reaction rates, and species-density evolution for a spherical neutron generator workflow.</p>
  </section>
  <section class="workflow">
    <div class="step"><small>01</small><b>LXCat Cross Sections</b></div><div class="arrow">&rarr;</div>
    <div class="step"><small>02</small><b>BOLSIG+</b></div><div class="arrow">&rarr;</div>
    <div class="step"><small>03</small><b>EEDF + Transport</b></div><div class="arrow">&rarr;</div>
    <div class="step"><small>04</small><b>Rate Coefficients</b></div><div class="arrow">&rarr;</div>
    <div class="step"><small>05</small><b>ZDPlasKin</b></div><div class="arrow">&rarr;</div>
    <div class="step"><small>06</small><b>Species Densities</b></div>
  </section>

  <h2>Step 1: LXCat Cross Sections</h2>
  <div class="note">LXCat supplies energy-dependent electron collision cross sections sigma(E), which define how likely each electron-impact process is as a function of electron energy.</div>
  <div class="metrics">
    <div class="metric"><b>Selected file</b><strong id="file"></strong></div>
    <div class="metric"><b>Processes</b><strong id="processCount"></strong></div>
    <div class="metric"><b>Rows</b><strong id="rows"></strong></div>
    <div class="metric"><b>Database</b><strong id="database"></strong></div>
  </div>
  <div class="chart" id="crossSectionPlot"></div>

  <div class="table-wrap">
    <table id="processTable"></table>
  </div>

  <h2>Step 2: BOLSIG+ Electron Kinetics</h2>
  <div class="note">Demo output until executable paths are configured. BOLSIG+ solves the Boltzmann equation for the electron energy distribution function f(E).</div>
  <div class="chart" id="eedfPlot"></div>

  <h2>Step 3: Transport And Rate Coefficients</h2>
  <p><b>k_i = integral sigma_i(E) v(E) f(E) dE</b></p>
  <div class="grid">
    <div class="table-wrap"><table id="transportTable"></table></div>
    <div class="table-wrap"><table id="rateTable"></table></div>
  </div>

  <h2>Step 4: ZDPlasKin Species Evolution</h2>
  <div class="note">Demo output until executable paths are configured. ZDPlasKin uses reaction rates to solve time-dependent species balance equations.</div>
  <div class="chart" id="speciesPlot"></div>

  <h2>Step 5: Interpretation</h2>
  <section class="interpret">
    <div><b>LXCat</b><p>Microscopic collision probabilities enter as cross sections that vary with electron energy.</p></div>
    <div><b>BOLSIG+</b><p>The Boltzmann solver converts those cross sections into electron-population behavior.</p></div>
    <div><b>Rates</b><p>Energy-dependent cross sections become reaction rates that drive source terms.</p></div>
    <div><b>ZDPlasKin</b><p>Species-balance equations evolve e, D2, D, D+, D2+, and D3+ densities over time.</p></div>
  </section>
</main>
<script>
const payload = {payload_json};
const colors = ["#0f766e", "#b7791f", "#2563eb", "#be123c", "#475569", "#15803d", "#0e7490", "#a16207"];
document.getElementById("file").textContent = payload.file;
document.getElementById("processCount").textContent = payload.process_count;
document.getElementById("rows").textContent = payload.rows.toLocaleString();
document.getElementById("database").textContent = payload.database;

function table(el, columns, rows) {{
  const head = "<tr>" + columns.map(c => `<th>${{c.label}}</th>`).join("") + "</tr>";
  const body = rows.map(row => "<tr>" + columns.map(c => `<td>${{row[c.key] ?? ""}}</td>`).join("") + "</tr>").join("");
  document.getElementById(el).innerHTML = head + body;
}}

Plotly.newPlot("crossSectionPlot", payload.cross_sections.map((s, i) => ({{
  x: s.x, y: s.y, name: s.name, type: "scatter", mode: "lines",
  line: {{ color: colors[i % colors.length], width: 2 }}
}})), {{
  title: "LXCat electron-impact cross sections",
  xaxis: {{ title: "Electron energy (eV)", type: "log" }},
  yaxis: {{ title: "Cross section (m2)", type: "log" }},
  paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff", margin: {{ t: 60, r: 20, b: 65, l: 70 }}
}}, {{ responsive: true }});

table("processTable", [
  {{ key: "type", label: "Type" }},
  {{ key: "process", label: "Process" }},
  {{ key: "threshold", label: "Threshold eV" }},
  {{ key: "rows", label: "Rows" }}
], payload.processes);

Plotly.newPlot("eedfPlot", [{{ x: payload.eedf.x, y: payload.eedf.y, type: "scatter", mode: "lines", fill: "tozeroy", line: {{ color: "#0f766e", width: 3 }} }}], {{
  title: "Electron energy distribution function",
  xaxis: {{ title: "Electron energy (eV)", type: "log" }},
  yaxis: {{ title: "f(E), normalized" }},
  paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff", margin: {{ t: 60, r: 20, b: 60, l: 70 }}
}}, {{ responsive: true }});

table("transportTable", [
  {{ key: "coefficient", label: "Transport Coefficient" }},
  {{ key: "value", label: "Value" }},
  {{ key: "unit", label: "Unit" }}
], payload.transport);

table("rateTable", [
  {{ key: "type", label: "Type" }},
  {{ key: "process", label: "Process" }},
  {{ key: "rate_coefficient_m3_s", label: "k (m3/s)" }}
], payload.rates);

Plotly.newPlot("speciesPlot", Object.entries(payload.species.series).map(([name, y], i) => ({{
  x: payload.species.time, y, name, type: "scatter", mode: "lines",
  line: {{ color: colors[i % colors.length], width: 3 }}
}})), {{
  title: "Species-density evolution",
  xaxis: {{ title: "Time (s)", type: "log" }},
  yaxis: {{ title: "Density (m-3)", type: "log" }},
  paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff", margin: {{ t: 60, r: 20, b: 60, l: 75 }}
}}, {{ responsive: true }});
</script>
</body>
</html>
"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLOTLY_FILE.write_text(get_plotlyjs(), encoding="utf-8")
    OUT_FILE.write_text(build_html(build_payload()), encoding="utf-8")
    print(OUT_FILE)


if __name__ == "__main__":
    main()
