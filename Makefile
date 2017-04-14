mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
DIR := $(notdir $(patsubst %/,%,$(dir $(mkfile_path))))

CSS = css/options.css css/popup-common.css css/popup-black.css css/popup-blue.css css/popup-lightblue.css css/popup-yellow.css
DICT_STATIC = data/kanji.dat data/radicals.dat data/deinflect.dat
DICT_DYNAMIC = data/dict.dat data/dict.idx data/names.dat data/names.idx data/kanji.idx data/expressions.dat
IMG = images/ba.png images/icon128.png images/icon48.png
HTML = html/background.html html/options.html html/scratchpad.html html/popup.html
JS = js/background.js js/config.js js/options.js js/rikaicontent.js js/selection.js js/highlight.js js/scratchpad.js js/popup.js
CPP = cpp/rikai.asm.js cpp/rikai.asm.js.mem cpp/rikai.asm.data

.PHONY: all dicts clean

all: dist/rikaigu.zip
dev: ${DICT_DYNAMIC} ${CPP} data/model.bin

${DICT_DYNAMIC}: data/prepare-dict.py data/utils.py data/index.py data/freqs.py
	data/prepare-dict.py

crfpp/tagger.cpp:
	git submodule init
	git submodule update

crfpp/js/libcrfpp.bc crfpp/crf_learn: crfpp/tagger.cpp
	cd crfpp && autoreconf -i
	cd crfpp && ./configure
	cd crfpp && make

${CPP}: crfpp/js/libcrfpp.bc ${DICT_DYNAMIC}
	cd cpp && make release=1

dist/rikaigu.zip: manifest.json ${CSS} ${DICT_STATIC} ${IMG} ${HTML} ${JS} ${DICT_DYNAMIC} ${CPP} data/model.bin
	mkdir -p dist/rikaigu/{css,data,images,html,js,cpp}
	ln -sfr ${CSS} dist/rikaigu/css
	ln -sfr ${IMG} dist/rikaigu/images
	ln -sfr ${HTML} dist/rikaigu/html
	ln -sfr ${JS} dist/rikaigu/js
	ln -sfr ${CPP} dist/rikaigu/cpp
	ln -sfr data/model.bin \
		data/radicals.dat \
		data/deinflect.dat data/expressions.dat \
		data/dict.idx data/names.idx data/kanji.idx \
		dist/rikaigu/data
	ln -sfr manifest.json dist/rikaigu
	cd dist; zip rikaigu.zip -r rikaigu

segmentation/l-train.csv: segmentation/prepare-corpus.py
	segmentation/prepare-corpus.py

data/model.bin: crfpp/crf_learn segmentation/l-train.csv
	crfpp/crf_learn -p 8 -f 1000 -a CRF-L1 \
		segmentation/models/model2.desc \
		segmentation/l-train.csv \
		data/model.bin

clean:
	cd cpp && make clean
	cd crfpp && make clean
	rm -rf tmp dist ${DICT_DYNAMIC} tmp data/model.bin segmentation/*.csv
