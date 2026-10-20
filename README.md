# drive-slower

Cost-per-km model for choosing a highway cruising speed: time, fuel, refuelling stops,
maintenance, crash risk and (optionally) CO2.

```bash
uv run python -m drive_slower                    # text report
uv run marimo run demo/speed_demo.py             # interactive demo (http://localhost:2718)
uv run marimo edit demo/speed_demo.py            # edit the demo notebook
uv run pytest
```

### Static build

`scripts/build_static.sh` bundles the project as a wheel and exports the demo to
`build/wasm`, a server-free page that runs Python in the browser (WebAssembly). It
takes ~30 s to load the first time. Serve it with any static host, e.g.
`python3 -m http.server 2719 --directory build/wasm`.

- `speed_model.py` — the model, optimiser and Monte Carlo.
- `scenarios.py` — preset vehicles, roads, prices and the private/social perspectives,
  with notes on which inputs are sourced and which are estimates.
- `curves.py` / `charts.py` — chart data and Altair charts used by the demo.
