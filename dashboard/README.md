# Dashboard Notes

`app.py` is the Streamlit entrypoint for the deuterium plasma modeling workflow dashboard.

Run from the repository root:

```powershell
streamlit run dashboard/app.py
```

The app reads LXCat `.txt` files from `data/lxcat/`, generates clearly labeled demo BOLSIG+ and ZDPlasKin outputs when solver paths are not configured, and writes demo CSVs to:

- `data/bolsig_outputs/`
- `data/zdplaskin_outputs/`

Use the sidebar to set:

- LXCat input file
- Gas temperature
- Pressure
- Reduced electric field `E/N`
- Optional BOLSIG+ executable path
- Optional ZDPlasKin executable and case path

The dashboard is intentionally separate from the bundled ZDPlasKin installations and does not overwrite those directories.
