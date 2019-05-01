#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include "fake-memory.h"

#define dictionary_index_max_entry_length 2048
#include "../src/state.c"
#include "../src/libc.c"
#include "../src/utf.c"
#include "../src/vardata_array.c"
#include "../generated/index.test.c"

dictionary_index_t test_index = {
	.last_chunk_index = test_dictionary_index_last_chunk_index,
	.last_chunk_size = test_dictionary_index_last_chunk_size,
	.original_size = test_dictionary_index_original_size,
	.chunks_offsets = test_dictionary_index_chunks_offsets,
	.data = test_dictionary_index_data,
	.currently_decompressed_chunk_index = -1,
};

void test_do_decompress_chunk()
{
	do_decompress_chunk(&test_index, 0);
	assert(0 == memcmp(decompressed_chunk, test_dictionary_index_original_data, dictionary_index_chunk_size));

	do_decompress_chunk(&test_index, 1);
	assert(0 == memcmp(
		decompressed_chunk,
		test_dictionary_index_original_data + dictionary_index_chunk_size, dictionary_index_chunk_size
	));

	do_decompress_chunk(&test_index, 2);
	assert(0 == memcmp(
		decompressed_chunk,
		test_dictionary_index_original_data + 2*dictionary_index_chunk_size, dictionary_index_chunk_size
	));

	do_decompress_chunk(&test_index, 3);
	assert(0 == memcmp(
		decompressed_chunk,
		test_dictionary_index_original_data + 3*dictionary_index_chunk_size, test_dictionary_index_last_chunk_size
	));
}

void test_find_entry_start_offset()
{
	const char16_t piece_of_index[] = {
		u'ン',  0xA500,  0xB6F8,  0xB880,  0xA5C6, // 5 * 2
		u'フ',  u'ェ',  u'ス',  u'テ',  u'ィ',  u'バ',  u'ル',  0xAC24,  0xB698,  0xA684,  0xAC80,  0xB42B,  0xB7BB,  0xBF5A,  0xA531,  0xAE59,  0xA8C3,  0xB660,  0xAEB5, // 19 * 2
		u'フ',  u'ェ',  u'ス',  u'テ',  u'ィ',  u'ヴ',  u'ァ',  u'ル',  0xA589,  0xBEAC,  0xB9F8,  0xAB6E,  0xA14C,  0xA4CE, // 14 * 2
	};
	memcpy(decompressed_chunk, piece_of_index, sizeof(piece_of_index));
	assert(find_index_entry_start_offset(0) == -1);
	assert(find_index_entry_start_offset(2*2) == -1);
	assert(find_index_entry_start_offset(4*2) == -1);
	assert(find_index_entry_start_offset(5*2) == 5*2);
	assert(find_index_entry_start_offset((5 + 18)*2) == 5*2);
	assert(find_index_entry_start_offset((5 + 18)*2) == 5*2);
	assert(find_index_entry_start_offset((5 + 19)*2) == (5 + 19)*2);
	assert(find_index_entry_start_offset((5 + 19 + 13)*2) == (5 + 19)*2);
	assert(find_index_entry_start_offset((5 + 19 + 13)*2) == (5 + 19)*2);
}

void test_find_entry_end_offset()
{
	const char16_t piece_of_index[] = {
		u'ン',  0xA500,  0xB6F8,  0xB880,  0xA5C6, // 5 * 2
		u'フ',  u'ェ',  u'ス',  u'テ',  u'ィ',  u'バ',  u'ル',  0xAC24,  0xB698,  0xA684,  0xAC80,  0xB42B,  0xB7BB,  0xBF5A,  0xA531,  0xAE59,  0xA8C3,  0xB660,  0xAEB5, // 19 * 2
		u'フ',  u'ェ',  u'ス',  u'テ',  u'ィ',  u'ヴ',  u'ァ',  u'ル',  0xA589,  0xBEAC,  0xB9F8,  0xAB6E,  0xA14C,  0xA4CE, // 14 * 2
	};
	memcpy(decompressed_chunk, piece_of_index, sizeof(piece_of_index));
	assert(find_index_entry_end_offset(sizeof(piece_of_index), 0) == 5*2);
	assert(find_index_entry_end_offset(sizeof(piece_of_index), 4*2) == 5*2);
	assert(find_index_entry_end_offset(sizeof(piece_of_index), 5*2) == (5 + 19)*2);
	assert(find_index_entry_end_offset(sizeof(piece_of_index), 15*2) == (5 + 19)*2);
	assert(find_index_entry_end_offset(sizeof(piece_of_index), (5 + 18)*2) == (5 + 19)*2);
	assert(find_index_entry_end_offset(sizeof(piece_of_index), (5 + 19)*2) == -1);
	assert(find_index_entry_end_offset(sizeof(piece_of_index), (5 + 19 + 7)*2) == -1);
	assert(find_index_entry_end_offset(sizeof(piece_of_index), (5 + 19 + 13)*2) == -1);
}

void test_find_entry_offsets_start()
{
	const char16_t piece_of_index[] = {
		u'ン',  0xA500,  0xB6F8,  0xB880,  0xA5C6, // 5 * 2
		u'フ',  u'ェ',  u'ス',  u'テ',  u'ィ',  u'バ',  u'ル',  0xAC24,  0xB698,  0xA684,  0xAC80,  0xB42B,  0xB7BB,  0xBF5A,  0xA531,  0xAE59,  0xA8C3,  0xB660,  0xAEB5, // 19 * 2
		u'フ',  u'ェ',  u'ス',  u'テ',  u'ィ',  u'ヴ',  u'ァ',  u'ル',  0xA589,  0xBEAC,  0xB9F8,  0xAB6E,  0xA14C,  0xA4CE, // 14 * 2
	};
	assert(find_index_entry_offsets_start_position((const uint8_t*)piece_of_index, 5*2) == 2);
	assert(find_index_entry_offsets_start_position((const uint8_t*)piece_of_index + 5*2, 19*2) == 7*2);
	assert(find_index_entry_offsets_start_position((const uint8_t*)piece_of_index + (5 + 19)*2, 14*2) == 8*2);
}

void get_and_compare_index_entry(size_t pos, size_t start_pos, size_t end_pos,  const uint8_t* gold, size_t gold_size)
{
	assert(end_pos - start_pos == gold_size);
	get_index_entry_at(&test_index, pos);
	assert(current_index_entry.start_position_in_index == start_pos);
	assert(current_index_entry.end_position_in_index == end_pos);
	assert(current_index_entry.key_length <= 6);
	assert(current_index_entry.key_length * 2 + current_index_entry.num_offsets * 4 == gold_size);
	assert(memcmp(current_index_entry.key, gold, gold_size) == 0);

	test_index.currently_decompressed_chunk_index = -1;

	get_index_entry_at(&test_index, pos);
	assert(memcmp(current_index_entry.key, gold, gold_size) == 0);
}

void test_get_index_entry_at()
{
	assert(dictionary_index_chunk_size * dict_dictionary_index_last_chunk_index + dict_dictionary_index_last_chunk_size == dict_index.original_size);

	for (size_t entry_index = 0; entry_index < 10; ++entry_index)
	{
		const size_t entry_start = test_dictionary_index_entries_offsets[entry_index];
		const size_t entry_end = test_dictionary_index_entries_offsets[entry_index + 1];
		for (size_t pos = entry_start; pos < entry_end; pos += 2)
		{
			get_and_compare_index_entry(
				pos,
				entry_start, entry_end,
				test_dictionary_index_original_data + entry_start,
				entry_end - entry_start
			);
		}
	}
}

void test_dictionary_index_entry_decode_offsets()
{
	uint32_t offsets_and_types[] = {0xBE23A873, 0xA924B39C, 0xABA7BE2A, 0xAD08A358, 0xB90AAD9A, 0xBE80BDFB, 0xA946A945, 0xAD59BD99, 0xBD04BC92, 0xBA18A0E8};
	current_index_entry.offsets = offsets_and_types;
	current_index_entry.num_offsets = sizeof(offsets_and_types) / sizeof(uint32_t);

	current_index_entry_decode_offsets();
	const uint32_t gold[] = {0x03C46873, 0x0124939C, 0x0174FE2A, 0x01A10358, 0x03214D9A, 0x03D01DFB, 0x0128C945, 0x01AB3D99, 0x03A09C92, 0x034300E8};
	assert(memcmp(current_index_entry.offsets, gold, sizeof(gold)) == 0);
}

void test_dictionary_index_search_for_offsets()
{
	size_t len;

	const char16_t k1[] = u"寿限無";
	len = sizeof(k1) / sizeof(char16_t) - 1;
	assert(dictionary_index_search_for_offsets(&test_index, k1, len, 0, test_index.original_size));
	assert(current_index_entry.start_position_in_index == test_dictionary_index_entries_offsets[2]);
	assert(0 == utf16_compare(
		current_index_entry.key, current_index_entry.key_length,
		k1, len
	));

	const char16_t k2[] = u"海砂利水魚の";
	len = sizeof(k2) / sizeof(char16_t) - 1;
	assert(dictionary_index_search_for_offsets(&test_index, k2, len, 0, test_index.original_size));
	assert(current_index_entry.start_position_in_index == test_dictionary_index_entries_offsets[5]);
	assert(0 == utf16_compare(
		current_index_entry.key, current_index_entry.key_length,
		k2, len
	));

	const char16_t k3[] = u"長久命";
	len = sizeof(k3) / sizeof(char16_t) - 1;
	assert(dictionary_index_search_for_offsets(&test_index, k3, len, 0, test_index.original_size));
	assert(current_index_entry.start_position_in_index == test_dictionary_index_entries_offsets[7]);
	assert(0 == utf16_compare(
		current_index_entry.key, current_index_entry.key_length,
		k3, len
	));

	const char16_t k4[] = u"長助";
	len = sizeof(k4) / sizeof(char16_t) - 1;
	assert(dictionary_index_search_for_offsets(&test_index, k4, len, 0, test_index.original_size));
	assert(current_index_entry.start_position_in_index == test_dictionary_index_entries_offsets[8]);
	assert(0 == utf16_compare(
		current_index_entry.key, current_index_entry.key_length,
		k4, len
	));

	const char16_t k5[] = u"擦り切れ";
	len = sizeof(k5) / sizeof(char16_t) - 1;
	assert(dictionary_index_search_for_offsets(&test_index, k5, len, 0, test_dictionary_index_original_size));
	assert(current_index_entry.start_position_in_index == test_dictionary_index_entries_offsets[3]);
	assert(0 == utf16_compare(
		current_index_entry.key, current_index_entry.key_length,
		k5, len
	));

	const char16_t k6[] = u"水行末";
	len = sizeof(k6) / sizeof(char16_t) - 1;
	assert(dictionary_index_search_for_offsets(
		&test_index, k6, len,
		test_dictionary_index_entries_offsets[4], test_dictionary_index_entries_offsets[5])
	);
	assert(current_index_entry.start_position_in_index == test_dictionary_index_entries_offsets[4]);
	assert(0 == utf16_compare(
		current_index_entry.key, current_index_entry.key_length,
		k6, len
	));
}

int main()
{
	test_do_decompress_chunk();
	test_find_entry_start_offset();
	test_find_entry_end_offset();
	test_find_entry_offsets_start();
	test_get_index_entry_at();
	test_dictionary_index_entry_decode_offsets();
	test_dictionary_index_search_for_offsets();

	return 0;
}
