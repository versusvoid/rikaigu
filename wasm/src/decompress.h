#pragma once

#include <stddef.h>
#include <stdint.h>

#include "../generated/config.h"

typedef struct {
	size_t last_chunk_index;
	size_t last_chunk_size;
	size_t original_size;
	const int32_t* chunks_offsets;
	const uint8_t* data;
	size_t currently_decompressed_chunk_index;
} compressed_file_t;

extern uint8_t decompressed_chunk[CHUNK_SIZE];
extern compressed_file_t* currently_decompressed_file;

void decompress_chunk(compressed_file_t* file, size_t chunk_index);

size_t get_real_chunk_size(const compressed_file_t* file, size_t chunk_index);
