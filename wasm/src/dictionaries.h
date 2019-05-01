#pragma once
#include <stdbool.h>

#include "state.h"

size_t search_start(size_t utf16_input_length, uint32_t request_id);
bool search_finish(buffer_t* raw_dentry_buffer);
