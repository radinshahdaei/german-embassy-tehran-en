from web_mirror.urls import is_crawlable, local_filename, normalize_url


def test_normalize_removes_fragment_and_tracking():
    value = normalize_url("/ir-de/test/?utm_source=x#part", "https://teheran.diplo.de/ir-de")
    assert value == "https://teheran.diplo.de/ir-de/test"


def test_crawl_scope():
    excluded = ["/suche", "/search", "/kontaktformular", "/newsletter"]
    assert is_crawlable("https://teheran.diplo.de/ir-de/service", "teheran.diplo.de", "/ir-de", excluded)
    assert not is_crawlable("https://teheran.diplo.de/ir-fa/service", "teheran.diplo.de", "/ir-de", excluded)
    assert not is_crawlable("https://example.com/ir-de/service", "teheran.diplo.de", "/ir-de", excluded)
    assert not is_crawlable("https://teheran.diplo.de/ir-de/file.pdf", "teheran.diplo.de", "/ir-de", excluded)
    # Path exclusion
    assert not is_crawlable("https://teheran.diplo.de/ir-de/suche", "teheran.diplo.de", "/ir-de", excluded)
    assert not is_crawlable("https://teheran.diplo.de/ir-de/newsletter/archiv", "teheran.diplo.de", "/ir-de", excluded)


def test_home_filename():
    assert local_filename("https://teheran.diplo.de/ir-de", "https://teheran.diplo.de/ir-de") == "pages/home.html"
