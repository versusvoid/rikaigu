#pragma once

#include <stdint.h>
#include <stddef.h>

#include "libc.h"

typedef struct {
	size_t word_length;
	char16_t* word;

	size_t inflection_name_length;
	char* inflection_name;

	uint32_t type;
} candidate_t;

candidate_t* deinflect(const char16_t* word, size_t length);

candidate_t* candidate_next(candidate_t*);
