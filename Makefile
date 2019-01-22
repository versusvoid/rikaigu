CSS = css/options.css css/popup-common.css css/popup-black.css css/popup-blue.css css/popup-lightblue.css css/popup-yellow.css
DICT_STATIC = data/kanji.dat data/radicals.dat data/deinflect.dat
DICT_DYNAMIC = data/dict.dat data/dict.idx data/names.dat data/names.idx data/kanji.idx data/expressions.dat
IMG = images/ba.png images/icon128.png images/icon48.png
HTML = html/background.html html/options.html html/scratchpad.html html/popup.html
JS = js/background.js js/config.js js/options.js js/rikaicontent.js js/selection.js js/highlight.js js/scratchpad.js js/popup.js
CPP_DEV = cpp/rikai.asm.js cpp/rikai.asm.js.mem cpp/rikai.asm.data
CPP_RELEASE = cpp/release/rikai.asm.js cpp/release/rikai.asm.wasm cpp/release/rikai.asm.data

.PHONY: all $(CPP_DEV) release dicts clean

all: cpp/rikai.asm.js
release: dist/rikaigu.zip

$(DICT_DYNAMIC): data/dictionary.py data/expressions.py data/prepare-dict.py data/utils.py data/index.py data/freqs.py data/romaji.py data/expressions.dat.in
	data/prepare-dict.py

$(CPP_DEV): $(DICT_DYNAMIC)
	cd cpp && make

$(CPP_RELEASE): $(DICT_DYNAMIC)
	cd cpp && make release

dist/rikaigu.zip: manifest.json $(CSS) $(DICT_STATIC) $(IMG) $(HTML) $(JS) $(DICT_DYNAMIC) $(CPP_RELEASE)
	mkdir -p dist/rikaigu/{css,data,images,html,js,cpp}
	ln -sfr $(CSS) dist/rikaigu/css
	ln -sfr $(IMG) dist/rikaigu/images
	ln -sfr $(HTML) dist/rikaigu/html
	ln -sfr $(JS) dist/rikaigu/js
	ln -sfr $(CPP_RELEASE) dist/rikaigu/cpp
	ln -sfr data/radicals.dat data/deinflect.dat \
		data/dict.idx data/names.idx data/kanji.idx data/expressions.dat \
		dist/rikaigu/data
	cp manifest.json dist/rikaigu/
	sed -i 's/rikaigu (devel)/rikaigu/g' dist/rikaigu/manifest.json
	cd dist; zip rikaigu.zip -r rikaigu

clean:
	cd cpp && make clean
	rm -rf data/release data/__pycache__ tmp dist $(DICT_DYNAMIC)
