from pathlib import Path

import yaml

from embassy_mirror.config import Settings
from embassy_mirror.render import Renderer
from embassy_mirror.storage import PageRecord, Storage
from embassy_mirror.urls import page_id


def test_renderer_builds_landing_and_rewrites_links(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "start_url": "https://teheran.diplo.de/ir-de",
        "path_prefix": "/ir-de",
        "source_lang": "de",
        "target_lang": "en",
        "translator_url": "http://localhost:5001",
        "translator_api_key": "",
        "crawl_delay_seconds": 1.0,
        "max_pages": 0,
        "robots_mode": "respect",
        "request_timeout_seconds": 30,
        "data_dir": str(tmp_path / "data"),
        "site_dir": str(tmp_path / "site"),
        "user_agent": "TestBot/1.0",
    }))
    settings = Settings.from_yaml(config_path)
    settings.ensure_directories()
    storage = Storage(settings.database_path)
    home = "https://teheran.diplo.de/ir-de"
    service = "https://teheran.diplo.de/ir-de/service"
    common = dict(
        content_hash="hash",
        fetched_at="2026-07-17T10:00:00+00:00",
        status="ok",
        http_status=200,
        error="",
    )
    storage.upsert_page(PageRecord(
        url=home,
        title_de="Startseite",
        title_en="Home",
        source_html=f'<h1>Startseite</h1><p><a href="{service}">Dienst</a></p>',
        translated_html=f'<h1>Home</h1><p><a href="{service}">Service</a></p>',
        outgoing_links=[service],
        **common,
    ))
    storage.upsert_page(PageRecord(
        url=service,
        title_de="Dienst",
        title_en="Service",
        source_html="<h1>Dienst</h1>",
        translated_html="<h1>Service</h1>",
        outgoing_links=[],
        **common,
    ))

    assert Renderer(settings, storage).render_all() == 2
    assert (settings.site_dir / "index.html").exists()
    home_file = settings.site_dir / "pages/home.html"
    service_file = settings.site_dir / "pages" / f"{page_id(service)}.html"
    assert home_file.exists()
    assert service_file.exists()
    assert f'{page_id(service)}.html' in home_file.read_text(encoding="utf-8")
    assert "pages/home.html" in (settings.site_dir / "index.html").read_text(encoding="utf-8")
