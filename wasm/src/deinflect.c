#include "deinflect.h"

#include <assert.h>
#include <uchar.h>

#include "state.h"
#include "libc.h"
#include "utf.h"
#include "../generated/deinflection-info.bin.c"

void apply_rule(buffer_t* buffer, const deinflection_rule_t* r, const size_t suffix_length,
	const char16_t* word, const size_t length,
	const char* inflection_name, const size_t inflection_name_length)
{
	assert(length >= suffix_length);
	const size_t new_inflection_name_length =
		inflection_name_length == 0
		? r->inflection_name_length
		: inflection_name_length + 1 + r->inflection_name_length;
	/*
	 * Memory layout of candidates:
	 * [
	 * 	candidate_t #1,
	 * 	word of candidate #1,
	 * 	inflection_name of candidate #1,
	 * 	candidate_t #2,
	 * 	word of candidate #2,
	 * 	inflection_name of candidate #2,
	 * 	...
	 * ]
	 */
	void* m = buffer_allocate(buffer,
		sizeof(candidate_t)
		+ (length - suffix_length + r->new_suffix_length) * sizeof(char16_t)
		+ new_inflection_name_length
	);
	candidate_t* new = m;

	new->word_length = (length - suffix_length + r->new_suffix_length);
	new->word = m + sizeof(candidate_t);
	memcpy(new->word, word, (length - suffix_length) * sizeof(char16_t));
	memcpy(new->word + length - suffix_length, r->new_suffix, r->new_suffix_length * sizeof(char16_t));

	new->inflection_name_length = new_inflection_name_length;
	new->inflection_name = (char*)(new->word + new->word_length);
	if (new_inflection_name_length == r->inflection_name_length)
	{
		memcpy(new->inflection_name, r->inflection_name, r->inflection_name_length);
	}
	else
	{
		memcpy(new->inflection_name, inflection_name, inflection_name_length);
		new->inflection_name[inflection_name_length] = ',';
		memcpy(new->inflection_name + inflection_name_length + 1, r->inflection_name, r->inflection_name_length);
	}

	new->type = r->target_pos_mask;
}

typedef struct {
	const char16_t* suffix;
	size_t suffix_length;
} deinflection_rule_search_context_t;

int deinflection_rule_search_cmp(const void* key, const void* object)
{
	const deinflection_rule_search_context_t* c = key;
	const deinflection_rule_t* r = object;

	return utf16_compare(c->suffix, c->suffix_length, r->suffix, c->suffix_length);
}

bool rule_index_bounds_for_suffix(const char16_t* suffix, const size_t suffix_length, size_t* out_low, size_t* out_high)
{
	const size_t low = first_suffix_of_length_position[suffix_length];
	const size_t high = first_suffix_of_length_position[suffix_length - 1];
	deinflection_rule_search_context_t c = {
		.suffix = suffix,
		.suffix_length = suffix_length,
	};

	bool found = binary_locate_bounds(
		&c, rules + low,
		high - low, sizeof(deinflection_rule_t),
		deinflection_rule_search_cmp,
		out_low, out_high
	);
	if (found)
	{
		*out_low += low;
		*out_high += low;
	}
	return found;
}

void deinflect_one_word(buffer_t* buffer, POS_FLAGS pos,
	const char16_t* word, const size_t length,
	const char* inflection_name, const size_t inflection_name_length)
{
	const size_t max_rule_suffix_length = sizeof(first_suffix_of_length_position) / sizeof(size_t) - 1;
	size_t suffix_length = max_rule_suffix_length > length ? length : max_rule_suffix_length;
	for (; suffix_length >= 1; --suffix_length)
	{
		const char16_t* suffix_start = word + length - suffix_length;
		size_t rule_index, end;
		if (!rule_index_bounds_for_suffix(suffix_start, suffix_length, &rule_index, &end))
		{
			continue;
		}

		for (; rule_index < end; ++rule_index)
		{
			const deinflection_rule_t* r = rules + rule_index;
			if ((pos & r->source_pos_mask) == 0)
			{
				continue;
			}

			apply_rule(buffer, r, suffix_length, word, length, inflection_name, inflection_name_length);
		}

	}
}

candidate_t* deinflect(const char16_t* word, size_t length)
{
	buffer_t* buffer = state_get_candidate_buffer();
	buffer->size = 0;

	deinflect_one_word(buffer, ANY_POS, word, length, NULL, 0);
	if (buffer->size == 0)
	{
		return NULL;
	}

	candidate_t* it = buffer->data;
	for(; it != NULL; it = candidate_next(it))
	{
		deinflect_one_word(buffer, it->type, it->word, it->word_length, it->inflection_name, it->inflection_name_length);
	}
	return buffer->data;
}

candidate_t* candidate_next(candidate_t* it)
{
	void* next_pos = (void*)(it->inflection_name + it->inflection_name_length);
	buffer_t* buffer = state_get_candidate_buffer();
	assert(next_pos <= buffer->data + buffer->size);
	if (buffer->data + buffer->size > next_pos)
	{
		return (candidate_t*)next_pos;
	}
	else
	{
		return NULL;
	}
}
