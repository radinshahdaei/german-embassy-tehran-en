# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Web Mirror crawls a website, extracts content, machine-translates it via LibreTranslate, and generates a static translated website in `site/`. It is configurable for any website — see `config.yaml`.

## Commands

### Quick start

```bash
./scripts/run.sh           # macOS/Linux — one command, serves on :8080
./scripts/run.ps1          # Windows PowerShell
```

### Manual workflow (two terminals)

```bash
# Terminal 1 — start LibreTranslate:
pip install libretranslate
libretranslate --host 0.0.0.0 --port 5001 --load-only de,en --disable-web-ui

# Terminal 2 — run the mirror:
pip install -e '.[test]'
web-mirror doctor --strict
web-mirror crawl
web-mirror crawl --max-pages 10   # Trial run
web-mirror serve --port 8080
web-mirror render                 # Regenerate from cache only
web-mirror --config my-site.yaml crawl   # Custom config
```

### Makefile

```bash
make translator              # Start LibreTranslate on :5001
make crawl                   # Crawl + translate + render
make refresh                 # Re-fetch all pages
make serve                   # Serve on :8080
make test                    # Run pytest
make clean                   # Delete database + generated site
make stop                    # Kill LibreTranslate
```

### Tests

```bash
pytest -q                          # All tests
pytest tests/test_urls.py -q       # Single test file
```

## Architecture

**Data flow:** Source website → Crawler → Extract → Translate (via LibreTranslate) → Storage (SQLite) → Render → `site/` static HTML → Serve

**Key modules:**

| Module | Role |
|---|---|
| `web_mirror/cli.py` | argparse dispatch: `crawl`, `render`, `doctor`, `serve`; `--config` global flag |
| `web_mirror/config.py` | `Settings` dataclass loaded from `config.yaml` with env var overrides |
| `web_mirror/crawler.py` | BFS crawl queue; respects `robots.txt` and crawl delay; delegates to extract → translate → store |
| `web_mirror/extract.py` | BeautifulSoup HTML extraction: strips scripts/forms/nav, keeps main content, discovers crawlable links |
| `web_mirror/translate.py` | LibreTranslate HTTP client with health check, batch translation, per-block SQLite caching |
| `web_mirror/storage.py` | SQLite (WAL mode): `pages` table (URL, titles, HTML, status, links) and `translations` cache table |
| `web_mirror/render.py` | Jinja2 static site generator: `index.html` (card grid + search), per-page HTML, `search.json`, `mirror.json` |
| `web_mirror/urls.py` | URL normalization, crawl-scope gating, filename generation |
| `web_mirror/server.py` | Stdlib `http.server` (ThreadingTCPServer) for `site/` |

**Templates:** `web_mirror/templates/index.html` (landing page with search) and `page.html` (individual translated page with expandable originals).

**Static assets:** `web_mirror/static/style.css` and `search.js` (client-side full-text search over `search.json`).

## Configuration

All settings in `config.yaml` at the project root. Env vars (`MIRROR_*`) override YAML values. Use `--config` to point to an alternate file.

The config is site-agnostic — set `start_url`, `path_prefix`, `site_title`, `source_attribution`, `source_language_label`, and extraction/crawl tuning fields to match your target site.

Defaults use port 5001 for the translator (macOS ControlCenter often binds port 5000).

## Sharing the mirror

The generated `site/` directory is fully self-contained static HTML/CSS/JS. Zip it and send — the recipient only needs `python3 -m http.server 8080` to browse it.

## Testing

Three test files in `tests/`: `test_extract.py` (HTML content extraction), `test_urls.py` (URL normalization and crawl scope), `test_render.py` (static site generation and link rewriting). Uses a shared `tests/fixture.html` for HTML extraction tests.

No linter, formatter, or type checker is currently configured.

## Known issues

- **Port 5000 conflict on macOS**: macOS ControlCenter often binds port 5000. `config.yaml` defaults to port 5001 to avoid this.
- **Dependency clash**: LibreTranslate pins `requests==2.31.0` and `beautifulsoup4==4.9.3`; the mirror needs `>=2.32` and `>=4.12`. Install the mirror last to get working versions. For clean separation, use two venvs.
