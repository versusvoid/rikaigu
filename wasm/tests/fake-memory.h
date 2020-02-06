#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <assert.h>
#include <stdnoreturn.h>

uint8_t* wasm_memory = NULL;
size_t wasm_memory_size_pages = 0;
size_t wasm_memory_max_size_pages = 0;

unsigned char __heap_base;

size_t __builtin_wasm_memory_size(int memory_index)
{
	if (wasm_memory == NULL)
	{
		fprintf(stderr, "Init fake memory before tests\n");
		abort();
	}
	assert(memory_index == 0);
	return wasm_memory_size_pages;
}

size_t __builtin_wasm_memory_grow(int memory_index, size_t num_pages)
{
	assert(memory_index == 0);
	assert(num_pages > 0);
	assert(wasm_memory_size_pages + num_pages <= wasm_memory_max_size_pages);

	size_t old_size_pages = wasm_memory_size_pages;
	wasm_memory_size_pages += num_pages;
	return old_size_pages;
}

noreturn void take_a_trip(const char* error)
{
	fprintf(stderr, "%s\n", error);
	abort();
}

void print(const char* s)
{
	printf("print('%s')\n", s);
}

void setup_memory()
{
	assert(wasm_memory == NULL);
	wasm_memory = (uint8_t*)malloc(4*(1<<16));
	wasm_memory_max_size_pages = 8;
	wasm_memory_size_pages = 1;
}

void clear_memory()
{
	free(wasm_memory);
	wasm_memory = NULL;
	wasm_memory_max_size_pages = 0;
	wasm_memory_size_pages = 0;
}

