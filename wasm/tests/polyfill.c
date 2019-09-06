#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>

void (*take_a_trip_impl)(const char*) = NULL;
void take_a_trip(const char* msg)
{
	take_a_trip_impl(msg);
}

size_t (*__builtin_wasm_memory_size_impl)(int) = NULL;
size_t __builtin_wasm_memory_size(int i)
{
	assert(__builtin_wasm_memory_size_impl);
	return __builtin_wasm_memory_size_impl(i);
}

size_t (*__builtin_wasm_memory_grow_impl)(int, size_t) = NULL;
size_t __builtin_wasm_memory_grow(int i, size_t n)
{
	assert(__builtin_wasm_memory_grow_impl);
	return __builtin_wasm_memory_grow_impl(i, n);
}

void print(const char* p)
{
	printf("\nprint('%s')\n", p);
}
