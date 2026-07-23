# Developer Guide

This document describes the internals of `web-mirror` — how the pieces fit together, where to make changes, and the design decisions behind them.

## Architecture

```
Source Website
     │
     ▼
┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────┐
│  Crawler  │───▶│ Extract  │───▶│   Translate   │───▶│ Storage  │───▶│  Render  │
│ (BFS)     │    │ (HTML)   │    │ (LibreTranslate)   │ (SQLite) │    │ (Jinja2) │
└──────────┘    └──────────┘    └──────────────┘    └──────────┘    └──────────┘
     │                                                    │               │
     │  robots.txt                                        │               │
     │  crawl delay                                       │  mirror.db    │  site/
     │  retry logic                                       │               │  ├── index.html
     │                                                    │               │  ├── pages/*.html
     ▼                                                    │               │  ├── search.json
  Config ◀────────────────────────────────────────────────┘               │  ├── mirror.json
(config.yaml)                                                             │  └── static/
                                                                          │
                                                                          ▼
                                                                     ┌──────────┐
                                                                     │  Server  │
                                                                     │ (stdlib) │
                                                                     └──────────┘
```

### Data flow, step by step

1. **Crawler** (`crawler.py`) runs a BFS queue starting from `start_url`. For each URL:
   - Skips if already cached and unchanged (unless `--refresh`)
   - Checks `robots.txt` (unless mode is `ignore`)
   - Fetches the page via `requests.Session` with retry logic
2. **Extract** (`extract.py`) parses the HTML with BeautifulSoup:
   - Finds the real page title (skipping configurable generic h1 patterns)
   - Strips scripts, forms, nav, iframes, canvas, svg, video, audio
   - Replaces images with `[Image: alt]` text spans
   - Whitelists only semantic HTML tags (see `ALLOWED_TAGS`)
   - Discovers outgoing links in the crawl scope
3. **Translate** (`translate.py`) sends content blocks to LibreTranslate:
   - Splits content into block-level elements (`<p>`, `<h1>`-`<h6>`, `<li>`, etc.)
   - Checks SQLite cache per block (SHA-256 keyed on provider + langs + source text)
   - Batches uncached blocks (24 at a time) and sends to the LibreTranslate API
   - Retries up to 5 times with exponential backoff
4. **Storage** (`storage.py`) persists everything to SQLite (WAL mode):
   - `pages` table: one row per URL with both German and English HTML
   - `translations` table: content-addressable translation cache
5. **Render** (`render.py`) generates a static site with Jinja2:
   - Rewrites internal links to relative paths
   - Marks external links with `target="_blank"`
   - Flags crawlable-but-not-mirrored links with `.not-mirrored` class
   - Generates `search.json` for client-side full-text search
6. **Serve** (`server.py`) serves the static site via stdlib `ThreadingTCPServer`

## Development setup

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with test dependencies
pip install -e '.[test]'

# Start LibreTranslate (separate terminal or background)
libretranslate --host 0.0.0.0 --port 5001 --load-only de,en --disable-web-ui

# Run the tool
web-mirror doctor --strict
web-mirror crawl --max-pages 10
web-mirror serve --port 8080
```

## Module map

```
web_mirror/
├── __init__.py      # Package docstring, version, shared _now() utility
├── __main__.py      # python -m web_mirror entry point
├── cli.py           # argparse: crawl, render, doctor, serve subcommands
├── config.py        # Settings dataclass, YAML + env var loading
├── crawler.py       # BFS crawl loop, HTTP session, robots.txt
├── extract.py       # BeautifulSoup HTML parsing and sanitization
├── translate.py     # LibreTranslate HTTP client, batch translation, caching
├── storage.py       # SQLite schema, PageRecord, CRUD operations
├── render.py        # Jinja2 static site generator, link rewriting
├── urls.py          # URL normalization, crawl-scope gating, filename generation
├── server.py        # Stdlib HTTP server for the generated site
├── templates/
│   ├── index.html   # Landing page: hero, search, card grid
│   └── page.html    # Individual page: content + expandable original
└── static/
    ├── style.css    # Design system (CSS custom properties, responsive)
    └── search.js    # Client-side full-text search over search.json
```

### Module dependency graph

```
cli.py ──────▶ config.py, crawler.py, render.py, server.py, storage.py, translate.py
crawler.py ──▶ config.py, extract.py, storage.py, translate.py, urls.py
extract.py ──▶ urls.py
translate.py ▶ extract.py, storage.py
render.py ───▶ config.py, storage.py, urls.py
server.py ─── (stdlib only)
urls.py ───── (stdlib only)
storage.py ── (stdlib + sqlite3)
config.py ─── (stdlib + PyYAML)
```

## Configuration system

Settings are loaded from `config.yaml` with environment variable overrides. The priority is:

1. Environment variable (if set and non-empty)
2. `config.yaml` value
3. Hardcoded default (empty string / empty list / 0)

### Adding a new config field

1. Add the field to `config.yaml` with a sensible default
2. Add a `MIRROR_*` entry to `_ENV_MAP` in `config.py`
3. Add the field to the `Settings` dataclass
4. Add parsing in `Settings.from_yaml()` — use `_resolve()` for scalar fields, `_resolve_list()` for list fields
5. Thread the field through to the module that needs it

List fields in env vars are comma-separated:
```bash
export MIRROR_EXCLUDED_PATH_SEGMENTS="/suche,/search,/newsletter"
```

## Database schema

### `pages` table

| Column | Type | Description |
|---|---|---|
| `url` | TEXT PK | Normalized URL (no query string, no fragment) |
| `title_de` | TEXT | Original-language title |
| `title_en` | TEXT | Translated title |
| `source_html` | TEXT | Extracted original HTML |
| `translated_html` | TEXT | Machine-translated HTML |
| `content_hash` | TEXT | SHA-256 of extracted HTML (change detection) |
| `outgoing_links` | TEXT | JSON array of crawled URLs |
| `fetched_at` | TEXT | ISO 8601 timestamp |
| `status` | TEXT | `ok`, `partial`, `failed`, `blocked` |
| `http_status` | INTEGER | HTTP status code (or NULL) |
| `error` | TEXT | Error description (or empty) |

### `translations` table

| Column | Type | Description |
|---|---|---|
| `cache_key` | TEXT PK | SHA-256 of `provider\0source_lang\0target_lang\0source_text` |
| `source_lang` | TEXT | Source language code |
| `target_lang` | TEXT | Target language code |
| `source_text` | TEXT | Original text block |
| `translated_text` | TEXT | Translated text block |
| `provider` | TEXT | Translation provider name |
| `created_at` | TEXT | ISO 8601 timestamp |

## Content extraction

### Tag whitelist

Only ~50 semantic HTML tags survive extraction. The full list is in `ALLOWED_TAGS` (extract.py). Everything else gets unwrapped (children kept, tag removed).

### Stripped elements

Scripts, styles, forms, buttons, inputs, selects, textareas, iframes, canvas, SVG, video, audio, nav, and elements with `role="navigation"` or `aria-hidden="true"` are removed entirely.

### Image handling

`<img>` tags are replaced with `[Image: alt text]` text spans. If the image has a `src`, the span is wrapped in a link to the original image URL.

### Title extraction

The algorithm finds the page title by:
1. Collecting all `<h1>` texts, excluding those matching `generic_h1_patterns`
2. Taking the last remaining `<h1>` (page content headings, not site chrome)
3. Falling back to `<title>` with `title_suffix_regex` stripped
4. Final fallback: `"Untitled page"`

### Link discovery

`discover_links()` finds all `<a href>` links, normalizes them, and filters by:
- Same host as `start_url`
- Under `path_prefix`
- Not a binary file suffix (PDF, images, archives, etc.)
- Not matching any `excluded_path_segments`

## Translation pipeline

### Block-level translation

Rather than translating entire pages, the system identifies block-level elements (headings, paragraphs, list items, table cells — see `BLOCK_TAGS` in extract.py) and translates each independently. This:
- Maximizes cache reuse (shared boilerplate blocks translate once)
- Makes translation failures granular (one bad block doesn't lose the whole page)
- Keeps LibreTranslate request sizes manageable

### Caching

Translation cache keys are SHA-256 hashes of `provider\0source_lang\0target_lang\0source_text`. The null byte delimiter prevents collisions between different inputs that would concatenate identically. Cached translations survive database rebuilds (the `translations` table is independent of `pages`).

### Retry logic

The LibreTranslate client retries up to 5 times with exponential backoff (1s, 2s, 4s, 8s). It retries on connection errors, HTTP errors, and unexpected response shapes.

## Link rewriting in the static site

`render.py` `_rewrite_links()` handles three cases:

| Link target | Behavior |
|---|---|
| Mirrored page (in `mapping`) | Rewritten to relative path (`../pages/abc123.html`) |
| External URL (different domain) | Kept as-is, `target="_blank"`, `rel="noopener noreferrer"` |
| Internal but not mirrored | Kept as-is, `.not-mirrored` class, `target="_blank"`, tooltip explaining it wasn't included |

## Testing

```bash
# Run all tests
pytest -q

# Run a single test file
pytest tests/test_extract.py -q

# Run with verbose output
pytest -v
```

### Test structure

| File | What it tests |
|---|---|
| `tests/test_extract.py` | HTML extraction: title detection, content sanitization, image replacement, link discovery |
| `tests/test_urls.py` | URL normalization, crawl scope gating, binary suffix exclusion, path segment exclusion, filename generation |
| `tests/test_render.py` | End-to-end rendering with two pages: landing page generation, link rewriting, cross-page references |
| `tests/fixture.html` | Sample German HTML page used by extraction tests |

Tests use `tmp_path` for isolation (render test) and in-memory config (all tests). No external services are needed.

## Common development tasks

### Adding a new CLI subcommand

1. Add a subparser in `cli.py` `build_parser()`
2. Add the handler in `cli.py` `main()`
3. If it needs new behavior, implement it in the relevant module

### Supporting a new translation provider

1. Create a new client class following the `LibreTranslateClient` pattern
2. Add a `provider_name` attribute
3. Implement `health()` and `translate_batch()` methods
4. Update `cli.py` to instantiate based on config

### Changing the static site design

- CSS: edit `web_mirror/static/style.css` (design tokens are CSS custom properties in `:root`)
- HTML structure: edit `web_mirror/templates/index.html` and `page.html`
- Search behavior: edit `web_mirror/static/search.js`

After any template/static change, run `web-mirror render` to regenerate the site.

### Crawling a new website

Create a new config file (e.g., `my-site.yaml`):

```yaml
start_url: https://example.com/docs
path_prefix: /docs
source_lang: en
target_lang: fr
site_title: "Example Docs"
source_attribution: "Example Inc."
source_language_label: "English"
translator_url: http://localhost:5001
```

Then:
```bash
web-mirror --config my-site.yaml doctor --strict
web-mirror --config my-site.yaml crawl --max-pages 5
web-mirror --config my-site.yaml serve --port 8080
```

## Design decisions

### Why SQLite instead of files on disk?

SQLite with WAL mode gives us atomic writes, concurrent reads during crawls, and structured queries (e.g., "give me all pages with status=ok ordered by title"). The translation cache is content-addressable, which SQLite's B-tree indexes handle efficiently.

### Why block-level translation instead of full-page?

Page-level translation would lose the cache whenever any part of a page changes. Block-level means that if only one paragraph changes, only that paragraph is re-translated. This is critical for incremental crawls where most content is unchanged.

### Why a content hash instead of HTTP ETags?

ETags are server-controlled and may change for reasons unrelated to content (e.g., CDN configuration). A SHA-256 of the extracted HTML reliably detects meaningful changes regardless of HTTP headers.

### Why strip query strings from URLs?

Many sites use query strings for analytics (`?utm_source=...`), session state (`?sid=...`), or UI state (`?tab=2`). Stripping them prevents duplicate pages while preserving the canonical URL. This is configurable only by editing `urls.py` — there's no config flag for it because the behavior is almost always desired.

### Why single-quoted YAML strings for regex patterns?

YAML double-quoted strings process backslash escapes (`\s` → space). Single-quoted strings preserve backslashes literally, which is what regex patterns need. Always use single quotes for `title_suffix_regex` in config files.

## Known limitations

- **Single-language pair per crawl**: LibreTranslate is loaded with one language pair (`--load-only de,en`). Multi-language sites need separate LibreTranslate instances or a different translation provider.
- **No JavaScript rendering**: The crawler fetches raw HTML. JavaScript-rendered content is invisible. For SPAs, a headless browser would be needed.
- **No incremental sitemap**: The BFS crawler discovers links organically. There's no sitemap.xml parsing. Sites with orphan pages may miss content.
- **Port 5000 conflict on macOS**: macOS ControlCenter often binds port 5000, which is LibreTranslate's default. The project defaults to port 5001.
- **LibreTranslate dependency clash**: LibreTranslate pins older versions of `requests` and `beautifulsoup4`. Using two venvs (one for LibreTranslate, one for web-mirror) is the cleanest workaround. The `run.sh` script handles this by installing both in sequence.
