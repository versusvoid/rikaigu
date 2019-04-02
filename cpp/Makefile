
.PHONY: all release

all: rikai.asm.js
release: release/rikai.asm.js

clean:
	rm -rf release
	find ./ -regex '.*\.\(bc\|d\)' -delete
	rm -f \
		rikai.asm.js rikai.asm.data \
		rikai.asm.wasm rikai.asm.wasm.pre rikai.asm.wast

COMMON_CXXFLAGS = -std=c++17 -O3 -Wall -I.

JS_CXXFLAGS = $(COMMON_CXXFLAGS)
JS_DEBUG_FLAGS = -g3 -s SAFE_HEAP=1 -s ASSERTIONS=1 -s WARN_UNALIGNED=1 -s DEMANGLE_SUPPORT=1
EMCC = emcc
EMCCFLAGS = \
		-s TOTAL_MEMORY=40MB \
		-s LZ4=1 \
		-s 'EXTRA_EXPORTED_RUNTIME_METHODS=["ccall", "cwrap", "getValue"]' \
		-s WASM=1 \
		--preload-file ../data/dict.dat@/dict.dat \
		--preload-file ../data/names.dat@/names.dat \
		--preload-file ../data/kanji.dat@/kanji.dat
		# -s TOTAL_STACK=500KB \

JS_SOURCES = \
	client/api.cpp \
	client/deinflector.cpp \
	client/dentry.cpp \
	client/dictionaries.cpp \
	client/html_render.cpp \
	client/word_types.cpp \
	client/utils.cpp
JS_OBJECTS = $(JS_SOURCES:%.cpp=%.bc)

rikai.asm.js: $(JS_OBJECTS) ../data/dict.dat ../data/names.dat ../data/kanji.dat Makefile
	$(EMCC) $(JS_CXXFLAGS) $(JS_OBJECTS) $(JS_DEBUG_FLAGS) $(EMCCFLAGS) -o $@

release/rikai.asm.js: $(JS_OBJECTS) ../data/dict.dat ../data/names.dat ../data/kanji.dat
	mkdir -p release
	$(EMCC) $(JS_CXXFLAGS) $(JS_OBJECTS) $(EMCCFLAGS) -o $@

%.bc : %.cpp
	$(EMCC) $(JS_CXXFLAGS) $< -o $@

%.bc.d : %.cpp
	$(EMCC) $(JS_CXXFLAGS) -MM $< -MT "$@ $(<:%.cpp=%.bc)" -o $@

ifneq ($(MAKECMDGOALS),clean)
include $(JS_SOURCES:%.cpp=%.bc.d)
endif