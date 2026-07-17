# German Embassy Tehran — English Mirror

An unofficial, read-only English mirror of the German Embassy in Tehran's website, generated from `teheran.diplo.de/ir-de`.

The tool crawls the embassy's German-language pages, extracts the main content, translates it via a local [LibreTranslate](https://libretranslate.com) instance, and produces a static, searchable website in `site/`.

## Quick start

**Requirements:** Python 3.10+

```bash
# Clone and run — starts the translator, crawls, and serves on :8080
git clone https://github.com/radinshahdaei/german-embassy-tehran-en.git
cd german-embassy-tehran-en
./scripts/run.sh
```

Then open `http://localhost:8080`.

The repository already includes a pre-built mirror in `site/`, so you can also browse immediately without crawling:

```bash
python3 -m http.server 8080 -d site
```

## How it works

- Crawls only pages under `/ir-de` on `teheran.diplo.de`, respecting `robots.txt` by default.
- Extracts readable content, stripping scripts, forms, navigation, social embeds, and media.
- Translates from German to English block-by-block via LibreTranslate, caching results in SQLite.
- Generates a static website with rewritten internal links, client-side full-text search, and expandable German originals on each page.

## Manual setup

Use two terminals — one for the translator, one for the mirror.

```bash
# Terminal 1 — start LibreTranslate
pip install libretranslate
libretranslate --host 0.0.0.0 --port 5001 --load-only de,en --disable-web-ui

# Terminal 2 — install and run the mirror
pip install -e .
teheran-mirror doctor --strict      # confirm translator is reachable
teheran-mirror crawl                # fetch, translate, render
teheran-mirror serve --port 8080    # browse at http://localhost:8080
```

Stop the translator with `pkill -f libretranslate`.

## Commands

```bash
teheran-mirror crawl --max-pages 10   # trial run, 10 pages
teheran-mirror crawl --refresh        # re-fetch all pages
teheran-mirror render                 # regenerate site from cache only
teheran-mirror doctor                 # inspect database and translator status
teheran-mirror serve --port 8080      # serve the generated site
teheran-mirror --config config.local.yaml crawl   # use an alternate config

pytest -q                             # run tests
```

## Configuration

Edit `config.yaml` at the project root. Defaults:

```yaml
start_url: https://teheran.diplo.de/ir-de
path_prefix: /ir-de
source_lang: de
target_lang: en
translator_url: http://localhost:5001
crawl_delay_seconds: 1.0
max_pages: 0               # 0 = unlimited
robots_mode: respect
data_dir: data
site_dir: site
```

Environment variables (`MIRROR_TRANSLATOR_URL`, `MIRROR_MAX_PAGES`, etc.) override YAML values. Use `--config` to point to an alternate file.

## Output

| File | Contents |
| --- | --- |
| `site/index.html` | Landing page with search and card grid |
| `site/pages/*.html` | Individual translated pages |
| `site/search.json` | Client-side full-text search index |
| `site/mirror.json` | Generation metadata |
| `data/mirror.db` | SQLite page and translation cache |

## Disclaimer

The English text is machine-generated and may contain errors. The source site can change after a crawl. Always consult the linked official German page before relying on any information — especially for visa requirements, travel warnings, legal procedures, fees, or contact details.

## License

This repository contains software and test fixtures only. Source content remains attributable to the German Federal Foreign Office (*Auswärtiges Amt*). Review the official site's terms before redistributing a generated mirror.

MIT License — see [LICENSE](LICENSE).
