#!/usr/bin/env bash
# Build a static, server-free copy of the demo into build/wasm.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf demo/public build/wasm
uv build --wheel -o demo/public
uv run marimo export html-wasm demo/speed_demo.py -o build/wasm --mode run
echo "Serve with: python3 -m http.server 2719 --directory build/wasm"
