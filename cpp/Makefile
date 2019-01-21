
all: rikai.asm.js

CXXFLAGS = -std=c++14 -O3 -Wall -I../crfpp
DEBUG_FLAGS = -g3 -s SAFE_HEAP=1 -s ASSERTIONS=1 -s WARN_UNALIGNED=1
EMCCFLAGS = -s TOTAL_MEMORY=48MB \
	    -g1 -s LZ4=1 \
	    --preload-file ../data/dict.dat@/dict.dat \
	    --preload-file ../data/names.dat@/names.dat \
	    # $(DEBUG_FLAGS)

rikai.asm.js: ../crfpp/js/libcrfpp.bc \
		../data/dict.dat ../data/names.dat \
		api.bc crf.bc deinflector.bc dentry.bc dictionaries.bc html_render.bc word_types.bc utils.bc
	emcc $(CXXFLAGS) $(EMCCFLAGS) $(^:%.dat=) -o rikai.asm.js

%.bc : %.cpp
	emcc $(CXXFLAGS) $< -o $@

clean:
	rm -rf *.bc
	rm -f rikai.asm.js
