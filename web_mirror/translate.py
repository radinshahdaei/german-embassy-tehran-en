from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Iterable

import requests

from .extract import root_inner_html, translatable_blocks
from .storage import Storage

LOGGER = logging.getLogger(__name__)


class TranslationError(RuntimeError):
    pass


@dataclass
class TranslationResult:
    html: str
    complete: bool
    translated_blocks: int
    failed_blocks: int


class LibreTranslateClient:
    provider_name = "libretranslate"

    def __init__(
        self,
        endpoint: str,
        source_lang: str,
        target_lang: str,
        api_key: str = "",
        timeout: float = 120.0,
        batch_size: int = 24,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.api_key = api_key
        self.timeout = timeout
        self.batch_size = batch_size
        self.session = requests.Session()

    def health(self) -> bool:
        try:
            response = self.session.get(f"{self.endpoint}/health", timeout=10)
            return response.ok
        except requests.RequestException:
            try:
                response = self.session.get(f"{self.endpoint}/languages", timeout=10)
                return response.ok
            except requests.RequestException:
                return False

    def translate_batch(self, texts: list[str], html: bool = True) -> list[str]:
        if not texts:
            return []
        payload: dict[str, object] = {
            "q": texts,
            "source": self.source_lang,
            "target": self.target_lang,
            "format": "html" if html else "text",
        }
        if self.api_key:
            payload["api_key"] = self.api_key

        last_error: Exception | None = None
        for attempt in range(5):
            try:
                response = self.session.post(
                    f"{self.endpoint}/translate",
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                translated = data.get("translatedText")
                if isinstance(translated, str) and len(texts) == 1:
                    return [translated]
                if isinstance(translated, list) and len(translated) == len(texts):
                    return [str(item) for item in translated]
                raise TranslationError("Unexpected LibreTranslate response shape")
            except (requests.RequestException, ValueError, TranslationError) as exc:
                last_error = exc
                if attempt < 4:
                    time.sleep(min(2 ** attempt, 8))
        raise TranslationError(f"Translation failed after retries: {last_error}")


def translate_document(
    content_html: str,
    client: LibreTranslateClient,
    storage: Storage,
) -> TranslationResult:
    soup, blocks = translatable_blocks(content_html)
    pending: list[tuple[object, str, str]] = []
    translated_count = 0

    for block in blocks:
        source = block.decode_contents().strip()
        cache_key = _cache_key(client, source)
        cached = storage.get_translation(cache_key)
        if cached is not None:
            block.clear()
            _append_html(block, cached)
            translated_count += 1
        else:
            pending.append((block, source, cache_key))

    failed = 0
    for batch in _chunks(pending, client.batch_size):
        sources = [item[1] for item in batch]
        try:
            translated = client.translate_batch(sources, html=True)
        except TranslationError as exc:
            LOGGER.error("Translation batch failed: %s", exc)
            failed += len(batch)
            continue

        for (block, source, cache_key), translated_html in zip(batch, translated):
            storage.put_translation(
                cache_key,
                client.source_lang,
                client.target_lang,
                source,
                translated_html,
                client.provider_name,
            )
            block.clear()
            _append_html(block, translated_html)
            translated_count += 1

    return TranslationResult(
        html=root_inner_html(soup),
        complete=failed == 0,
        translated_blocks=translated_count,
        failed_blocks=failed,
    )


def translate_plain_text(text: str, client: LibreTranslateClient, storage: Storage) -> str:
    source = text.strip()
    if not source:
        return source
    cache_key = _cache_key(client, source)
    cached = storage.get_translation(cache_key)
    if cached is not None:
        return cached
    translated = client.translate_batch([source], html=False)[0]
    storage.put_translation(
        cache_key,
        client.source_lang,
        client.target_lang,
        source,
        translated,
        client.provider_name,
    )
    return translated


def _cache_key(client: LibreTranslateClient, source: str) -> str:
    payload = f"{client.provider_name}\0{client.source_lang}\0{client.target_lang}\0{source}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _chunks(items: list[tuple[object, str, str]], size: int) -> Iterable[list[tuple[object, str, str]]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _append_html(tag, html: str) -> None:
    from bs4 import BeautifulSoup

    fragment = BeautifulSoup(f"<div id='translated-fragment'>{html}</div>", "lxml")
    root = fragment.find(id="translated-fragment")
    if root is None:
        tag.append(html)
        return
    for child in list(root.contents):
        tag.append(child)
