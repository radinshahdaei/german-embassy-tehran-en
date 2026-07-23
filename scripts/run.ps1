$ErrorActionPreference = "Stop"

# ── Check prerequisites ───────────────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "Python 3 is required."
}

# ── Read translator port from config.yaml ─────────────────
try {
  $config = Get-Content config.yaml | python -c "import yaml,sys; print(yaml.safe_load(sys.stdin)['translator_url'].split(':')[-1])"
  $TRANSLATOR_PORT = $config.Trim()
} catch {
  $TRANSLATOR_PORT = "5001"
}

# ── Install if needed ─────────────────────────────────────
try { python -c "import libretranslate" } catch {
  Write-Host "Installing LibreTranslate…"
  pip install libretranslate
}
try { python -c "import web_mirror" } catch {
  Write-Host "Installing web-mirror…"
  pip install -e .
}

# ── Start translator ──────────────────────────────────────
$job = Start-Job -ScriptBlock {
  param($port)
  libretranslate --host 0.0.0.0 --port $port --load-only de,en --disable-web-ui
} -ArgumentList $TRANSLATOR_PORT

$TRANSLATOR_URL = "http://localhost:$TRANSLATOR_PORT"
Write-Host "Waiting for translator to become ready…"
do {
  Start-Sleep -Seconds 3
  try { $null = Invoke-WebRequest -Uri "$TRANSLATOR_URL/frontend/settings" -UseBasicParsing -TimeoutSec 3; $ready = $true } catch { $ready = $false }
} until ($ready)
Write-Host "Translator is ready."

# ── Verify ────────────────────────────────────────────────
web-mirror doctor --strict
if ($LASTEXITCODE -ne 0) { throw "Doctor check failed." }

# ── Crawl, translate, render ──────────────────────────────
web-mirror crawl
if ($LASTEXITCODE -ne 0) { throw "Crawl failed." }

# ── Serve ─────────────────────────────────────────────────
Write-Host ""
Write-Host "Starting web server on http://localhost:8080"
web-mirror serve --port 8080
