.PHONY: run translator crawl refresh render serve stop test clean

TRANSLATOR_PORT ?= 5001

run: translator crawl serve

translator:
	libretranslate --host 0.0.0.0 --port $(TRANSLATOR_PORT) --load-only de,en --disable-web-ui

crawl:
	teheran-mirror crawl

refresh:
	teheran-mirror crawl --refresh

render:
	teheran-mirror render

serve:
	teheran-mirror serve --port 8080

stop:
	pkill -f libretranslate || true

test:
	python -m pytest -q

clean:
	rm -f data/mirror.db data/mirror.db-shm data/mirror.db-wal
	rm -rf site/*
	touch site/.gitkeep
