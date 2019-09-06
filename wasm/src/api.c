#include "state.h"
#include "dictionaries.h"
#include "html_render.h"

export uint32_t rikaigu_search(size_t utf16_input_length)
{
	state_clear();
	return (uint32_t)search(utf16_input_length);
}

export double get_html()
{
	make_html();
	buffer_t* buffer = state_get_html_buffer();
	uint64_t res = (size_t)buffer->data;
	uint64_t size = buffer->size;
	res |= size << 32;
	return (double)res;
}
