#pragma once

#include <stddef.h>
#include <stdint.h>
#include <uchar.h>

#include "state.h"

typedef struct dictionary_index_entry dictionary_index_entry_t;

dictionary_index_entry_t* get_index_entry(Dictionary d, const char16_t* needle, size_t needle_length);

typedef struct {
	uint32_t* current;
	uint32_t* end;
} offsets_iterator_t;

offsets_iterator_t dictionary_index_entry_get_offsets_iterator(dictionary_index_entry_t* entry);

bool offsets_iterator_read_next(offsets_iterator_t* it, uint32_t* type, uint32_t* offset);
