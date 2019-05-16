#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include "fake-memory.h"

#include "../src/state.c"
#include "../src/libc.c"
#include "../src/dentry.c"
#include "../src/utf.c"


void test_init()
{
	setup_memory();
	uint8_t* heap_base = wasm_memory + 31419;
	init((size_t)heap_base, wasm_memory_size_pages * (1<<16) - ((size_t)heap_base - (size_t)wasm_memory));

	assert((uint8_t*)state == heap_base);
	assert(wasm_memory_size_pages == 2);

	uint8_t* suggested_start = heap_base + sizeof(state_t);
	assert(state->buffers[0].data == suggested_start + (8 - ((size_t)suggested_start % 8)));
	for (size_t i = 0; i < NUM_BUFFER_TOKENS; ++i)
	{
		assert(state->buffers[i].size == 0);
	}
	clear_memory();
}

void test_enlarge_your_buffer()
{
	setup_memory();
	uint8_t* heap_base = wasm_memory + 31419;
	init((size_t)heap_base, wasm_memory_size_pages * (1<<16) - ((size_t)heap_base - (size_t)wasm_memory));

	const uint8_t buf0_content[] = {1,2,3,4,5,6,7,8,9,10,11};
	assert(state->buffers[0].capacity >= sizeof(buf0_content));
	memcpy(state->buffers[0].data, buf0_content, sizeof(buf0_content));
	state->buffers[0].size = sizeof(buf0_content);
	const size_t buf0_initial_capacity = state->buffers[0].capacity;

	const uint8_t buf1_content[] = {12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28};
	assert(state->buffers[1].capacity >= sizeof(buf1_content));
	memcpy(state->buffers[1].data, buf1_content, sizeof(buf1_content));
	state->buffers[1].size = sizeof(buf1_content);
	const size_t buf1_initial_capacity = state->buffers[1].capacity;

	const uint8_t buf2_content[] = {29,30,31,32,33,34,35,36,37,38,39,40,41,42,43};
	assert(state->buffers[2].capacity >= sizeof(buf2_content));
	memcpy(state->buffers[2].data, buf2_content, sizeof(buf2_content));
	state->buffers[2].size = sizeof(buf2_content);
	const size_t buf2_initial_capacity = state->buffers[2].capacity;

	assert(state->buffers[0].size == sizeof(buf0_content));
	assert(memcmp(state->buffers[0].data, buf0_content, sizeof(buf0_content)) == 0);
	assert(state->buffers[1].size == sizeof(buf1_content));
	assert(memcmp(state->buffers[1].data, buf1_content, sizeof(buf1_content)) == 0);
	assert(state->buffers[2].size == sizeof(buf2_content));
	assert(memcmp(state->buffers[2].data, buf2_content, sizeof(buf2_content)) == 0);

	enlarge_your_buffer(state->buffers + 1, 25);

	assert(state->buffers[0].size == sizeof(buf0_content));
	assert(state->buffers[0].capacity == buf0_initial_capacity);
	assert(memcmp(state->buffers[0].data, buf0_content, sizeof(buf0_content)) == 0);
	assert(state->buffers[1].size == sizeof(buf1_content));
	assert(state->buffers[1].capacity == buf1_initial_capacity + PAGE_SIZE_BYTES);
	assert(memcmp(state->buffers[1].data, buf1_content, sizeof(buf1_content)) == 0);
	assert(state->buffers[2].size == sizeof(buf2_content));
	assert(state->buffers[2].capacity == buf2_initial_capacity);
	assert(memcmp(state->buffers[2].data, buf2_content, sizeof(buf2_content)) == 0);

	enlarge_your_buffer(state->buffers + 2, PAGE_SIZE_BYTES);

	assert(state->buffers[0].size == sizeof(buf0_content));
	assert(state->buffers[0].capacity == buf0_initial_capacity);
	assert(memcmp(state->buffers[0].data, buf0_content, sizeof(buf0_content)) == 0);
	assert(state->buffers[1].size == sizeof(buf1_content));
	assert(state->buffers[1].capacity == buf1_initial_capacity + PAGE_SIZE_BYTES);
	assert(memcmp(state->buffers[1].data, buf1_content, sizeof(buf1_content)) == 0);
	assert(state->buffers[2].size == sizeof(buf2_content));
	assert(state->buffers[2].capacity == buf2_initial_capacity + 2 * PAGE_SIZE_BYTES);
	assert(memcmp(state->buffers[2].data, buf2_content, sizeof(buf2_content)) == 0);

	enlarge_your_buffer(state->buffers, PAGE_SIZE_BYTES * 3 / 2);

	assert(state->buffers[0].size == sizeof(buf0_content));
	assert(state->buffers[0].capacity == buf0_initial_capacity + 2 * PAGE_SIZE_BYTES);
	assert(memcmp(state->buffers[0].data, buf0_content, sizeof(buf0_content)) == 0);
	assert(state->buffers[1].size == sizeof(buf1_content));
	assert(state->buffers[1].capacity == buf1_initial_capacity + PAGE_SIZE_BYTES);
	assert(memcmp(state->buffers[1].data, buf1_content, sizeof(buf1_content)) == 0);
	assert(state->buffers[2].size == sizeof(buf2_content));
	assert(state->buffers[2].capacity == buf2_initial_capacity + 2 * PAGE_SIZE_BYTES);
	assert(memcmp(state->buffers[2].data, buf2_content, sizeof(buf2_content)) == 0);

	assert(wasm_memory_size_pages == 8);

	clear_memory();
}

void test_buffer_allocate()
{
	setup_memory();

	uint8_t* heap_base = wasm_memory + 31419;
	init((size_t)heap_base, wasm_memory_size_pages * (1<<16) - ((size_t)heap_base - (size_t)wasm_memory));

	const uint8_t buf1_content[] = {12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28};
	assert(state->buffers[1].capacity >= sizeof(buf1_content));
	memcpy(state->buffers[1].data, buf1_content, sizeof(buf1_content));
	state->buffers[1].size = sizeof(buf1_content);
	const void* const old_buf1_data = state->buffers[1].data;

	const size_t buf0_initial_capacity = state->buffers[0].capacity;
	const uint8_t buf0_content1[] = {1,2,3,4,5,6,7,8,9,10,11};
	assert(state->buffers[0].size == 0);
	void* ptr1 = buffer_allocate(state->buffers, sizeof(buf0_content1));
	assert(state->buffers[0].size == sizeof(buf0_content1));
	assert(state->buffers[0].capacity == buf0_initial_capacity);
	assert(ptr1 == state->buffers[0].data);
	memcpy(ptr1, buf0_content1, sizeof(buf0_content1));

	const uint8_t buf0_content2[] = {12,13,14,15,16};
	void* ptr2 = buffer_allocate(state->buffers, sizeof(buf0_content2));
	assert(state->buffers[0].size == sizeof(buf0_content1) + sizeof(buf0_content2));
	assert(state->buffers[0].capacity == buf0_initial_capacity);
	assert(ptr2 == ptr1 + sizeof(buf0_content1));
	memcpy(ptr2, buf0_content2, sizeof(buf0_content2));

	const size_t to_allocate = state->buffers[0].capacity - state->buffers[0].size + 10;
	buffer_allocate(state->buffers, to_allocate);
	assert(state->buffers[0].size == sizeof(buf0_content1) + sizeof(buf0_content2) + to_allocate);
	assert(state->buffers[0].capacity == buf0_initial_capacity + PAGE_SIZE_BYTES);
	assert(memcmp(state->buffers[0].data, buf0_content1, sizeof(buf0_content1)) == 0);
	assert(memcmp(state->buffers[0].data + sizeof(buf0_content1), buf0_content2, sizeof(buf0_content2)) == 0);

	assert(memcmp(state->buffers[1].data, buf1_content, sizeof(buf1_content)) == 0);
	assert(state->buffers[1].data == old_buf1_data + PAGE_SIZE_BYTES);

	clear_memory();
}

int main()
{
	test_enlarge_your_buffer();
	test_buffer_allocate();

	return 0;
}
