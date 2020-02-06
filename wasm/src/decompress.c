#include "decompress.h"
#include "imports.h"

#include "../generated/config.h"

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Weverything"
#define LZ4LIB_VISIBILITY __attribute__((visibility("hidden")))
#include "../generated/lz4.c"
#pragma clang diagnostic pop

compressed_file_t* currently_decompressed_file = NULL;
uint8_t decompressed_chunk[CHUNK_SIZE];

void decompress_chunk(compressed_file_t* file, size_t chunk_index)
{
	// NOTE there is place for further optimization:
	// when we have following/previous chunk decompressed, we want to
	// cache entry end/start, so in case after decompressing current chunk
	// we find part of required entry is in following/previous chunk we
	// won't decompress it again
	if (file == currently_decompressed_file && chunk_index == file->currently_decompressed_chunk_index)
	{
		return;
	}

	const int32_t chunk_start = file->chunks_offsets[chunk_index];
	const int num_decompressed_bytes = LZ4_decompress_safe(
		(const char*)(file->data + chunk_start),
		(char*)decompressed_chunk,
		// chunks_offsets have additional element at the end
		// so this expression is valid for every valid `chunk_index`
		file->chunks_offsets[chunk_index + 1] - chunk_start,
		sizeof(decompressed_chunk)
	);
	if (num_decompressed_bytes < 0)
	{
		take_a_trip("Error during decompression");
	}

	file->currently_decompressed_chunk_index = chunk_index;
	currently_decompressed_file = file;
}

size_t get_real_chunk_size(const compressed_file_t* file, size_t chunk_index)
{
	if (chunk_index == file->last_chunk_index)
	{
		return file->last_chunk_size;
	}
	else
	{
		return CHUNK_SIZE;
	}
}
