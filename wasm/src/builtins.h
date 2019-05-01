#pragma once
#include <stddef.h>

extern size_t __builtin_wasm_memory_size(int);
extern size_t __builtin_wasm_memory_grow(int, size_t);

