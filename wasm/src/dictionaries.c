#include <stddef.h>
#include <uchar.h>
#include <stdbool.h>
#include <assert.h>

#include "state.h"
#include "dentry.h"
#include "imports.h"
#include "index.h"
#include "libc.h"
#include "deinflect.h"
#include "word_results.h"
#include "utf.h"

bool word_search(Dictionary d, const size_t input_length,
	const char16_t* word, const size_t word_length,
	const uint32_t required_type,
	const char* inflection_name, const size_t inflection_name_length)
{
	dictionary_index_entry_t* entry = get_index_entry(d, word, word_length);
	if (entry == NULL)
	{
		return false;
	}

	bool found = 0;
	uint32_t entry_type, offset;
	offsets_iterator_t it = dictionary_index_entry_get_offsets_iterator(entry);
	while (offsets_iterator_read_next(&it, &entry_type, &offset))
	{
		if (required_type != 0 && (entry_type & required_type) == 0)
		{
			continue;
		}

		found |= state_try_add_word_result(
			d, input_length,
			word, word_length,
			inflection_name, inflection_name_length,
			offset
		);
	}

	return found;
}

size_t input_search(const input_t* input, Dictionary dictionary)
{
	size_t max_match_length = 0;
	size_t input_length = input->length;
	for (; input_length > 0; input_length = utf16_drop_code_point(input->data, input_length))
	{
		bool found = word_search(dictionary, input_length, input->data, input_length, 0, NULL, 0);

		if (dictionary == WORDS)
		{
			candidate_t* c = deinflect(input->data, input_length);
			for (; c != NULL; c = candidate_next(c))
			{
				found |= word_search(dictionary, input_length, c->word, c->word_length, c->type, c->inflection_name, c->inflection_name_length);
			}
		}

		if (found && max_match_length == 0)
		{
			max_match_length = input_length;
		}
	}

	return max_match_length;
}

bool word_search_finish(buffer_t* raw_dentry_buffer)
{
	void* data = raw_dentry_buffer->data;
	const void* const end = data + raw_dentry_buffer->size;
	size_t dentry_index = 0;
	word_result_iterator_t it = state_get_word_result_iterator();
	while (data < end)
	{
		const uint16_t line_length = *(uint16_t*)data;
		dentry_t* dentry = dentry_make(data + sizeof(uint16_t), line_length, word_result_is_name(it.current));
		word_result_set_dentry(it.current, dentry);

		data += sizeof(uint16_t) + line_length;
		dentry_index += 1;
		word_result_iterator_next(&it);
	}

	return true;
}

size_t search_start(size_t utf16_input_length, uint32_t request_id)
{
	input_t* input = state_get_input();
	assert(utf16_input_length < 32);
	input->length = utf16_input_length;
	input_kata_to_hira(input);

	const size_t max_words_match_length = input_search(input, WORDS);
	const size_t max_names_match_length = input_search(input, NAMES);

	const size_t max_match_length = max_words_match_length > max_names_match_length ? max_words_match_length : max_names_match_length;

	if (max_match_length > 0)
	{
		state_make_offsets_array_and_request_read(request_id);
		return input->length_mapping[max_match_length];
	}
	else
	{
		return 0;
	}
}

bool search_finish(buffer_t* raw_dentry_buffer)
{
	return word_search_finish(raw_dentry_buffer);
}
