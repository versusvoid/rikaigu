
.PHONY: all test c-test py-test

all: test rikai.wasm

clean:
	rm -rf build rikai.wasm

SOURCES := \
	src/api.c \
	src/dentry.c \
	src/dictionaries.c \
	src/html_render.c \
	src/libc.c \
	src/state.c \
	src/index.c \
	src/deinflect.c \
	src/word_results.c \
	src/vardata_array.c \
	src/utf.c \
	src/names_types_mapping.c
BITCODE_OBJECTS := $(SOURCES:src/%.c=build/%.bc) generated/index.bc
EXPORTS := rikaigu_search_start rikaigu_search_finish rikaigu_set_config buffer_allocate
EXPORTS := $(EXPORTS:%=--export=%)

rikai.wasm: build/wasm.o src/imports.txt
	wasm-ld \
		$(EXPORTS) \
		--no-entry \
		--lto-O3 \
		--allow-undefined-file=src/imports.txt \
		--stack-first -z stack-size=32768 \
		--verbose --print-gc-sections \
		build/wasm.o -o rikai.wasm
	@# Check we don't expect malloc
	! wasm-objdump -j Import -x rikai.wasm | grep -q malloc

build/wasm.o: build/wasm.bc-linked
	llc -O3 -filetype=obj build/wasm.bc-linked -o build/wasm.o

build/wasm.bc-linked: $(BITCODE_OBJECTS) Makefile
	llvm-link -o build/wasm.bc-linked $(BITCODE_OBJECTS)
	opt -O3 build/wasm.bc-linked -o build/wasm.bc-linked

build:
	mkdir build

CC := clang
COMMON_CFLAGS := $(shell cat cflags)
CFLAGS := $(COMMON_CFLAGS) -DNDEBUG -c -emit-llvm --target=wasm32-unknown-unknown-wasm
build/%.bc : src/%.c | build
	$(CC) $(CFLAGS) $< -o $@

build/%.bc.d : src/%.c | build
	@# -MM - ignore includes from system paths
	@# -MT - change target of generated rules from .o to .bc
	$(CC) $(COMMON_CFLAGS) -MM $< -MT "$(@:%.bc.d=%.bc)" -o $@


TEST_SOURCES := \
	tests/libc.c \
	tests/state.c \
	tests/dentry.c \
	tests/index.c \
	tests/utf.c

test: c-test py-test

TEST_EXES := $(TEST_SOURCES:tests/%.c=build/%.test)
c-test: $(TEST_EXES)
	set -ex; for f in $(TEST_EXES); do ./$$f; done

TEST_CFLAGS := $(COMMON_CFLAGS) -ggdb -fstack-protector-all -fsanitize=address -fsanitize=undefined -fno-sanitize=alignment
build/%.test : tests/%.c build/index.polyfill.o | build
	$(CC) $(TEST_CFLAGS) -o $@ build/index.polyfill.o $<

build/index.polyfill.o: tests/index.polyfill.c
	$(CC) -c tests/index.polyfill.c -o build/index.polyfill.o

build/generated.index.o: generated/index.bc
	llc -O3 -filetype=obj -mtriple=$$(llc --version | grep -F 'Default target' | sed 's/.*: \(\w\+\)/\1/g') generated/index.bc -o build/generated.index.o

build/%.test.d : tests/%.c | build
	$(CC) $(COMMON_CFLAGS) -MM $< -MT "$(@:%.test.d=%.test)" -o $@

COMPILER_RT := /usr/lib/clang/8.0.0/lib/linux
py-test: build/test.so tests/test.py
	LD_PRELOAD=$(COMPILER_RT)/libclang_rt.asan-x86_64.so ASAN_OPTIONS=detect_leaks=false \
		python -m unittest -v -f tests/*.py

build/bindings.py: build/test.so | build
	LD_PRELOAD=$(COMPILER_RT)/libclang_rt.asan-x86_64.so ASAN_OPTIONS=detect_leaks=false \
		PYTHONPATH=../../ctypeslib python ../../ctypeslib/ctypeslib/clang2py.py \
		--clang-args="$(COMMON_CFLAGS)" \
		-l build/test.so --debug -x \
		src/*.c -o build/bindings.py
	LD_PRELOAD=$(COMPILER_RT)/libclang_rt.asan-x86_64.so ASAN_OPTIONS=detect_leaks=false python build/bindings.py

SHARED_TEST_CFLAGS := $(TEST_CFLAGS) -fPIC -fdata-sections -ffunction-sections -shared-libsan
build/test.so: $(SOURCES) tests/polyfill.c generated/index.test.c build/generated.index.o | build
	$(CC) $(SOURCES:src/index.c=generated/index.test.c) tests/polyfill.c build/generated.index.o \
		$(SHARED_TEST_CFLAGS) \
		-D dictionary_index_max_entry_length=2048 \
		-shared -Wl,--gc-sections,--print-gc-sections \
		-L$(COMPILER_RT) -lclang_rt.ubsan_standalone-x86_64 \
		-Wl,-rpath=$(COMPILER_RT) \
		-o build/test.so

ifneq ($(MAKECMDGOALS),clean)
include $(SOURCES:src/%.c=build/%.bc.d)
include $(TEST_SOURCES:tests/%.c=build/%.test.d)
endif