from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from . import _now
from typing import Iterator


@dataclass
class PageRecord:
    url: str
    title_de: str
    title_en: str
    source_html: str
    translated_html: str
    content_hash: str
    outgoing_links: list[str]
    fetched_at: str
    status: str
    http_status: int | None
    error: str


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS pages (
    url TEXT PRIMARY KEY,
    title_de TEXT NOT NULL DEFAULT '',
    title_en TEXT NOT NULL DEFAULT '',
    source_html TEXT NOT NULL DEFAULT '',
    translated_html TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL DEFAULT '',
    outgoing_links TEXT NOT NULL DEFAULT '[]',
    fetched_at TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    http_status INTEGER,
    error TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS translations (
    cache_key TEXT PRIMARY KEY,
    source_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    provider TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS pages_status_idx ON pages(status);
"""


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_page(self, url: str) -> PageRecord | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM pages WHERE url = ?", (url,)).fetchone()
        return self._row_to_page(row) if row else None

    def upsert_page(self, page: PageRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO pages (
                    url, title_de, title_en, source_html, translated_html,
                    content_hash, outgoing_links, fetched_at, status,
                    http_status, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title_de=excluded.title_de,
                    title_en=excluded.title_en,
                    source_html=excluded.source_html,
                    translated_html=excluded.translated_html,
                    content_hash=excluded.content_hash,
                    outgoing_links=excluded.outgoing_links,
                    fetched_at=excluded.fetched_at,
                    status=excluded.status,
                    http_status=excluded.http_status,
                    error=excluded.error
                """,
                (
                    page.url,
                    page.title_de,
                    page.title_en,
                    page.source_html,
                    page.translated_html,
                    page.content_hash,
                    json.dumps(page.outgoing_links, ensure_ascii=False),
                    page.fetched_at,
                    page.status,
                    page.http_status,
                    page.error,
                ),
            )

    def all_pages(self, statuses: tuple[str, ...] = ("ok", "partial")) -> list[PageRecord]:
        placeholders = ",".join("?" for _ in statuses)
        query = f"SELECT * FROM pages WHERE status IN ({placeholders}) ORDER BY title_en, url"
        with self.connect() as conn:
            rows = conn.execute(query, statuses).fetchall()
        return [self._row_to_page(row) for row in rows]

    def count_by_status(self) -> dict[str, int]:
        with self.connect() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS count FROM pages GROUP BY status").fetchall()
        return {row["status"]: row["count"] for row in rows}

    def get_translation(self, cache_key: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT translated_text FROM translations WHERE cache_key = ?", (cache_key,)
            ).fetchone()
        return row["translated_text"] if row else None

    def put_translation(
        self,
        cache_key: str,
        source_lang: str,
        target_lang: str,
        source_text: str,
        translated_text: str,
        provider: str,
    ) -> None:
        now = _now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO translations (
                    cache_key, source_lang, target_lang, source_text,
                    translated_text, provider, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    source_lang,
                    target_lang,
                    source_text,
                    translated_text,
                    provider,
                    now,
                ),
            )

    @staticmethod
    def _row_to_page(row: sqlite3.Row) -> PageRecord:
        return PageRecord(
            url=row["url"],
            title_de=row["title_de"],
            title_en=row["title_en"],
            source_html=row["source_html"],
            translated_html=row["translated_html"],
            content_hash=row["content_hash"],
            outgoing_links=json.loads(row["outgoing_links"] or "[]"),
            fetched_at=row["fetched_at"],
            status=row["status"],
            http_status=row["http_status"],
            error=row["error"],
        )
