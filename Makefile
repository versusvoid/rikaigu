CSS = css/options.css css/popup-common.css css/popup-black.css css/popup-blue.css css/popup-lightblue.css css/popup-yellow.css
DICT_DYNAMIC = wasm/generated/dictionary.bc wasm/generated/index.bc
IMG = images/ba.png images/icon128.png images/icon48.png
HTML = html/background.html html/options.html html/scratchpad.html html/popup.html
JS = js/background.js js/config.js js/options.js js/rikaicontent.js js/selection.js js/highlight.js js/scratchpad.js js/popup.js
WASM = wasm/rikai.wasm

.PHONY: all release clean wasm/rikai.wasm

all: wasm/rikai.wasm
release: dist/rikaigu.zip

$(DICT_DYNAMIC): data/dictionary.py data/prepare-dict.py data/utils.py data/index.py data/freqs.py data/romaji.py
	data/prepare-dict.py

$(WASM): $(DICT_DYNAMIC)
	cd wasm && make

dist/rikaigu.zip: manifest.json $(CSS) $(IMG) $(HTML) $(JS) $(DICT_DYNAMIC) $(WASM)
	mkdir -p dist/rikaigu/{css,data,images,html,js,wasm}
	ln -sfr $(CSS) dist/rikaigu/css
	ln -sfr $(IMG) dist/rikaigu/images
	ln -sfr $(HTML) dist/rikaigu/html
	ln -sfr $(JS) dist/rikaigu/js
	ln -sfr $(WASM) dist/rikaigu/wasm
	ln -sfr $(DICT_DYNAMIC) dist/rikaigu/data
	head -n 33 wasm/generated/lz4.c > dist/rikaigu/lz4.license
	cp manifest.json dist/rikaigu/
	sed -i 's/rikaigu (devel)/rikaigu/g' dist/rikaigu/manifest.json
	cd dist; zip rikaigu.zip -r rikaigu

clean:
	cd wasm && make clean
	rm -rf data/release data/__pycache__ tmp dist $(DICT_DYNAMIC)
