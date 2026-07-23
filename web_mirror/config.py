from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import yaml

DEFAULT_CONFIG_PATH = Path("config.yaml")

_ENV_MAP: dict[str, str] = {
    "start_url": "MIRROR_START_URL",
    "path_prefix": "MIRROR_PATH_PREFIX",
    "source_lang": "MIRROR_SOURCE_LANG",
    "target_lang": "MIRROR_TARGET_LANG",
    "translator_url": "MIRROR_TRANSLATOR_URL",
    "translator_api_key": "MIRROR_TRANSLATOR_API_KEY",
    "crawl_delay_seconds": "MIRROR_CRAWL_DELAY_SECONDS",
    "max_pages": "MIRROR_MAX_PAGES",
    "robots_mode": "MIRROR_ROBOTS_MODE",
    "request_timeout_seconds": "MIRROR_REQUEST_TIMEOUT_SECONDS",
    "data_dir": "MIRROR_DATA_DIR",
    "site_dir": "MIRROR_SITE_DIR",
    "user_agent": "MIRROR_USER_AGENT",
    "site_title": "MIRROR_SITE_TITLE",
    "source_attribution": "MIRROR_SOURCE_ATTRIBUTION",
    "source_language_label": "MIRROR_SOURCE_LANGUAGE_LABEL",
    "generic_h1_patterns": "MIRROR_GENERIC_H1_PATTERNS",
    "title_suffix_regex": "MIRROR_TITLE_SUFFIX_REGEX",
    "excluded_path_segments": "MIRROR_EXCLUDED_PATH_SEGMENTS",
}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a mapping: {path}")
    return data


def _resolve(key: str, yaml_data: dict) -> str | int | float:
    env_name = _ENV_MAP.get(key)
    if env_name and os.getenv(env_name, "") != "":
        return os.environ[env_name]
    return yaml_data.get(key, "")


def _resolve_list(key: str, yaml_data: dict) -> list[str]:
    """Resolve a list config value from env var (comma-separated) or YAML."""
    env_name = _ENV_MAP.get(key)
    if env_name:
        raw = os.getenv(env_name)
        if raw is not None and raw.strip() != "":
            return [item.strip() for item in raw.split(",") if item.strip()]
    value = yaml_data.get(key)
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


@dataclass(frozen=True)
class Settings:
    start_url: str
    path_prefix: str
    source_lang: str
    target_lang: str
    translator_url: str
    translator_api_key: str
    crawl_delay: float
    max_pages: int
    robots_mode: str
    request_timeout: float
    data_dir: Path
    site_dir: Path
    user_agent: str
    site_title: str
    source_attribution: str
    source_language_label: str
    generic_h1_patterns: list[str]
    title_suffix_regex: str
    excluded_path_segments: list[str]

    @classmethod
    def from_yaml(cls, config_path: Path | None = None) -> "Settings":
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        data = _load_yaml(path)
        return cls(
            start_url=str(_resolve("start_url", data)),
            path_prefix=str(_resolve("path_prefix", data)),
            source_lang=str(_resolve("source_lang", data)),
            target_lang=str(_resolve("target_lang", data)),
            translator_url=str(_resolve("translator_url", data)),
            translator_api_key=str(_resolve("translator_api_key", data) or ""),
            crawl_delay=float(_resolve("crawl_delay_seconds", data)),
            max_pages=int(_resolve("max_pages", data)),
            robots_mode=str(_resolve("robots_mode", data)),
            request_timeout=float(_resolve("request_timeout_seconds", data)),
            data_dir=Path(str(_resolve("data_dir", data))),
            site_dir=Path(str(_resolve("site_dir", data))),
            user_agent=str(_resolve("user_agent", data)),
            site_title=str(_resolve("site_title", data)),
            source_attribution=str(_resolve("source_attribution", data)),
            source_language_label=str(_resolve("source_language_label", data)),
            generic_h1_patterns=_resolve_list("generic_h1_patterns", data),
            title_suffix_regex=str(_resolve("title_suffix_regex", data) or ""),
            excluded_path_segments=_resolve_list("excluded_path_segments", data),
        )

    @property
    def origin(self) -> str:
        parsed = urlsplit(self.start_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def host(self) -> str:
        return urlsplit(self.start_url).netloc.lower()

    @property
    def database_path(self) -> Path:
        return self.data_dir / "mirror.db"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.site_dir.mkdir(parents=True, exist_ok=True)
