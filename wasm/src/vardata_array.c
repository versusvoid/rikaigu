#include "vardata_array.h"

#include <stddef.h>
#include <assert.h>
#include <stdio.h>

#include "state.h"
#include "libc.h"


typedef struct {
	size_t capacity;
	size_t size;
	size_t element_size;
} vardata_array_header_t;

typedef struct {
	vardata_array_header_t header;
	uint8_t data[];
} vardata_array_t;

inline size_t calc_initial_capacity(size_t buffer_capacity, const size_t element_size)
{
	if (buffer_capacity < sizeof(vardata_array_header_t))
	{
		buffer_capacity = sizeof(vardata_array_header_t);
	}
	size_t initial_elements = (buffer_capacity - sizeof(vardata_array_header_t)) / 10 / element_size;
	if (initial_elements < 10)
	{
		initial_elements = 10;
	}
	return initial_elements;
}

void vardata_array_make(buffer_t* buf, size_t element_size)
{
	buf->size = 0;
	const size_t initial_elements = calc_initial_capacity(buf->capacity, element_size);
	vardata_array_t* array = buffer_allocate(buf, sizeof(vardata_array_header_t) + element_size * initial_elements);
	array->header.capacity = initial_elements;
	array->header.size = 0;
	array->header.element_size = element_size;
}

size_t vardata_array_num_elements(buffer_t* b)
{
	return ((vardata_array_t*)b->data)->header.size;
}

size_t vardata_array_capacity(buffer_t* b)
{
	return ((vardata_array_t*)b->data)->header.capacity;
}

void vardata_array_increment_size(buffer_t* b)
{
	vardata_array_t* array = b->data;
	assert(array->header.size < array->header.capacity);
	array->header.size += 1;
}

void vardata_array_set_size(buffer_t* b, const size_t new_size)
{
	vardata_array_t* array = b->data;
	assert(array->header.size >= new_size);
	array->header.size = new_size;
}

void* vardata_array_elements_start(buffer_t* b)
{
	return ((vardata_array_t*)b->data)->data;
}

void* vardata_array_vardata_start(buffer_t* b)
{
	vardata_array_t* array = b->data;
	return array->data + array->header.capacity * array->header.element_size;
}

void* vardata_array_enlarge(buffer_t* b, vardata_array_t* array, const size_t additional_elements, const size_t additional_vardata_size)
{
	const size_t elements_array_diff_size = additional_elements * array->header.element_size;
	void* current_vardata_end = buffer_allocate(b, elements_array_diff_size + additional_vardata_size);
	void* current_vardata_start = vardata_array_vardata_start(b);
	void* new_vardata_start = current_vardata_start + elements_array_diff_size;
	memmove(new_vardata_start, current_vardata_start, current_vardata_end - current_vardata_start);
	array->header.capacity += additional_elements;

	return current_vardata_end + elements_array_diff_size;
}

void* vardata_array_reserve_place_for_element(buffer_t* b, const size_t element_vardata_size)
{
	vardata_array_t* array = b->data;
	if (array->header.size == array->header.capacity)
	{
		return vardata_array_enlarge(b, array, array->header.capacity, element_vardata_size);
	}
	else
	{
		return buffer_allocate(b, element_vardata_size);
	}
}
