#include "state.h"
#include "dictionaries.h"
#include "html_render.h"

export size_t rikaigu_search_start(size_t utf16_input_length, uint32_t request_id)
{
	state_clear();
	return search_start(utf16_input_length, request_id);
}

export double rikaigu_search_finish(buffer_t* raw_dentry_buffer)
{
	bool no_errors = search_finish(raw_dentry_buffer);
	if (!no_errors)
	{
		return -1;
	}
	make_html();
	buffer_t* buffer = state_get_html_buffer();
	uint64_t res = (size_t)buffer->data;
	uint64_t size = buffer->size;
	res |= size << 32;
	return (double)res;
}
