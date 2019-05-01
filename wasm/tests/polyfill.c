#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

void (*request_read_dictionary_impl)(const uint32_t*, const size_t, const size_t, void*, uint32_t) = NULL;
void request_read_dictionary(const uint32_t* a, const size_t b, const size_t c, void* d, uint32_t e)
{
	request_read_dictionary_impl(a, b, c, d, e);
}

void (*take_a_trip_impl)(const char*) = NULL;
void take_a_trip(const char* msg)
{
	take_a_trip_impl(msg);
}

size_t (*__builtin_wasm_memory_size_impl)(int) = NULL;
size_t __builtin_wasm_memory_size(int i)
{
	return __builtin_wasm_memory_size_impl(i);
}

size_t (*__builtin_wasm_memory_grow_impl)(int, size_t) = NULL;
size_t __builtin_wasm_memory_grow(int i, size_t n)
{
	return __builtin_wasm_memory_grow_impl(i, n);
}

void print(const char* p)
{
	printf("print('%s')\n", p);
}
