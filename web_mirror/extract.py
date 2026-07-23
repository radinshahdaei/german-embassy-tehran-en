from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from .urls import is_crawlable, normalize_url

ALLOWED_TAGS = {
    "a", "abbr", "address", "article", "aside", "b", "blockquote", "br",
    "caption", "cite", "code", "dd", "del", "details", "dfn", "div", "dl",
    "dt", "em", "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "i", "kbd", "li", "main", "mark", "ol", "p", "pre", "q", "s",
    "samp", "section", "small", "span", "strong", "sub", "summary", "sup",
    "table", "tbody", "td", "tfoot", "th", "thead", "time", "tr", "u", "ul",
    "var",
}
ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "abbr": {"title"},
    "td": {"colspan", "rowspan", "headers"},
    "th": {"colspan", "rowspan", "scope", "abbr", "headers"},
    "time": {"datetime"},
}
DROP_SELECTORS = [
    "script", "style", "noscript", "iframe", "form", "button", "input",
    "select", "textarea", "canvas", "svg", "video", "audio", "source", "nav",
    "[role='navigation']", "[aria-hidden='true']",
]
BLOCK_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "dt", "dd", "th", "td",
    "figcaption", "caption", "summary", "blockquote", "address",
}


@dataclass
class ExtractedPage:
    title: str
    content_html: str
    outgoing_links: list[str]
    content_hash: str


def discover_links(html: str, page_url: str, host: str, path_prefix: str,
                   excluded_path_segments: list[str] | None = None) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    found: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        url = normalize_url(href, page_url)
        if is_crawlable(url, host, path_prefix, excluded_path_segments):
            found.add(url)
    return sorted(found)


def extract_page(html: str, page_url: str, host: str, path_prefix: str,
                 generic_h1_patterns: list[str] | None = None,
                 title_suffix_regex: str = "",
                 excluded_path_segments: list[str] | None = None) -> ExtractedPage:
    original = BeautifulSoup(html, "lxml")
    title = _extract_title(original, generic_h1_patterns, title_suffix_regex)
    outgoing = discover_links(html, page_url, host, path_prefix, excluded_path_segments)

    main = _select_main(original)
    fragment = BeautifulSoup(str(main), "lxml")
    body = fragment.body or fragment

    for selector in DROP_SELECTORS:
        for node in body.select(selector):
            node.decompose()

    for heading in list(body.find_all("h1")):
        text = heading.get_text(" ", strip=True)
        if generic_h1_patterns and any(text == pattern for pattern in generic_h1_patterns):
            heading.decompose()

    _replace_images(body, page_url)
    _sanitize(body, page_url)
    _remove_empty_wrappers(body)

    content_html = "".join(str(child) for child in body.contents).strip()
    digest = hashlib.sha256(content_html.encode("utf-8")).hexdigest()
    return ExtractedPage(title, content_html, outgoing, digest)


def translatable_blocks(content_html: str) -> tuple[BeautifulSoup, list[Tag]]:
    soup = BeautifulSoup(f"<div id='mirror-root'>{content_html}</div>", "lxml")
    root = soup.find(id="mirror-root")
    assert root is not None
    blocks: list[Tag] = []
    for tag in root.find_all(BLOCK_TAGS):
        if any(getattr(parent, "name", None) in BLOCK_TAGS for parent in tag.parents if parent is not root):
            continue
        text = tag.get_text(" ", strip=True)
        if text and _contains_letters(text):
            blocks.append(tag)
    return soup, blocks


def root_inner_html(soup: BeautifulSoup) -> str:
    root = soup.find(id="mirror-root")
    assert root is not None
    return "".join(str(child) for child in root.contents).strip()


def _extract_title(soup: BeautifulSoup,
                   generic_h1_patterns: list[str] | None = None,
                   title_suffix_regex: str = "") -> str:
    patterns = set(generic_h1_patterns) if generic_h1_patterns else set()
    headings = [
        heading.get_text(" ", strip=True)
        for heading in soup.find_all("h1")
        if heading.get_text(" ", strip=True) not in patterns
    ]
    if headings:
        return headings[-1]
    if soup.title and soup.title.string:
        raw = soup.title.string.strip()
        if title_suffix_regex:
            raw = re.sub(title_suffix_regex, "", raw)
        return raw
    return "Untitled page"


def _select_main(soup: BeautifulSoup) -> Tag:
    candidates = [
        soup.find("main"),
        soup.find(attrs={"role": "main"}),
        soup.select_one("#content"),
        soup.select_one(".content"),
        soup.select_one("article"),
        soup.body,
    ]
    for candidate in candidates:
        if isinstance(candidate, Tag):
            return candidate
    return soup


def _replace_images(root: Tag, page_url: str) -> None:
    factory = BeautifulSoup("", "lxml")
    for image in list(root.find_all("img")):
        alt = image.get("alt", "").strip()
        src = image.get("src", "").strip()
        replacement = factory.new_tag("span")
        replacement.string = f"[Image: {alt}]" if alt else "[Image omitted]"
        if src:
            wrapper = factory.new_tag("a", href=urljoin(page_url, src))
            wrapper.append(replacement)
            image.replace_with(wrapper)
        else:
            image.replace_with(replacement)


def _sanitize(root: Tag, page_url: str) -> None:
    for tag in list(root.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        allowed = ALLOWED_ATTRS.get(tag.name, set())
        attrs = dict(tag.attrs)
        for attr in attrs:
            if attr not in allowed:
                del tag.attrs[attr]
        if tag.name == "a":
            href = tag.get("href", "").strip()
            if href:
                if href.startswith(("mailto:", "tel:")):
                    continue
                parsed = urlsplit(urljoin(page_url, href))
                if parsed.scheme in {"http", "https"}:
                    tag["href"] = urljoin(page_url, href)
                else:
                    tag.unwrap()
            else:
                tag.unwrap()


def _remove_empty_wrappers(root: Tag) -> None:
    changed = True
    while changed:
        changed = False
        for tag in list(root.find_all(["div", "section", "article", "aside", "span"])):
            if not tag.get_text(" ", strip=True) and not tag.find(["hr", "br", "table"]):
                tag.decompose()
                changed = True


def _contains_letters(text: str) -> bool:
    return any(char.isalpha() for char in text)
