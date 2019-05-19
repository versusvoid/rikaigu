#pragma once
#include <stddef.h>
#include <stdint.h>
#include <uchar.h>
#include <stdnoreturn.h>

#include "dentry.h"

extern noreturn void take_a_trip(const char* message);

extern void request_read_dictionary(
	const uint32_t* offsets, const size_t num_offsets,
	void* buffer_handle, uint32_t request_id
);

extern void print(const char* message);
