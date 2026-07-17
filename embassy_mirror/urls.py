from __future__ import annotations

import hashlib
import posixpath
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

BINARY_SUFFIXES = {
    ".7z", ".avi", ".bmp", ".csv", ".doc", ".docx", ".eps", ".gif",
    ".gz", ".ico", ".jpeg", ".jpg", ".json", ".m4a", ".mkv", ".mov",
    ".mp3", ".mp4", ".mpeg", ".ods", ".odt", ".pdf", ".png", ".ppt",
    ".pptx", ".rar", ".rss", ".svg", ".tar", ".tif", ".tiff", ".txt",
    ".wav", ".webm", ".webp", ".xls", ".xlsx", ".xml", ".zip",
}


def normalize_url(raw_url: str, base_url: str | None = None) -> str:
    joined = urljoin(base_url, raw_url) if base_url else raw_url
    parsed = urlsplit(joined.strip())
    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower()
    path = quote(unquote(parsed.path or "/"), safe="/%:@-._~!$&'()*+,;=")
    path = posixpath.normpath(path)
    if not path.startswith("/"):
        path = "/" + path
    # The target site uses query strings mostly for UI/search state. Dropping them
    # prevents duplicate pages while preserving the canonical path.
    return urlunsplit((scheme, host, path, "", ""))


def is_crawlable(url: str, host: str, path_prefix: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() != host.lower():
        return False
    if not parsed.path.startswith(path_prefix.rstrip("/") + "/") and parsed.path != path_prefix.rstrip("/"):
        return False
    suffix = Path(unquote(parsed.path)).suffix.lower()
    if suffix in BINARY_SUFFIXES:
        return False
    lowered = parsed.path.lower()
    excluded_fragments = ("/suche", "/search", "/kontaktformular", "/newsletter")
    return not any(fragment in lowered for fragment in excluded_fragments)


def page_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def local_filename(url: str, start_url: str) -> str:
    if normalize_url(url) == normalize_url(start_url):
        return "pages/home.html"
    return f"pages/{page_id(url)}.html"
