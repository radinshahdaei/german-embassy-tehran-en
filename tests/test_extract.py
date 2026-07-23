from pathlib import Path

from web_mirror.extract import extract_page


def test_extracts_safe_main_content():
    html = Path("tests/fixture.html").read_text(encoding="utf-8")
    page = extract_page(
        html,
        "https://teheran.diplo.de/ir-de/test",
        "teheran.diplo.de",
        "/ir-de",
        generic_h1_patterns=["Willkommen auf den Seiten des Auswärtigen Amts", "Navigation und Service"],
        title_suffix_regex=r"\s+-\s+Auswärtiges Amt\s*$",
        excluded_path_segments=["/suche", "/search", "/kontaktformular", "/newsletter"],
    )
    assert page.title == "Willkommen"
    assert "Willkommen" in page.content_html
    assert "wichtiger Hinweis" in page.content_html
    assert "Image: Botschaft" in page.content_html
    assert "alert" not in page.content_html
    assert "<form" not in page.content_html
    assert "style=" not in page.content_html
    assert "https://teheran.diplo.de/ir-de/service" in page.content_html
    assert "https://teheran.diplo.de/ir-de/service" in page.outgoing_links
    assert "https://teheran.diplo.de/ir-de/footer" in page.outgoing_links
