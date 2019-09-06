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
#include "decompress.h"

#include "../generated/config.h"
#include "../generated/dictionary.h"

compressed_file_t words_dictionary = {
	.last_chunk_index = words_dictionary_last_chunk_index,
	.last_chunk_size = words_dictionary_last_chunk_size,
	.original_size = words_dictionary_original_size,
	.chunks_offsets = words_dictionary_chunks_offsets,
	.data = words_dictionary_data,
	.currently_decompressed_chunk_index = SIZE_MAX,
};

compressed_file_t names_dictionary = {
	.last_chunk_index = names_dictionary_last_chunk_index,
	.last_chunk_size = names_dictionary_last_chunk_size,
	.original_size = names_dictionary_original_size,
	.chunks_offsets = names_dictionary_chunks_offsets,
	.data = names_dictionary_data,
	.currently_decompressed_chunk_index = SIZE_MAX,
};

static bool copy_until_newline(buffer_t* b, size_t position_in_chunk, size_t real_chunk_size)
{
	char* const start = (char*)(decompressed_chunk + position_in_chunk);
	char* const end = (char*)(decompressed_chunk + real_chunk_size);
	const size_t num_bytes_to_copy = find_char(start, end, '\n') - start;

	char* const to = buffer_allocate(b, num_bytes_to_copy);
	memcpy(to, start, num_bytes_to_copy);
	return num_bytes_to_copy < (size_t)(end - start);
}

const char* get_dentry_at(buffer_t* b, compressed_file_t* dictionary, size_t position)
{
	const char* const start = b->data + b->size;

	size_t chunk_index = position / CHUNK_SIZE;
	decompress_chunk(dictionary, chunk_index);

	size_t position_in_chunk = position % CHUNK_SIZE;
	bool seen_newline = copy_until_newline(b, position_in_chunk, get_real_chunk_size(dictionary, chunk_index));
	while (!seen_newline) {
		chunk_index += 1;
		decompress_chunk(dictionary, chunk_index);

		position_in_chunk = 0;
		seen_newline = copy_until_newline(b, position_in_chunk, get_real_chunk_size(dictionary, chunk_index));
	}

	return start;
}

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

void get_and_parse_dentries(const size_t num_word_results)
{
	buffer_t* b = state_get_raw_dentry_buffer();
	const char** raw_dentries = buffer_allocate(b, sizeof(const char*) * (num_word_results + 1));

	// Loading and parsing dentries in two phases so that pointers in dentry buffer won't
	// become invalid in case of raw dentry buffer enlargement
	word_result_iterator_t it = state_get_word_result_iterator();
	size_t raw_dentry_index = 0;
	while (it.current < it.end)
	{
		raw_dentries[raw_dentry_index] = get_dentry_at(
			b,
			word_result_is_name(it.current) ? &names_dictionary : &words_dictionary,
			word_result_get_offset(it.current)
		);
		word_result_iterator_next(&it);
		raw_dentry_index += 1;
	}
	raw_dentries[raw_dentry_index] = b->data + b->size;

	it = state_get_word_result_iterator();
	raw_dentry_index = 0;
	while (it.current < it.end)
	{
		word_result_set_dentry(
			it.current,
			dentry_make(
				raw_dentries[raw_dentry_index],
				raw_dentries[raw_dentry_index + 1] - raw_dentries[raw_dentry_index],
				word_result_is_name(it.current)
			)
		);
		word_result_iterator_next(&it);
		raw_dentry_index += 1;
	}
}

size_t search(size_t utf16_input_length)
{
	input_t* input = state_get_input();
	assert(utf16_input_length < 32);
	input->length = utf16_input_length;
	input_kata_to_hira(input);

	const size_t max_words_match_length = input_search(input, WORDS);
	const size_t max_names_match_length = input_search(input, NAMES);

	const size_t max_match_length = max_words_match_length > max_names_match_length ? max_words_match_length : max_names_match_length;
	if (max_match_length == 0) {
		return max_match_length;
	}

	const size_t num_word_results = state_sort_and_limit_word_results();

	get_and_parse_dentries(num_word_results);

	return max_match_length;
}
