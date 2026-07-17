from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Settings
from .crawler import Crawler
from .render import Renderer
from .server import serve
from .storage import Storage
from .translate import LibreTranslateClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="teheran-mirror",
        description="Build and serve a local English text mirror of teheran.diplo.de/ir-de",
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to config.yaml (default: config.yaml)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl = subparsers.add_parser("crawl", help="Crawl, translate, and render the mirror")
    crawl.add_argument("--refresh", action="store_true", help="Refetch pages already in the cache")
    crawl.add_argument("--max-pages", type=int, default=None, help="Limit pages; 0 means no limit")
    crawl.add_argument("--render-only", action="store_true", help="Render existing cached pages without crawling")

    render = subparsers.add_parser("render", help="Render existing cached pages")
    render.add_argument("--clean", action="store_true", help="Reserved for compatibility")

    doctor = subparsers.add_parser("doctor", help="Check the local translator and stored mirror")
    doctor.add_argument("--strict", action="store_true", help="Return a failure code if translator is unavailable")

    server = subparsers.add_parser("serve", help="Serve the generated static site")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8080)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    settings = Settings.from_yaml(args.config)
    settings.ensure_directories()
    storage = Storage(settings.database_path)

    if args.command == "serve":
        serve(settings.site_dir, args.host, args.port)
        return 0

    renderer = Renderer(settings, storage)
    if args.command == "render":
        count = renderer.render_all()
        print(f"Rendered {count} page(s) into {settings.site_dir}")
        return 0

    translator = LibreTranslateClient(
        endpoint=settings.translator_url,
        source_lang=settings.source_lang,
        target_lang=settings.target_lang,
        api_key=settings.translator_api_key,
    )

    if args.command == "doctor":
        translator_ok = translator.health()
        print(f"Translator: {'ready' if translator_ok else 'unavailable'} ({settings.translator_url})")
        print(f"Database: {settings.database_path}")
        print(f"Stored pages: {storage.count_by_status() or '{}'}")
        return 1 if args.strict and not translator_ok else 0

    if args.command == "crawl":
        if args.render_only:
            count = renderer.render_all()
            print(f"Rendered {count} cached page(s) into {settings.site_dir}")
            return 0
        if not translator.health():
            print(
                "Translator is not ready. Start LibreTranslate first, then run this command again.\n"
                f"Expected endpoint: {settings.translator_url}",
                file=sys.stderr,
            )
            return 2
        crawler = Crawler(settings, storage, translator)
        statuses = crawler.crawl(refresh=args.refresh, max_pages=args.max_pages)
        count = renderer.render_all()
        print(f"Crawl status: {statuses}")
        print(f"Rendered {count} page(s) into {settings.site_dir}")
        return 0

    parser.error("Unknown command")
    return 2
