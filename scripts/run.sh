#!/usr/bin/env bash
set -eu

# ── Check prerequisites ───────────────────────────────────
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required." >&2; exit 1; }

# ── Install if needed ─────────────────────────────────────
if ! python3 -c "import libretranslate" 2>/dev/null; then
  echo "Installing LibreTranslate…"
  pip install libretranslate
fi
if ! python3 -c "import web_mirror" 2>/dev/null; then
  echo "Installing web-mirror…"
  pip install -e .
fi

# ── Start translator ──────────────────────────────────────
# Port is read from config.yaml (default: 5001).
TRANSLATOR_PORT=$(python3 -c "import yaml; print(yaml.safe_load(open('config.yaml'))['translator_url'].split(':')[-1])" 2>/dev/null || echo "5001")

cleanup() {
  if [ -n "${TRANSLATOR_PID:-}" ] && kill -0 "$TRANSLATOR_PID" 2>/dev/null; then
    kill "$TRANSLATOR_PID" 2>/dev/null || true
    wait "$TRANSLATOR_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "Starting LibreTranslate on port $TRANSLATOR_PORT…"
libretranslate --host 0.0.0.0 --port "$TRANSLATOR_PORT" \
  --load-only de,en --disable-web-ui &
TRANSLATOR_PID=$!

# ── Wait for translator ───────────────────────────────────
echo "Waiting for translator to become ready…"
TRANSLATOR_URL="http://localhost:${TRANSLATOR_PORT}"
until curl -s "${TRANSLATOR_URL}/frontend/settings" >/dev/null 2>&1; do
  sleep 3
done
echo "Translator is ready."

# ── Verify ────────────────────────────────────────────────
web-mirror doctor --strict

# ── Crawl, translate, render ──────────────────────────────
web-mirror crawl

# ── Serve ─────────────────────────────────────────────────
echo ""
echo "Starting web server on http://localhost:8080"
web-mirror serve --port 8080
