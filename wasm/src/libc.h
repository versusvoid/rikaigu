#pragma once
#include <stddef.h>
#include <stdbool.h>

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

// __attribute__((__format__(__printf__, 1, 2)))
int consolef(const char* format, ...);
