mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
DIR := $(notdir $(patsubst %/,%,$(dir $(mkfile_path))))

CSS = css/options.css css/popup-common.css css/popup-black.css css/popup-blue.css css/popup-lightblue.css css/popup-yellow.css
DICT_STATIC = data/kanji.dat data/names.dat data/names.idx data/radicals.dat data/deinflect.dat
DICT_DYNAMIC = dist/rikaigu/data/dict.dat dist/rikaigu/data/dict.idx
IMG = images/ba.png images/icon128.png images/icon48.png
HTML = html/background.html html/options.html html/scratchpad.html html/popup.html
JS = js/background.js js/deinflector.js js/data.js js/options.js js/rikaicontent.js js/rikaigu.js js/scratchpad.js js/popup.js

.PHONY: all dicts clean

all: dist/rikaigu.zip
dicts: ${DICT_DYNAMIC}

dist/rikaigu/data/dict.dat: data/prepare-dict.py data/utils.py
	mkdir -p dist/rikaigu/data
	data/prepare-dict.py --output dist/rikaigu/data/dict.dat
	cd data; ln -sf ../dist/rikaigu/data/dict.dat ./

dist/rikaigu/data/dict.idx: dist/rikaigu/data/dict.dat data/compute_index.py data/utils.py
	data/compute_index.py --variate-writings --kanji-dictionary data/kanji.dat dist/rikaigu/data/dict.dat
	cd data; ln -sf ../dist/rikaigu/data/dict.idx ./

dist/rikaigu.zip: Makefile manifest.json ${CSS} ${DICT_STATIC} ${IMG} ${HTML} ${JS} ${DICT_DYNAMIC}
	cp --parents manifest.json ${CSS} ${DICT_STATIC} ${IMG} ${HTML} ${JS} dist/rikaigu/
	cd dist; zip rikaigu.zip -r rikaigu

data/model.bin: crfpp/crf_learn
	crfpp/crf_learn -p 4 -f 1000 -a CRF-L1 \
		segmentation/models/model2.desc \
		segmentation/l-train.csv \
		data/model.bin

clean:
	rm -rf tmp dist data/dict.idx data/dict.dat
