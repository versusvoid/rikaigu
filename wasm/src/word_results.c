#include "word_results.h"

#include <assert.h>

#include "state.h"
#include "libc.h"
#include "vardata_array.h"
#include "imports.h"
#include "utf.h"

typedef struct word_result {
	uint32_t offset;

	size_t vardata_start_offset;
	uint8_t key_length;
	uint8_t inflection_name_length;

	uint8_t match_utf16_length;
	bool is_name;

	dentry_t* dentry;
} word_result_t;

size_t word_result_copy_new_data(
	buffer_t* b,
	const char16_t* word, const size_t word_length,
	const char* inflection_name, const size_t inflection_name_length
	)
{
	const size_t word_num_bytes = word_length * sizeof(char16_t);
	void* new_element_vardata_start = vardata_array_reserve_place_for_element(b, word_num_bytes + inflection_name_length);
	memcpy(new_element_vardata_start, word, word_num_bytes);
	memcpy(new_element_vardata_start + word_num_bytes, inflection_name, inflection_name_length);

	return new_element_vardata_start - vardata_array_vardata_start(b);
}

int uniq_dentry_cmp(const void* key, const void* object)
{
	const word_result_t* a = key;
	const word_result_t* b = object;

	if (a->is_name != b->is_name)
	{
		return (int)a->is_name - (int)b->is_name;
	}
	return (int)a->offset - (int)b->offset;
}

bool state_try_add_word_result(
	Dictionary d, const size_t input_length,
	const char16_t* word, const size_t word_length,
	const char* inflection_name, const size_t inflection_name_length,
	const uint32_t offset)
{
	buffer_t* b = state_get_word_result_buffer();
	if (b->size == 0)
	{
		vardata_array_make(b, sizeof(word_result_t));
	}

	word_result_t* array = vardata_array_elements_start(b);
	const size_t num_elements = vardata_array_num_elements(b);
	word_result_t new_wr = {
		.offset = offset,
		.match_utf16_length = input_length,
		.is_name = d == NAMES,
		.key_length = word_length,
		.inflection_name_length = inflection_name_length,
		.vardata_start_offset = 0,
		.dentry = NULL,
	};
	bool found;
	word_result_t* it = binary_locate(
		&new_wr, array,
		num_elements, sizeof(word_result_t),
		uniq_dentry_cmp, &found
	);
	if (found)
	{
		return false;
	}

	new_wr.vardata_start_offset = word_result_copy_new_data(b, word, word_length, inflection_name, inflection_name_length);
	const size_t index = it - array;
	vardata_array_increment_size(b);
	memmove(it + 1, it, (num_elements - index) * sizeof(word_result_t));
	memcpy(it, &new_wr, sizeof(word_result_t));

	return true;
}

int sort_cmp(const void* key, const void* object)
{
       const word_result_t* a = key;
       const word_result_t* b = object;

       if (a->match_utf16_length != b->match_utf16_length)
       {
               return -((int)a->match_utf16_length - (int)b->match_utf16_length);
       }
       if (a->is_name != b->is_name)
       {
               return (int)a->is_name - (int)b->is_name;
       }
       return -((int)a->inflection_name_length - (int)b->inflection_name_length);
}

size_t locate_sorted(word_result_t* array, const size_t i)
{
       bool found;
       word_result_t* it = binary_locate(
               array + i, array,
               i, sizeof(word_result_t),
               sort_cmp, &found
       );
       return it - array;
}

void sort_results(word_result_t* array, const size_t num_elements)
{
       for (size_t i = 0; i < num_elements; ++i)
       {
               size_t to_index = locate_sorted(array, i);
               if (to_index == i)
               {
                       continue;
               }

               word_result_t tmp = array[i];
               memmove(array + to_index + 1, array + to_index, (i - to_index) * sizeof(word_result_t));
               array[to_index] = tmp;
       }
}

size_t sort_and_limit_word_results(buffer_t* b, word_result_t* array)
{
	size_t num_elements = vardata_array_num_elements(b);
	sort_results(array, num_elements);

	if (num_elements > 32)
	{
		num_elements = 32;
		vardata_array_set_size(b, 32);
	}
	return num_elements;
}

void state_make_offsets_array_and_request_read(uint32_t request_id)
{
	buffer_t* b = state_get_word_result_buffer();
	word_result_t* array = vardata_array_elements_start(b);
	size_t num_elements = sort_and_limit_word_results(b, array);

	const size_t padding = 4 - b->size % 4;
	uint32_t* offsets = buffer_allocate(b, num_elements * sizeof(uint32_t) + padding) + padding;

	for (size_t i = 0; i < num_elements; ++i)
	{
		if (array[i].is_name)
		{
			offsets[i] = (1u << 31) | array[i].offset;
		}
		else
		{
			offsets[i] = array[i].offset;
		}
	}

	buffer_t* raw_dentry_buffer = state_get_raw_dentry_buffer();
	request_read_dictionary(offsets, num_elements, raw_dentry_buffer, request_id);
}

void word_result_set_dentry(word_result_t* wr, dentry_t* dentry)
{
	wr->dentry = dentry;
}

void state_polish_word_results()
{
	buffer_t* b = state_get_word_result_buffer();
	const void* const vardata_start = vardata_array_vardata_start(b);

	const input_t* input = state_get_input();
	const bool reading_key = is_hiragana(input->data, input->length);

	word_result_t* it = vardata_array_elements_start(b);
	const word_result_t* const end = it + vardata_array_num_elements(b);
	for (; it < end; ++it)
	{
		if (it->is_name && reading_key)
		{
			dentry_drop_kanji_groups(it->dentry);
		}

		dentry_parse(it->dentry);

		const char16_t* key = vardata_start + it->vardata_start_offset;
		if (reading_key)
		{
			dentry_filter_readings(it->dentry, key, it->key_length);
		}
		else
		{
			dentry_filter_kanji_groups(it->dentry, key, it->key_length);
		}
	}
}

word_result_iterator_t state_get_word_result_iterator()
{
	buffer_t* b = state_get_word_result_buffer();

	word_result_t* array = vardata_array_elements_start(b);
	const size_t num_elements = vardata_array_num_elements(b);
	word_result_iterator_t res = {
		.current = array,
		.end = array + num_elements,
	};
	return res;
}

void word_result_iterator_next(word_result_iterator_t* it)
{
	assert(it->current != it->end);
	it->current += 1;
}

size_t word_result_get_match_length(word_result_t* wr)
{
	return wr->match_utf16_length;
}

bool word_result_is_name(word_result_t* wr)
{
	return wr->is_name;
}

size_t word_result_get_inflection_name_length(word_result_t* wr)
{
	return wr->inflection_name_length;
}

char* word_result_get_inflection_name(word_result_t* wr)
{
	buffer_t* b = state_get_word_result_buffer();
	return (char*)(
		vardata_array_vardata_start(b)
		+ wr->vardata_start_offset
		+ wr->key_length * sizeof(char16_t)
	);
}

dentry_t* word_result_get_dentry(word_result_t* wr)
{
	return wr->dentry;
}
