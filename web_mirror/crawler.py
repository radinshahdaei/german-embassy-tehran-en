from __future__ import annotations

import logging
import time
import urllib.robotparser
from collections import deque
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import _now
from .config import Settings
from .extract import extract_page
from .storage import PageRecord, Storage
from .translate import LibreTranslateClient, TranslationError, translate_document, translate_plain_text
from .urls import is_crawlable, normalize_url

LOGGER = logging.getLogger(__name__)
MAX_HTML_BYTES = 5 * 1024 * 1024


class Crawler:
    def __init__(self, settings: Settings, storage: Storage, translator: LibreTranslateClient):
        self.settings = settings
        self.storage = storage
        self.translator = translator
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.user_agent,
            "Accept-Language": "de,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml",
        })
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=1,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self.robots = self._load_robots()

    def crawl(self, refresh: bool = False, max_pages: int | None = None) -> dict[str, int]:
        start = normalize_url(self.settings.start_url)
        limit = self.settings.max_pages if max_pages is None else max_pages
        queue: deque[str] = deque([start])
        queued = {start}
        processed = 0

        while queue and (limit <= 0 or processed < limit):
            url = queue.popleft()
            existing = self.storage.get_page(url)
            if existing and not refresh and existing.status in {"ok", "partial"}:
                LOGGER.info("Cached: %s", url)
                outgoing = existing.outgoing_links
            else:
                outgoing = self._fetch_translate_store(url)
                processed += 1
                if self.settings.crawl_delay > 0:
                    time.sleep(self.settings.crawl_delay)

            for link in outgoing:
                if link not in queued and is_crawlable(
                    link, self.settings.host, self.settings.path_prefix,
                    self.settings.excluded_path_segments,
                ):
                    queued.add(link)
                    queue.append(link)

        return self.storage.count_by_status()

    def _fetch_translate_store(self, url: str) -> list[str]:
        LOGGER.info("Fetching: %s", url)
        if self.robots and not self.robots.can_fetch(self.settings.user_agent, url):
            LOGGER.warning("Blocked by robots.txt: %s", url)
            self._store_error(url, None, "blocked", "Blocked by robots.txt")
            return []

        try:
            response = self.session.get(url, timeout=self.settings.request_timeout, stream=True)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                raise ValueError(f"Unsupported content type: {content_type}")
            body = _read_limited(response)
            encoding = response.encoding or "utf-8"
            html = body.decode(encoding, errors="replace")
        except Exception as exc:
            LOGGER.error("Fetch failed for %s: %s", url, exc)
            status = getattr(getattr(exc, "response", None), "status_code", None)
            self._store_error(url, status, "failed", str(exc))
            return []

        extracted = extract_page(
            html, url, self.settings.host, self.settings.path_prefix,
            generic_h1_patterns=self.settings.generic_h1_patterns,
            title_suffix_regex=self.settings.title_suffix_regex,
            excluded_path_segments=self.settings.excluded_path_segments,
        )
        existing = self.storage.get_page(url)
        if existing and existing.content_hash == extracted.content_hash and existing.translated_html:
            LOGGER.info("Unchanged: %s", url)
            existing.fetched_at = _now()
            existing.outgoing_links = extracted.outgoing_links
            existing.http_status = response.status_code
            existing.error = ""
            self.storage.upsert_page(existing)
            return extracted.outgoing_links

        title_en = extracted.title
        translated_html = extracted.content_html
        status = "partial"
        error = ""
        try:
            title_en = translate_plain_text(extracted.title, self.translator, self.storage)
            result = translate_document(extracted.content_html, self.translator, self.storage)
            translated_html = result.html
            status = "ok" if result.complete else "partial"
            if result.failed_blocks:
                error = f"{result.failed_blocks} content blocks could not be translated"
        except TranslationError as exc:
            LOGGER.error("Page translation failed for %s: %s", url, exc)
            error = str(exc)

        self.storage.upsert_page(PageRecord(
            url=url,
            title_de=extracted.title,
            title_en=title_en,
            source_html=extracted.content_html,
            translated_html=translated_html,
            content_hash=extracted.content_hash,
            outgoing_links=extracted.outgoing_links,
            fetched_at=_now(),
            status=status,
            http_status=response.status_code,
            error=error,
        ))
        return extracted.outgoing_links

    def _store_error(self, url: str, http_status: int | None, status: str, error: str) -> None:
        existing = self.storage.get_page(url)
        self.storage.upsert_page(PageRecord(
            url=url,
            title_de=existing.title_de if existing else "",
            title_en=existing.title_en if existing else "",
            source_html=existing.source_html if existing else "",
            translated_html=existing.translated_html if existing else "",
            content_hash=existing.content_hash if existing else "",
            outgoing_links=existing.outgoing_links if existing else [],
            fetched_at=_now(),
            status=status,
            http_status=http_status,
            error=error,
        ))

    def _load_robots(self) -> urllib.robotparser.RobotFileParser | None:
        mode = self.settings.robots_mode.lower()
        if mode == "ignore":
            LOGGER.warning("robots.txt checks are disabled")
            return None
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(f"{self.settings.origin}/robots.txt")
        try:
            parser.read()
            return parser
        except Exception as exc:
            if mode == "strict":
                raise RuntimeError(f"Could not read robots.txt in strict mode: {exc}") from exc
            LOGGER.warning("Could not read robots.txt; continuing politely: %s", exc)
            return None


def _read_limited(response: requests.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_HTML_BYTES:
            raise ValueError(f"HTML response exceeds {MAX_HTML_BYTES} bytes")
        chunks.append(chunk)
    return b"".join(chunks)
