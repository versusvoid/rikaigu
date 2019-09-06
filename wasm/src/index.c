#include "index.h"

#include <stdbool.h>
#include <assert.h>

#include "imports.h"
#include "libc.h"
#include "vardata_array.h"
#include "utf.h"
#include "decompress.h"

#include "../generated/config.h"
#include "../generated/index.h"

compressed_file_t words_index = {
	.last_chunk_index = words_dictionary_index_last_chunk_index,
	.last_chunk_size = words_dictionary_index_last_chunk_size,
	.original_size = words_dictionary_index_original_size,
	.chunks_offsets = words_dictionary_index_chunks_offsets,
	.data = words_dictionary_index_data,
	.currently_decompressed_chunk_index = SIZE_MAX,
};

compressed_file_t names_index = {
	.last_chunk_index = names_dictionary_index_last_chunk_index,
	.last_chunk_size = names_dictionary_index_last_chunk_size,
	.original_size = names_dictionary_index_original_size,
	.chunks_offsets = names_dictionary_index_chunks_offsets,
	.data = names_dictionary_index_data,
	.currently_decompressed_chunk_index = SIZE_MAX,
};

struct dictionary_index_entry {
	size_t start_position_in_index;
	size_t end_position_in_index;
	size_t key_length;
	size_t num_offsets;
	size_t vardata_start_offset;
};

struct {
	size_t start_position_in_index;
	size_t end_position_in_index;
	size_t key_length;
	char16_t* key;
	size_t num_offsets;
	uint32_t* offsets;
} current_index_entry = {0};

uint8_t index_entry_buffer[dictionary_index_max_entry_length];

inline bool is_offset_or_type(char16_t v)
{
	return (v & dictionary_index_offset_prefix_mask) == dictionary_index_offset_prefix;
}

ptrdiff_t find_index_entry_start_offset(size_t position_in_chunk)
{
	const char16_t* const begin = (char16_t*)decompressed_chunk;
	const char16_t* current = (char16_t*)(decompressed_chunk + position_in_chunk);
	while (current >= begin && is_offset_or_type(*current))
	{
		current -= 1;
	}
	while (current >= begin && !is_offset_or_type(*current))
	{
		current -= 1;
	}

	return current >= begin ? ((const uint8_t*)(current + 1) - decompressed_chunk) : -1;
}

ptrdiff_t find_index_entry_start_offset_in_previous_chunk(char16_t index_entry_second_part_first_char16)
{
	// previous chunk is always of CHUNK_SIZE
	const char16_t last_char16 = *(char16_t*)(decompressed_chunk + CHUNK_SIZE - 2);
	if (!is_offset_or_type(index_entry_second_part_first_char16) && is_offset_or_type(last_char16))
	{
		// edge case when previous entry ended on chunk boundary
		return CHUNK_SIZE;
	}

	// -2 because find_index_entry_start_offset(pos) iterates backward and start reading
	// at `decompressed_chunk[pos]`
	return find_index_entry_start_offset(CHUNK_SIZE - 2);
}

ptrdiff_t find_index_entry_end_offset(size_t real_chunk_size, size_t position_in_chunk)
{
	const char16_t* const end = (char16_t*)(decompressed_chunk + real_chunk_size);
	const char16_t* current = (char16_t*)(decompressed_chunk + position_in_chunk);
	while (current < end && !is_offset_or_type(*current))
	{
		current += 1;
	}
	while (current < end && is_offset_or_type(*current))
	{
		current += 1;
	}

	return current < end ? ((const uint8_t*)current - decompressed_chunk) : -1;
}

ptrdiff_t find_index_entry_end_offset_in_next_chunk(size_t real_chunk_size, char16_t index_entry_first_part_last_char16)
{
	const char16_t first_char16 = *(char16_t*)decompressed_chunk;
	if (is_offset_or_type(index_entry_first_part_last_char16) && !is_offset_or_type(first_char16))
	{
		// edge case when entry ended on chunk boundary
		return 0;
	}
	return find_index_entry_end_offset(real_chunk_size, 0);
}

size_t find_index_entry_offsets_start_position(const uint8_t* index_entry_start, const size_t index_entry_length)
{
	const char16_t* const end = (const char16_t*)(index_entry_start + index_entry_length);
	const char16_t* current = (const char16_t*)index_entry_start;
	while (current < end && !is_offset_or_type(*current))
	{
		current += 1;
	}

	if (current == end)
	{
		take_a_trip("Can't find offsets start in index entry");
	}
	return (const uint8_t*)current - index_entry_start;
}

void current_index_entry_fill(uint8_t* index_entry_start, const size_t index_entry_length, const size_t start_position_in_index)
{
	assert(index_entry_length <= dictionary_index_max_entry_length);
	current_index_entry.start_position_in_index = start_position_in_index;
	current_index_entry.end_position_in_index = start_position_in_index + index_entry_length;

	size_t offsets_start_pos = find_index_entry_offsets_start_position(index_entry_start, index_entry_length);
	current_index_entry.key_length = offsets_start_pos / 2;
	current_index_entry.key = (char16_t*)index_entry_start;

	current_index_entry.num_offsets = (index_entry_length - offsets_start_pos) / 4;
	current_index_entry.offsets = (uint32_t*)(index_entry_start + offsets_start_pos);
}

void get_index_entry_at(compressed_file_t* index, size_t position)
{
	// All data in index (utf16 character or 4-bytes offset) is at least 2-aligned
	// so we can always start at 2-aligned position
	position -= (position % 2);

	const size_t chunk_index = position / CHUNK_SIZE;
	decompress_chunk(index, chunk_index);

	const size_t position_in_chunk = position % CHUNK_SIZE;
	ptrdiff_t entry_start_offset = find_index_entry_start_offset(position_in_chunk);

	size_t real_chunk_size = get_real_chunk_size(index, chunk_index);
	ptrdiff_t entry_end_offset = find_index_entry_end_offset(real_chunk_size, position_in_chunk);

	assert(entry_start_offset != -1 || entry_end_offset != -1);
	if (entry_start_offset == -1 && chunk_index == 0)
	{
		entry_start_offset = 0;
	}
	if (entry_end_offset == -1 && chunk_index == index->last_chunk_index)
	{
		entry_end_offset = real_chunk_size;
	}

	uint8_t* index_entry_start = NULL;
	size_t index_entry_length = 0;
	size_t start_position_in_index = 0;
	if (entry_start_offset == -1)
	{
		// Searching for index entry start in previous chunk

		memcpy(index_entry_buffer + sizeof(index_entry_buffer) - entry_end_offset, decompressed_chunk, entry_end_offset);

		decompress_chunk(index, chunk_index - 1);

		const char16_t index_entry_second_part_first_char16 = *(char16_t*)(index_entry_buffer + sizeof(index_entry_buffer) - entry_end_offset);
		entry_start_offset = find_index_entry_start_offset_in_previous_chunk(index_entry_second_part_first_char16);
		assert(entry_start_offset != -1);

		// Previous chunk is always of CHUNK_SIZE
		size_t prefix_length = CHUNK_SIZE - entry_start_offset;

		index_entry_start = index_entry_buffer + sizeof(index_entry_buffer) - entry_end_offset - prefix_length;
		index_entry_length = prefix_length + entry_end_offset;
		start_position_in_index = (chunk_index - 1)*CHUNK_SIZE + entry_start_offset;

		memcpy(index_entry_start, decompressed_chunk + entry_start_offset, prefix_length);
	}
	else if (entry_end_offset == -1)
	{
		// Searching for index entry end in next chunk

		size_t prefix_length = real_chunk_size - entry_start_offset;
		memcpy(index_entry_buffer, decompressed_chunk + entry_start_offset, prefix_length);

		decompress_chunk(index, chunk_index + 1);

		real_chunk_size = get_real_chunk_size(index, chunk_index + 1);
		const char16_t index_entry_first_part_last_char16 = *(char16_t*)(index_entry_buffer + prefix_length - 2);
		entry_end_offset = find_index_entry_end_offset_in_next_chunk(real_chunk_size, index_entry_first_part_last_char16);
		assert(entry_end_offset != -1);

		index_entry_start = index_entry_buffer;
		index_entry_length = prefix_length + entry_end_offset;
		start_position_in_index = chunk_index*CHUNK_SIZE + entry_start_offset;

		memcpy(index_entry_buffer + prefix_length, decompressed_chunk, entry_end_offset);
	}
	else
	{
		index_entry_start = index_entry_buffer;
		index_entry_length = entry_end_offset - entry_start_offset;
		start_position_in_index = chunk_index*CHUNK_SIZE + entry_start_offset;

		memcpy(index_entry_buffer, decompressed_chunk + entry_start_offset, index_entry_length);
	}

	current_index_entry_fill(
		index_entry_start, index_entry_length,
		start_position_in_index
	);
}

void current_index_entry_decode_offsets()
{
	const uint16_t sm = dictionary_index_offset_suffix_mask;
	const uint32_t shift2 = 16 - dictionary_index_offset_prefix_len;

	uint32_t* it = current_index_entry.offsets;
	const uint32_t* const end = it + current_index_entry.num_offsets;
	for (; it < end; ++it)
	{
		uint16_t* halves = (uint16_t*)it;
		uint32_t h1 = halves[0];
		uint32_t h2 = halves[1];
		*it = (h1 & sm) | ((h2 & sm) << shift2);
	}
}

bool dictionary_index_search_for_offsets(
	compressed_file_t* index, const char16_t* needle, size_t search_length,
	size_t low, size_t high
	)
{
	while (low < high)
	{
		size_t mid = (low + high) / 2;
		get_index_entry_at(index, mid);
		int order = utf16_compare(
			current_index_entry.key, current_index_entry.key_length,
			needle, search_length
		);
		if (order < 0)
		{
			low = current_index_entry.end_position_in_index;
		}
		else if (order > 0)
		{
			high = current_index_entry.start_position_in_index;
		}
		else
		{
			current_index_entry_decode_offsets();
			return true;
		}
	}

	return false;
}

dictionary_index_entry_t* index_entries_cache_clear(buffer_t* b)
{
	vardata_array_make(b, sizeof(dictionary_index_entry_t));
	return vardata_array_elements_start(b);
}

typedef struct {
	const char16_t* needle;
	const size_t needle_length;
	const void* data_start;
} index_entries_cache_search_context_t;

int index_entries_cache_cmp(const void* key, const void* object)
{
	const index_entries_cache_search_context_t* c = key;
	const dictionary_index_entry_t* e = object;

	return utf16_compare(
		c->needle, c->needle_length,
		(const char16_t*)(c->data_start + e->vardata_start_offset), e->key_length
	);
}

dictionary_index_entry_t* index_entries_cache_locate_entry(
	buffer_t* b, const char16_t* needle, size_t needle_length,
	size_t* low, size_t* high, bool* found
	)
{
	index_entries_cache_search_context_t c = {
		.needle = needle,
		.needle_length = needle_length,
		.data_start = vardata_array_vardata_start(b),
	};

	dictionary_index_entry_t* array = vardata_array_elements_start(b);
	const size_t num_elements = vardata_array_num_elements(b);
	dictionary_index_entry_t* it = binary_locate(
		&c, array,
		num_elements, sizeof(dictionary_index_entry_t),
		index_entries_cache_cmp, found
	);
	if (*found)
	{
		return it;
	}

	if (it > array)
	{
		*low = (it - 1)->end_position_in_index;
	}
	if (it < array + num_elements)
	{
		*high = it->start_position_in_index;
	}
	return it;
}

size_t index_entries_cache_copy_current_data(buffer_t* b)
{
	const size_t key_size = current_index_entry.key_length * sizeof(char16_t);
	const size_t offsets_size = current_index_entry.num_offsets * sizeof(uint32_t);

	void* new_entry_vardata_start = vardata_array_reserve_place_for_element(b, key_size + offsets_size);
	memcpy(new_entry_vardata_start, current_index_entry.key, key_size);
	memcpy(new_entry_vardata_start + key_size, current_index_entry.offsets, offsets_size);

	return new_entry_vardata_start - vardata_array_vardata_start(b);
}

void index_entries_cache_add_current(buffer_t* b, dictionary_index_entry_t* it)
{
	const size_t vardata_start_offset = index_entries_cache_copy_current_data(b);

	dictionary_index_entry_t* array = vardata_array_elements_start(b);
	const size_t num_elements = vardata_array_num_elements(b);

	vardata_array_increment_size(b);
	memmove(it + 1, it, (array + num_elements - it) * sizeof(dictionary_index_entry_t));

	it->start_position_in_index = current_index_entry.start_position_in_index;
	it->end_position_in_index = current_index_entry.end_position_in_index;
	it->key_length = current_index_entry.key_length;
	it->num_offsets = current_index_entry.num_offsets;
	it->vardata_start_offset = vardata_start_offset;
}

dictionary_index_entry_t* dictionary_index_get_entry(compressed_file_t* d, const char16_t* needle, size_t needle_length)
{
	buffer_t* buf = state_get_index_entry_buffer();

	size_t low = 0;
	dictionary_index_entry_t* it = NULL;
	size_t high = d->original_size;
	if (d != currently_decompressed_file)
	{
		// we search indices separately (only words, then only names)
		// and assume cache contains only words OR only names
		// if d != currently_decompressed_file, then we switched index
		// and need to clear cache
		it = index_entries_cache_clear(buf);
	}
	else
	{
		bool found;
		it = index_entries_cache_locate_entry(
			buf, needle, needle_length,
			&low, &high, &found
		);
		if (found)
		{
			return it;
		}
	}

	if (!dictionary_index_search_for_offsets(d, needle, needle_length, low, high))
	{
		return NULL;
	}

	index_entries_cache_add_current(buf, it);
	return it;
}

dictionary_index_entry_t* get_index_entry(Dictionary d, const char16_t* needle, size_t needle_length)
{
	if (d == WORDS)
	{
		return dictionary_index_get_entry(&words_index, needle, needle_length);
	}
	else
	{
		return dictionary_index_get_entry(&names_index, needle, needle_length);
	}
}

size_t dictionary_index_entry_num_offsets(dictionary_index_entry_t* entry)
{
	return entry->num_offsets;
}

offsets_iterator_t dictionary_index_entry_get_offsets_iterator(dictionary_index_entry_t* entry)
{
	buffer_t* b = state_get_index_entry_buffer();
	void* data_start = vardata_array_vardata_start(b) + entry->vardata_start_offset;
	uint32_t* offsets = data_start + entry->key_length * sizeof(char16_t);
	return (offsets_iterator_t) {
		.current = offsets,
		.end = offsets + entry->num_offsets,
	};
}

bool offsets_iterator_read_next(offsets_iterator_t* it, uint32_t* type, uint32_t* offset)
{
	if (it->current >= it->end)
	{
		return false;
	}

	if (*it->current & dictionary_index_type_bit)
	{
		*type = *it->current & ~dictionary_index_type_bit;
		*offset = *(it->current + 1);
		it->current += 2;
	}
	else
	{
		*type = 0;
		*offset = *it->current;
		it->current += 1;
	}
	return true;
}
