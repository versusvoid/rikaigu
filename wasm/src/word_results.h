#pragma once

#include "state.h"
#include "dentry.h"

typedef struct word_result word_result_t;

bool state_try_add_word_result(
	Dictionary d, const size_t input_length,
	const char16_t* word, const size_t word_length,
	const char* inflection_name, const size_t inflection_name_length,
	const uint32_t offset);

void state_make_offsets_array_and_request_read(uint32_t request_id);


typedef struct word_result_iterator {
	word_result_t* current;
	word_result_t* end;
} word_result_iterator_t;

word_result_iterator_t state_get_word_result_iterator(void);

void word_result_iterator_next(word_result_iterator_t* it);


size_t word_result_get_match_length(word_result_t* wr);

bool word_result_is_name(word_result_t* wr);

size_t word_result_get_inflection_name_length(word_result_t* wr);
char* word_result_get_inflection_name(word_result_t* wr);

void word_result_set_dentry(word_result_t* wr, dentry_t* dentry);
dentry_t* word_result_get_dentry(word_result_t* wr);


