#pragma once
#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

#ifndef NDEBUG
#include <assert.h>
#else
#define assert(expr)
#define static_assert _Static_assert
#endif

#ifdef TRACE
#undef TRACE
#define TRACE(format, ...) consolef("%s " format, __PRETTY_FUNCTION__, sizeof(__PRETTY_FUNCTION__) - 1, __VA_ARGS__)
#else
#define TRACE(format, ...)
#endif

typedef uint_least16_t char16_t;

void* memcpy(void* dest, const void* src, size_t n);
void* memcpy_backward(void* dest, const void* src, size_t n);
void* memmove(void* dest, const void* src, size_t n);
void memzero(void* dest, size_t n);
void* binary_locate(
	const void *key, const void *array,
	size_t num_elements, size_t element_size,
	int (*compar)(const void*, const void*), bool* found
);
bool binary_locate_bounds(
	const void *key, const void *array,
	size_t num_elements, size_t element_size,
	int (*compar)(const void*, const void*),
	size_t* lower, size_t* upper
);

const char* find_char(const char* start, const char* end, const char c);

// __attribute__((__format__(__printf__, 1, 2)))
int consolef(const char* format, ...);
