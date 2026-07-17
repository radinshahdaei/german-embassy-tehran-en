from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from jinja2 import Environment, PackageLoader, select_autoescape

from .config import Settings
from .storage import PageRecord, Storage
from .urls import is_crawlable, local_filename, normalize_url


class Renderer:
    def __init__(self, settings: Settings, storage: Storage):
        self.settings = settings
        self.storage = storage
        self.env = Environment(
            loader=PackageLoader("embassy_mirror", "templates"),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_all(self) -> int:
        pages = self.storage.all_pages()
        self.settings.site_dir.mkdir(parents=True, exist_ok=True)
        pages_dir = self.settings.site_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        self._copy_static()

        mapping = {page.url: local_filename(page.url, self.settings.start_url) for page in pages}
        for page in pages:
            self._render_page(page, mapping)
        self._render_index(pages, mapping)
        self._write_search(pages, mapping)
        self._write_metadata(pages)
        return len(pages)

    def _render_page(self, page: PageRecord, mapping: dict[str, str]) -> None:
        current_filename = mapping[page.url]
        content = self._rewrite_links(page.translated_html, page.url, current_filename, mapping)
        original = self._rewrite_links(page.source_html, page.url, current_filename, mapping)
        template = self.env.get_template("page.html")
        html = template.render(
            title=page.title_en or page.title_de,
            title_de=page.title_de,
            content=content,
            original_content=original,
            source_url=page.url,
            fetched_at=_human_time(page.fetched_at),
            partial=page.status != "ok",
            error=page.error,
            home_href="../index.html" if current_filename.startswith("pages/") else "index.html",
            asset_prefix="../" if current_filename.startswith("pages/") else "",
        )
        destination = self.settings.site_dir / current_filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html, encoding="utf-8")

    def _render_index(self, pages: list[PageRecord], mapping: dict[str, str]) -> None:
        template = self.env.get_template("index.html")
        home_url = normalize_url(self.settings.start_url)
        home = next((p for p in pages if normalize_url(p.url) == home_url), None)
        cards = [
            {
                "title": page.title_en or page.title_de,
                "title_de": page.title_de,
                "href": mapping[page.url],
                "snippet": _snippet(BeautifulSoup(page.translated_html, "lxml").get_text(" ", strip=True)),
                "partial": page.status != "ok",
            }
            for page in pages
            if page is not home
        ]
        html = template.render(
            title="German Embassy Tehran — English mirror",
            home_title=(home.title_en or home.title_de) if home else "Embassy home page",
            home_href=mapping.get(home.url, "") if home else "",
            home_snippet=_snippet(BeautifulSoup(home.translated_html, "lxml").get_text(" ", strip=True), 360) if home else "",
            pages=cards,
            page_count=len(pages),
            generated_at=_human_time(datetime.now(timezone.utc).isoformat()),
        )
        (self.settings.site_dir / "index.html").write_text(html, encoding="utf-8")

    def _rewrite_links(
        self,
        html: str,
        page_url: str,
        current_filename: str,
        mapping: dict[str, str],
    ) -> str:
        soup = BeautifulSoup(f"<div id='content-root'>{html}</div>", "lxml")
        root = soup.find(id="content-root")
        assert root is not None
        current_dir = Path(current_filename).parent
        for anchor in root.find_all("a", href=True):
            href = anchor.get("href", "")
            parsed = urlsplit(href)
            fragment = parsed.fragment
            normalized = normalize_url(href, page_url)
            if normalized in mapping:
                target = Path(mapping[normalized])
                relative = os.path.relpath(target, current_dir or Path("."))
                anchor["href"] = relative.replace(os.sep, "/") + (f"#{fragment}" if fragment else "")
                anchor.attrs.pop("target", None)
            else:
                anchor["href"] = href
                if parsed.scheme in {"http", "https"}:
                    anchor["target"] = "_blank"
                    anchor["rel"] = "noopener noreferrer"
                    if is_crawlable(normalized, self.settings.host, self.settings.path_prefix):
                        anchor["class"] = "not-mirrored"
                        anchor["title"] = "This internal page was not included; open the official site"
        return "".join(str(child) for child in root.contents)

    def _copy_static(self) -> None:
        package_dir = Path(__file__).resolve().parent
        source = package_dir / "static"
        destination = self.settings.site_dir / "static"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)

    def _write_search(self, pages: list[PageRecord], mapping: dict[str, str]) -> None:
        records = []
        for page in pages:
            text = BeautifulSoup(page.translated_html, "lxml").get_text(" ", strip=True)
            records.append({
                "title": page.title_en or page.title_de,
                "title_de": page.title_de,
                "href": mapping[page.url],
                "text": text,
            })
        (self.settings.site_dir / "search.json").write_text(
            json.dumps(records, ensure_ascii=False), encoding="utf-8"
        )

    def _write_metadata(self, pages: list[PageRecord]) -> None:
        metadata = {
            "source": self.settings.start_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "page_count": len(pages),
            "language": self.settings.target_lang,
            "unofficial_machine_translation": True,
        }
        (self.settings.site_dir / "mirror.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )


def _snippet(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _human_time(value: str) -> str:
    if not value:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M %Z")
    except ValueError:
        return value
