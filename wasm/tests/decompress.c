#include "fake-memory.h"

#include "../src/decompress.c"
#include "../generated/index.test.c"

compressed_file_t test_index = {
	.last_chunk_index = test_dictionary_index_last_chunk_index,
	.last_chunk_size = test_dictionary_index_last_chunk_size,
	.original_size = test_dictionary_index_original_size,
	.chunks_offsets = test_dictionary_index_chunks_offsets,
	.data = test_dictionary_index_data,
	.currently_decompressed_chunk_index = -1,
};

void test_decompress_chunk()
{
	decompress_chunk(&test_index, 0);
	assert(0 == memcmp(decompressed_chunk, test_dictionary_index_original_data, CHUNK_SIZE));

	decompress_chunk(&test_index, 1);
	assert(0 == memcmp(
		decompressed_chunk,
		test_dictionary_index_original_data + CHUNK_SIZE, CHUNK_SIZE
	));

	decompress_chunk(&test_index, 2);
	assert(0 == memcmp(
		decompressed_chunk,
		test_dictionary_index_original_data + 2*CHUNK_SIZE, CHUNK_SIZE
	));

	decompress_chunk(&test_index, 3);
	assert(0 == memcmp(
		decompressed_chunk,
		test_dictionary_index_original_data + 3*CHUNK_SIZE, test_dictionary_index_last_chunk_size
	));
}

int main()
{
	test_decompress_chunk();

	return 0;
}
