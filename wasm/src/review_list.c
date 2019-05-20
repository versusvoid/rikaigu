#include "review_list.h"

#include "state.h"
#include "libc.h"

int entry_id_cmp(const void* key, const void* object)
{
	int32_t a = (int32_t)(size_t)key;
	int32_t b = *(const int32_t*)object;
	return a - b;
}

bool in_review_list(const uint32_t entry_id)
{
	buffer_t* b = state_get_review_list_buffer();

	bool found;
	binary_locate(
		(void*)(size_t)entry_id, b->data,
		b->size / sizeof(int32_t), sizeof(int32_t),
		entry_id_cmp, &found
	);
	return found;
}

export void review_list_add_entry(const uint32_t entry_id)
{
	buffer_t* b = state_get_review_list_buffer();

	bool found;
	const size_t num_elements = b->size / sizeof(uint32_t);
	uint32_t* it = binary_locate(
		(void*)(size_t)entry_id, b->data,
		num_elements, sizeof(uint32_t),
		entry_id_cmp, &found
	);
	if (found)
	{
		return;
	}


	buffer_allocate(b, sizeof(uint32_t));
	memmove(it + 1, it, num_elements - (it - (uint32_t*)b->data));
	*it = entry_id;
}

export void review_list_remove_entry(const uint32_t entry_id)
{
	buffer_t* b = state_get_review_list_buffer();

	bool found;
	const size_t num_elements = b->size / sizeof(uint32_t);
	uint32_t* it = binary_locate(
		(void*)(size_t)entry_id, b->data,
		num_elements, sizeof(uint32_t),
		entry_id_cmp, &found
	);
	if (!found)
	{
		return;
	}

	memmove(it, it + 1, num_elements - (it + 1 - (uint32_t*)b->data));
	b->size -= sizeof(uint32_t);
}
