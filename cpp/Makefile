
all: rikai.asm.js

CXXFLAGS = -std=c++14 -O3 -Wall -I../crfxx/include
DEBUG_FLAGS = -g3 -s SAFE_HEAP=1 -s ASSERTIONS=1 -s WARN_UNALIGNED=1
EMCCFLAGS =  -L../crfxx/js -l crfxx \
		-s TOTAL_MEMORY=32MB \
	    -s TOTAL_STACK=500KB \
	    -g1 -s LZ4=1 \
	    --preload-file ../data/dict.dat@/dict.dat \
	    --preload-file ../data/names.dat@/names.dat \
	    --preload-file ../data/kanji.dat@/kanji.dat

ifndef release
EMCCFLAGS += ${DEBUG_FLAGS}
endif

OBJECTS = api.bc crf.bc deinflector.bc dentry.bc dictionaries.bc html_render.bc word_types.bc utils.bc

rikai.asm.js: ../crfxx/js/libcrfxx.a $(OBJECTS) \
		../data/dict.dat ../data/names.dat ../data/kanji.dat
	emcc $(CXXFLAGS) $(^:%.dat=)  $(EMCCFLAGS) -o $@

%.d : %.cpp
	emcc $(CXXFLAGS) -MM $< -MT $(<:%.cpp=%.bc) -o $@
	sed 's/^\($(<:%.cpp=%.bc)\)/\1 $@/g' -i $@

include $(OBJECTS:%.bc=%.d)

%.bc : %.cpp
	emcc $(CXXFLAGS) $< -o $@

clean:
	rm -rf *.bc *.d
	rm -f rikai.asm.js rikai.asm.js.data rikai.asm.js.mem rikai.asm.js.map
