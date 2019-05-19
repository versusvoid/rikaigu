import math
import random
import subprocess
from collections import namedtuple

import lz4.block

from utils import print_lengths_stats, download


def generate_config_header(max_reading_index, min_entry_id):
	with open('wasm/generated/config.h', 'w') as of:
		print('#define MAX_READING_INDEX', max_reading_index, file=of)
		print('#define MIN_ENTRY_ID', min_entry_id, file=of)

def get_lz4_source():
	download('https://github.com/lz4/lz4/raw/master/lib/lz4.c', 'wasm/generated/lz4.c', temp=False)

def generate_deinflection_rules_header():
	max_in_suffix_len = 0
	max_out_suffix_len = 0
	maxinflection_name_length = 0
	pos_flags_map = {}
	rules = []
	with open('data/deinflect.dat') as f:
		for l in f:
			if l[0] == '#':
				continue
			l = l.strip().split('\t')
			max_in_suffix_len = max(max_in_suffix_len, len(l[0].encode('utf-16le'))//2)
			max_out_suffix_len = max(max_out_suffix_len, len(l[1].encode('utf-16le'))//2)

			source_pos = []
			for pos in l[2].split('|'):
				pos_flags_map.setdefault(pos, 1 << len(pos_flags_map))
				source_pos.append(pos.upper().replace('-', '_'))

			target_pos = []
			for pos in l[3].split('|'):
				pos_flags_map.setdefault(pos, 1 << len(pos_flags_map))
				target_pos.append(pos.upper().replace('-', '_'))

			maxinflection_name_length = max(maxinflection_name_length, len(l[4].encode('utf8')))

			rules.append((l[0], l[1], source_pos, target_pos, l[4]))

	rules.sort(key=lambda r: (-len(r[0]), r[0]))

	assert len(pos_flags_map) < 26
	with open('wasm/generated/deinflection-info.bin.c', 'w') as of:

		print('typedef enum {', file=of)

		any_pos = 0
		for k, flag in pos_flags_map.items():
			print('\t', k.upper().replace('-', '_').rjust(6), '=', f'0x{flag:08X},', file=of)
			any_pos |= flag
		print(f'\tANY_POS = 0x{any_pos:08X},', file=of)

		print('} POS_FLAGS;', file=of)

		print(
			'typedef struct {',
			'\tuint32_t source_pos_mask;',
			'\tuint32_t target_pos_mask;',
			f'\tchar16_t suffix[{max_in_suffix_len + 1}];',
			f'\tchar16_t new_suffix[{max_out_suffix_len + 1}];',
			f'\tchar inflection_name[{maxinflection_name_length + 1}];',
			f'\tuint8_t new_suffix_length;',
			f'\tuint8_t inflection_name_length;',
			'} deinflection_rule_t;',
			sep='\n', file=of
		)

		print('const deinflection_rule_t rules[] = {', file=of)
		last_suffix_len = None
		first_suffix_of_len_positions = []
		for i, (in_suffix, out_suffix, source_pos, target_pos, inflection_name) in enumerate(rules):
			if len(in_suffix) != last_suffix_len:
				first_suffix_of_len_positions.append((len(in_suffix), i))
				last_suffix_len = len(in_suffix)

			print(
				'\t{',
				f'\t\t.suffix = u"{in_suffix}",',
				f'\t\t.new_suffix = u"{out_suffix}",',
				f'\t\t.source_pos_mask = {"|".join(source_pos)},',
				f'\t\t.target_pos_mask = {"|".join(target_pos)},',
				f'\t\t.inflection_name = "{inflection_name}",',
				f'\t\t.new_suffix_length = {len(out_suffix)},',
				f'\t\t.inflection_name_length = {len(inflection_name)},',
				'\t},',
				sep='\n',
				file=of
			)
		print('};', file=of)

		# When fails, check for gaps (when next rule's `in_suffix` shorter than previous by two or more characters)
		assert list(sorted(length for length, _ in first_suffix_of_len_positions)) == [1, 2, 3, 4, 5]
		positions = (str(pos) for _, pos in first_suffix_of_len_positions[::-1])

		print(
			'const size_t first_suffix_of_length_position[] = { ',
			len(rules), ', ',
			', '.join(positions),
			' };',
			sep='', file=of
		)

	return pos_flags_map


# Fun fact: this is the only possible prefix
offset_prefix_len = 3
type_bit_shift = 32 - (2*offset_prefix_len + 1)
offset_prefix = int('1010,0000,0000,0000'.replace(',', ''), 2)
prefix_mask   = int('1110,0000,0000,0000'.replace(',', ''), 2)  # noqa: E221
suffix_mask   = int('0001,1111,1111,1111'.replace(',', ''), 2)  # noqa: E221

chunk_size = 2048

def encode_int(i, is_type=False):
	assert i < 2**(32 - (2*offset_prefix_len + 1))  # +1 for `type` bit

	h1 = (i & suffix_mask) | offset_prefix
	h2 = (i >> (16 - offset_prefix_len))
	assert (h2 & (prefix_mask | (1 << (15 - offset_prefix_len)))) == 0
	h2 |= offset_prefix

	if is_type:
		h2 |= (1 << (15 - offset_prefix_len))

	assert h1 < 2**16
	assert h2 < 2**16

	return (h1 & 0xff, h1 >> 8, h2 & 0xff, h2 >> 8)

TypedOffset = namedtuple('TypedOffset', 'type, offset')

def encode_index(label, index, line_lengths):
	buf = bytearray()
	keys_len = 0
	offsets_len = 0
	types_len = 0

	index = list(index.items())
	index.sort()
	for w, offsets in index:
		old_buf_len = len(buf)

		w = w.encode('utf-16le')
		for b2 in w[1::2]:
			assert (b2 & (prefix_mask >> 8)) != (offset_prefix >> 8)
		buf.extend(w)
		keys_len += len(w)

		for offset in offsets:

			if type(offset) == int:
				buf.extend(encode_int(offset))
				offsets_len += 4
			else:
				buf.extend(encode_int(offset.type, is_type=True))
				types_len += 4
				buf.extend(encode_int(offset.offset))
				offsets_len += 4

		line_lengths.append(len(buf) - old_buf_len)

	print(f'''{label}.u16.idx would be of {len(buf) / 2**20:.2f}MiB:
		{keys_len / 2**20:.2f} - keys,
		{offsets_len / 2**20:.2f} - offsets,
		{types_len / 2**20:.2f} - types,
	''')

	return buf


def write_utf16_index_to_clang(label, buf, clang):
	# len(chunk_offsets) would be number of chunks + 1, so for all `i`
	# can compute compressed chunk length with single expression:
	# `chunk_offsets[i + 1] - chunk_offsets[i]`
	chunk_offsets = [0]
	print(f'const uint8_t {label}_dictionary_index_data[] = {{', file=clang)
	for chunk_start in range(0, len(buf), chunk_size):
		chunk = buf[chunk_start:chunk_start + chunk_size]

		compressed = lz4.block.compress(chunk, store_size=False)
		chunk_offsets.append(chunk_offsets[-1] + len(compressed))
		print(*compressed, sep=',', end=',', file=clang)

	print('};', file=clang)
	print(f'const int32_t {label}_dictionary_index_chunks_offsets[] = {{', file=clang)
	print(*chunk_offsets, sep=',', end='};', file=clang)

	return chunk_offsets[-1], len(chunk_offsets), len(chunk)

def write_index_header(label, original_size, compressed_len, num_chunk_offsets, last_chunk_size, of):
	print(f'const size_t {label}_dictionary_index_original_size = {original_size};', file=of)
	print(f'extern const uint8_t {label}_dictionary_index_data[{compressed_len}];', file=of)
	print(f'extern const int32_t {label}_dictionary_index_chunks_offsets[{num_chunk_offsets}];', file=of)
	print(f'const size_t {label}_dictionary_index_last_chunk_size = {last_chunk_size};', file=of)
	print(f'const size_t {label}_dictionary_index_last_chunk_index = {num_chunk_offsets - 2};', file=of)

def write_utf16_index(label, index, line_lengths, of, clang):
	buf = encode_index(label, index, line_lengths)
	compressed_len, num_chunk_offsets, last_chunk_size = write_utf16_index_to_clang(label, buf, clang)
	write_index_header(label, len(buf), compressed_len, num_chunk_offsets, last_chunk_size, of)
	print(f'{label} utf16 index lz4-chunked is of size {compressed_len / 2**20:.2f}MiB')
	return buf

def write_utf16_indexies(dict_index, names_index):
	with open('wasm/cflags') as f:
		flags = f.read().strip().split()
	flags.insert(0, 'clang')
	flags.extend([
		'-c', '-emit-llvm', '--target=wasm32-unknown-unknown-wasm',
		'-x', 'c', '-o', 'wasm/generated/index.bc', '-'
	])
	clang = subprocess.Popen(flags, stdin=subprocess.PIPE, text=True)
	print('#include <stdint.h>', file=clang.stdin)

	with open('wasm/generated/index.h', 'w') as of:
		print(f'#define dictionary_index_chunk_size {chunk_size}', file=of)
		print(f'const uint32_t dictionary_index_type_bit = 0x{1<<type_bit_shift:08X};', file=of)
		print(f'const uint16_t dictionary_index_offset_prefix = 0x{offset_prefix:04X};', file=of)
		print(f'const size_t dictionary_index_offset_prefix_len = 3;', file=of)
		print(f'const uint16_t dictionary_index_offset_prefix_mask = 0x{prefix_mask:04X};', file=of)
		print(f'const uint16_t dictionary_index_offset_suffix_mask = 0x{suffix_mask:04X};', file=of)

		line_lengths = []
		for label, index in zip(('dict', 'names'), (dict_index, names_index)):
			write_utf16_index(label, index, line_lengths, of, clang.stdin)

		print_lengths_stats('utf16 index', line_lengths)
		print(f'''
			#ifndef dictionary_index_max_entry_length
			#define dictionary_index_max_entry_length {2**math.ceil(math.log2(max(line_lengths)))}
			#endif
		''', file=of)

	print(file=clang.stdin)
	clang.stdin.close()
	clang.wait()

	with open('wasm/generated/index-samples.csv', 'w') as of:
		print(
			'かける', *map(lambda o: f'{o[0]};{o[1]}' if type(o) == TypedOffset else o, dict_index['かける']),
			sep=',', file=of
		)

if __name__ == '__main__':
	get_lz4_source()
	generate_deinflection_rules_header()

	# Test data generation
	parts = [
		(
			'ン',
			offset_prefix | random.randrange(2**13), offset_prefix | (1 << 12) | random.randrange(2**12),
			offset_prefix | random.randrange(2**13), offset_prefix | random.randrange(2**12),
		),
		(
			'フェスティバル',
			offset_prefix | random.randrange(2**13), offset_prefix | (1 << 12) | random.randrange(2**12),
			offset_prefix | random.randrange(2**13), offset_prefix | random.randrange(2**12),
			offset_prefix | random.randrange(2**13), offset_prefix | (1 << 12) | random.randrange(2**12),
			offset_prefix | random.randrange(2**13), offset_prefix | random.randrange(2**12),
			offset_prefix | random.randrange(2**13), offset_prefix | random.randrange(2**12),
			offset_prefix | random.randrange(2**13), offset_prefix | random.randrange(2**12),
		),
		(
			'フェスティヴァル',
			offset_prefix | random.randrange(2**13), offset_prefix | (1 << 12) | random.randrange(2**12),
			offset_prefix | random.randrange(2**13), offset_prefix | random.randrange(2**12),
			offset_prefix | random.randrange(2**13), offset_prefix | random.randrange(2**12),
		),
	]
	for s, *halves in parts:
		print(*(f"u'{c}', " for c in s), *(f'0x{h:04X}, ' for h in halves))

	res = []
	for i in range(10):
		v = random.randrange(2**24, 2**25)
		is_type = random.choice([True, False])
		b0, b1, b2, b3 = encode_int(v, is_type=is_type)
		print(f'0x{b3:02X}{b2:02X}{b1:02X}{b0:02X}', end=', ')

		if is_type:
			res.append(v | (1 << type_bit_shift))
		else:
			res.append(v)
	print('\n', *(f'0x{v:08X}, ' for v in res), sep='')

	test_entries = [
		('五劫の', 750),
		('住む処', 750),
		# 1500 bytes
		('寿限無', 750),  # cross on offsets, end of chunk 0
		('擦り切れ', 752),
		('水行末', 1090),
		# 4092 bytes
		('海砂利水魚の', 752),  # cross on key, end of chunk 1
		('藪柑子', 750),
		('長久命', 550),  # end of chunk 2
		# 6144 bytes
		('長助', 540),
		('雲来末', 750),
	]
	test_index = {}
	gold_line_length = []
	for i, (key, entry_line_length_bytes) in enumerate(test_entries):
		assert len(key.encode('utf-16le')) == len(key)*2
		bytes_left = entry_line_length_bytes - len(key)*2
		assert bytes_left % 4 == 0
		gold_line_length.append(entry_line_length_bytes)

		num_offsets = bytes_left // 4 - 3
		offsets = (random.randrange(10) for i in range(num_offsets))
		test_index[key] = [TypedOffset(i*2 + 1, i*2 + 2), i, *offsets]

	assert list(sorted(test_index)) == list(k for k, _ in test_entries)
	assert all(len(k.encode('utf-16le')) == len(k) * 2 for k in test_index)

	line_lengths = []
	with open('wasm/generated/index.test.c', 'w') as of:
		print('#include "../src/index.c"', file=of)
		buf = write_utf16_index('test', test_index, line_lengths, of, of)
		print('const uint8_t test_dictionary_index_original_data[] = {', ','.join(map(str, buf)), '};', file=of)
		test_entries_offsets = [0]
		for l in line_lengths:
			test_entries_offsets.append(test_entries_offsets[-1] + l)
		print('const size_t test_dictionary_index_entries_offsets[] = {', ','.join(map(str, test_entries_offsets)), '};', file=of)
	assert line_lengths == gold_line_length, f'{line_lengths}\n{gold_line_length}'
	assert sum(line_lengths[:2]) < chunk_size and sum(line_lengths[:3]) > chunk_size
	assert sum(line_lengths[:5]) == chunk_size * 2 - 4
	assert sum(line_lengths[:8]) == chunk_size * 3
