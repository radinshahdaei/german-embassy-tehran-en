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

deploy:
	rm -rf /tmp/deploy-pages
	git clone https://github.com/radinshahdaei/radinshahdaei.github.io.git /tmp/deploy-pages
	rm -rf /tmp/deploy-pages/german-embassy-tehran-en
	cp -r site /tmp/deploy-pages/german-embassy-tehran-en
	touch /tmp/deploy-pages/german-embassy-tehran-en/.nojekyll
	cd /tmp/deploy-pages && git add german-embassy-tehran-en/ && git commit -m "Update Tehran embassy mirror" && git push
	rm -rf /tmp/deploy-pages

clean:
	rm -f data/mirror.db data/mirror.db-shm data/mirror.db-wal
	rm -rf site/*
	touch site/.gitkeep
