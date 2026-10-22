#!/usr/bin/env bash
# Build a static, server-free copy of the demo into build/wasm.
set -euo pipefail
cd "$(dirname "$0")/.."
WHEEL=drive_slower-0.1.0-py3-none-any.whl
LIVE=${LIVE_URL:-https://andrewgordstewart.github.io/drive-slower}
OUT=build/wasm
rm -rf demo/public "$OUT"
uv build --wheel -o demo/public
uv run marimo export html-wasm demo/speed_demo.py -o "$OUT" --mode run

# Give each build's wheel its own URL, so a page always loads the wheel it was built
# with. GitHub Pages lets browsers cache both for 10 minutes; with a fixed URL a new
# page could get an old cached wheel, or the reverse.
hash=$(shasum -a 256 "$OUT/public/$WHEEL" | cut -c1-12)
mkdir -p "$OUT/public/$hash"
mv "$OUT/public/$WHEEL" "$OUT/public/$hash/$WHEEL"
sed -i.bak "s#$WHEEL#$hash/$WHEEL#g" "$OUT/index.html" && rm "$OUT/index.html.bak"
grep -q "$hash/$WHEEL" "$OUT/index.html" || {
  echo "error: wheel path not rewritten in $OUT/index.html" >&2
  exit 1
}

# Each deploy replaces the whole site. Keep the live site's wheel too, so a browser
# still holding the previous page can load it. Before hashed paths, it was public/.
if live=$(curl -fsS "$LIVE/"); then
  prev=$(grep -o "[0-9a-f]\{12\}/$WHEEL" <<<"$live" | head -1 || true)
  prev=${prev:-$WHEEL}
  if [[ "$prev" != "$hash/$WHEEL" ]]; then
    mkdir -p "$(dirname "$OUT/public/$prev")"
    curl -fsS "$LIVE/public/$prev" -o "$OUT/public/$prev" ||
      echo "warning: couldn't fetch the previous wheel ($prev)" >&2
  fi
else
  echo "warning: couldn't reach $LIVE; not keeping the previous wheel" >&2
fi

# marimo's export adds its generic notebook-assistant instructions; not ours to publish.
rm -f "$OUT/CLAUDE.md"

echo "Wheel: public/$hash/$WHEEL"
echo "Serve with: python3 -m http.server 2719 --directory $OUT"
