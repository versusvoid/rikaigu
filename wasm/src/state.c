#include "state.h"

#include <assert.h>

#include "builtins.h"
#include "imports.h"
#include "libc.h"
#include "index.h"
#include "word_results.h"

typedef enum {
	REVIEW_LIST_BUFFER,
	CANDIDATE_BUFFER,
	INDEX_ENTRY_BUFFER,
	WORD_RESULT_BUFFER,
	RAW_DENTRY_BUFFER,
	DENTRY_BUFFER,
	HTML_BUFFER,

	NUM_BUFFER_TOKENS,
} BUFFER_TOKENS;

const size_t initial_sizes[NUM_BUFFER_TOKENS] = {1<<10, 1<<10, 1<<12, 1<<12, 1<<14, 1<<14, 1<<16};

typedef struct {
	input_t input;
	// NOTE if buffer `i` cross-references buffer `j` (which may be equal `i`),
	// all buffers < `j` mustn't grow
	// Now we have two cross-references:
	// 1. DENTRY -> RAW_DENTRY (at point of referencing all previous buffers are frozen)
	// 2. WORD_RESULT -> DENTY (the same)
	buffer_t buffers[NUM_BUFFER_TOKENS];
} state_t;

state_t* state = NULL;

void split_memory_into_buffers(void* start, size_t capacity_left)
{
	capacity_left -= 8 - ((size_t)start % 8);
	start += 8 - ((size_t)start % 8);

	static_assert(NUM_BUFFER_TOKENS == 7, "Update split_memory_into_buffers()");
	for (size_t i = 0; i < NUM_BUFFER_TOKENS - 1; ++i)
	{
		state->buffers[i].capacity = initial_sizes[i];
		state->buffers[i].size = 0;
		state->buffers[i].data = start;

		capacity_left -= initial_sizes[i];
		start += initial_sizes[i];
	}

	static_assert(HTML_BUFFER == NUM_BUFFER_TOKENS - 1, "wut");
	state->buffers[HTML_BUFFER].capacity = capacity_left;
	state->buffers[HTML_BUFFER].size = 0;
	state->buffers[HTML_BUFFER].data = start;
}

#define PAGE_SIZE_BYTES (1<<16)
void init(size_t heap_base, size_t free_size)
{
	size_t required_size = sizeof(state_t);
	for (size_t i = 0; i < NUM_BUFFER_TOKENS; ++i)
	{
		required_size += initial_sizes[i];
	}
	if (free_size < required_size)
	{
		const size_t diff_bytes = required_size - free_size;
		const size_t diff_pages = diff_bytes / PAGE_SIZE_BYTES + (diff_bytes % PAGE_SIZE_BYTES != 0 ? 1 : 0);
		size_t old_num_pages = __builtin_wasm_memory_grow(0, diff_pages);
		if (old_num_pages == (size_t)-1)
		{
			take_a_trip("can't initialize memory");
		}
		free_size += diff_pages * PAGE_SIZE_BYTES;
	}
	state = (state_t*)heap_base;

	split_memory_into_buffers(state + 1, free_size - sizeof(state_t));
}

void enlarge_your_buffer(buffer_t* buffer, size_t required_place_bytes)
{
	assert(state != NULL);
	if (required_place_bytes > 1<<20)
	{
		take_a_trip("huge allocation asked");
	}

	const size_t buffer_index = buffer - state->buffers;
	// NOTE not effective when allocationg ~PAGE_SIZE_BYTES - 1, but we won't have such huge allocations
	size_t diff_pages = (buffer->capacity > required_place_bytes ? buffer->capacity : required_place_bytes) / PAGE_SIZE_BYTES + 1;
	const size_t old_num_pages = __builtin_wasm_memory_grow(0, diff_pages);
	if (old_num_pages == (size_t)-1)
	{
		take_a_trip("Can't grow memory");
	}

	const size_t offset = diff_pages * PAGE_SIZE_BYTES;
	for (size_t i = NUM_BUFFER_TOKENS - 1; i > buffer_index; --i)
	{
		buffer_t* moved_buffer = &state->buffers[i];
		memcpy_backward(moved_buffer->data + offset, moved_buffer->data, moved_buffer->size);
		moved_buffer->data = moved_buffer->data + offset;
	}

	buffer->capacity += offset;
}

void* buffer_allocate(buffer_t* buffer, size_t num_bytes)
{
	char local = 'a';
	if ((size_t)&local < 256) {
		take_a_trip("going down");
	}

	if (buffer->capacity - buffer->size < num_bytes)
	{
		enlarge_your_buffer(buffer, num_bytes - (buffer->capacity - buffer->size));
	}
	void* res = buffer->data + buffer->size;
	buffer->size += num_bytes;
	return res;
}

export void* rikaigu_set_config(uint32_t heap_base, uint32_t current_memory_size)
{
	if (state == NULL)
	{
		init(heap_base, current_memory_size - heap_base);
	}

	return &state->input;
}

input_t* state_get_input()
{
	return &state->input;
}

void state_clear()
{
	// REVIEW_LIST_BUFFER does not reset
	state->buffers[CANDIDATE_BUFFER].size = 0;
	state->buffers[INDEX_ENTRY_BUFFER].size = 0;
	state->buffers[WORD_RESULT_BUFFER].size = 0;
	state->buffers[RAW_DENTRY_BUFFER].size = 0;
	state->buffers[DENTRY_BUFFER].size = 0;
	state->buffers[HTML_BUFFER].size = 0;
}

buffer_t* state_get_review_list_buffer()
{
	return &state->buffers[REVIEW_LIST_BUFFER];
}

buffer_t* state_get_candidate_buffer()
{
	return &state->buffers[CANDIDATE_BUFFER];
}

buffer_t* state_get_index_entry_buffer()
{
	return &state->buffers[INDEX_ENTRY_BUFFER];
}

buffer_t* state_get_word_result_buffer()
{
	return &state->buffers[WORD_RESULT_BUFFER];
}

buffer_t* state_get_raw_dentry_buffer()
{
	return &state->buffers[RAW_DENTRY_BUFFER];
}

buffer_t* state_get_dentry_buffer()
{
	return &state->buffers[DENTRY_BUFFER];
}

buffer_t* state_get_html_buffer()
{
	return &state->buffers[HTML_BUFFER];
}
