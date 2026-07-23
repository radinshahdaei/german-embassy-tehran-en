# Web Mirror

Crawl any website, extract readable content, machine-translate it via a local [LibreTranslate](https://libretranslate.com) instance, and generate a static, searchable mirror.

## Quick start

**Requirements:** Python 3.10+

```bash
git clone <this-repo>
cd <this-repo>
./scripts/run.sh
```

Then open `http://localhost:8080`.

The `site/` directory is generated locally and is not checked into the repository.

**Live mirror:** [radinshahdaei.github.io/german-embassy-tehran-en](https://radinshahdaei.github.io/german-embassy-tehran-en/) — an English mirror of the German Embassy in Tehran.

## What it does

- Crawls pages under a configurable path prefix, respecting `robots.txt` by default.
- Extracts readable content — strips scripts, forms, navigation, social embeds, and media.
- Translates block-by-block via LibreTranslate, caching results in SQLite.
- Generates a static website with rewritten internal links, client-side full-text search, and expandable originals on each page.

## Configuration

Copy and edit `config.yaml`. Every field can be overridden with an environment variable (`MIRROR_*` — see `web_mirror/config.py` for the full list). Use `--config` to point to an alternate file.

### Example: German Embassy Tehran

```yaml
start_url: https://teheran.diplo.de/ir-de
path_prefix: /ir-de
source_lang: de
target_lang: en
site_title: "German Embassy Tehran"
source_attribution: "Auswärtiges Amt"
source_language_label: "German"
generic_h1_patterns:
  - "Willkommen auf den Seiten des Auswärtigen Amts"
  - "Navigation und Service"
title_suffix_regex: '\s+-\s+Auswärtiges Amt\s*$'
excluded_path_segments:
  - /suche
  - /search
  - /kontaktformular
  - /newsletter
```

## Manual setup

Use two terminals — one for the translator, one for the mirror.

```bash
# Terminal 1 — start LibreTranslate
pip install libretranslate
libretranslate --host 0.0.0.0 --port 5001 --load-only de,en --disable-web-ui

# Terminal 2 — install and run the mirror
pip install -e '.[test]'
web-mirror doctor --strict       # confirm translator is reachable
web-mirror crawl                 # fetch, translate, render
web-mirror serve --port 8080     # browse at http://localhost:8080
```

Stop the translator with `pkill -f libretranslate`.

## Commands

```bash
web-mirror crawl --max-pages 10   # trial run, 10 pages
web-mirror crawl --refresh        # re-fetch all pages
web-mirror render                 # regenerate site from cache only
web-mirror doctor                 # inspect database and translator status
web-mirror serve --port 8080      # serve the generated site
web-mirror --config my-site.yaml crawl   # use an alternate config

pytest -q                         # run tests
```

## Output

| File | Contents |
| --- | --- |
| `site/index.html` | Landing page with search and card grid |
| `site/pages/*.html` | Individual translated pages |
| `site/search.json` | Client-side full-text search index |
| `site/mirror.json` | Generation metadata |
| `data/mirror.db` | SQLite page and translation cache |

## How it works

- **Crawler** — BFS queue from `start_url`, scoped to `path_prefix`. Respects `robots.txt` and crawl delay.
- **Extractor** — BeautifulSoup-based: strips scripts, forms, nav, media. Whitelists semantic HTML tags.
- **Translator** — LibreTranslate HTTP client with batch translation and per-block SQLite caching.
- **Storage** — SQLite (WAL mode): `pages` table and `translations` cache table.
- **Renderer** — Jinja2 static site generator with internal link rewriting and client-side full-text search.

## Disclaimer

The translated text is machine-generated and may contain errors. The source site can change after a crawl. Always consult the linked official page before relying on any information — especially for legal, financial, medical, or travel-related content.

## License

MIT License — see [LICENSE](LICENSE). Source content remains attributable to the original publisher. Review the official site's terms before redistributing a generated mirror.
