#!/usr/bin/env python3

import re
import struct
from collections import defaultdict

import dictionary
import freqs
from utils import kata_to_hira
from index import index_keys
from romaji import is_romajination

control_sense_symbols = re.compile('[\\`]')
def format_sense(sense, entry):
	parts = []
	kanji_restriction = sense.kanji_restriction or ()
	reading_restriction = sense.reading_restriction or ()
	if len(kanji_restriction) + len(reading_restriction) > 0:
		restrictions = []
		for ki in kanji_restriction:
			restrictions.append(entry.kanjis[ki].text)
		for ri in reading_restriction:
			restrictions.append(entry.readings[ri].text)
		parts.append('(only ' + ','.join(restrictions) + ')')

	if bool(sense.s_inf):
		parts.append('(' + sense.s_inf + ')')

	parts.append('; '.join(sense.glosses))

	res = ' '.join(parts)
	assert control_sense_symbols.search(res) is None
	return res

trans_type_abbreviations = {
	"company": "c",
	"fem": "f",
	"given": "g",
	"masc": "m",
	"organization": "o",
	"person": "p",
	"place": "pl",
	"product": "pr",
	"station": "s",
	"surname": "su",
	"unclass": "u",
	"work": "w",
}
def format_trans(trans, name):
	parts = []
	parts.append(','.join(map(trans_type_abbreviations.__getitem__, trans.types)))
	parts.append(';')  # FIXME не всегда нужен
	if (len(trans.glosses) == 1 and len(name.readings) == 1
				and is_romajination(kata_to_hira(name.readings[0].text, agressive=False), trans.glosses[0])):
		#parts.append('*')
		pass
	else:
		parts.append('; '.join(trans.glosses))
	return ''.join(parts)


control_kanji_symbols = re.compile('[#|,;\t]')
control_reading_symbols = re.compile('[|;\t]')
def format_entry(entry):
	any_common_kanji = any(map(lambda k: k.common, entry.kanjis))
	any_common_kana = any(map(lambda r: r.common, entry.readings))

	parts = []
	if len(entry.kanjis) > 0:
		'''
		Inverse kanjis-readings restrictions, because it's easier to show entries this way.
		'''
		kanji_index_to_readings = {}
		for ri, r in enumerate(entry.readings):
			kanji_indices = r.kanji_restriction or range(len(entry.kanjis))
			for ki in kanji_indices:
				kanji_index_to_readings.setdefault(ki, []).append(ri)

		grouped_readings_to_kanji_offsets = {}
		for ki, reading_indices in kanji_index_to_readings.items():
			grouped_readings_to_kanji_offsets.setdefault(tuple(reading_indices), []).append(ki)
		del kanji_index_to_readings

		'''
		Format kanji groups
		'''
		groups = []
		seen = set()
		for reading_indices, kanji_offsets in grouped_readings_to_kanji_offsets.items():
			for i, ki in enumerate(kanji_offsets):
				seen.add(ki)
				k = entry.kanjis[ki]
				assert control_kanji_symbols.search(k.text) is None
				kanji_offsets[i] = k.text
				if any_common_kanji and not k.common:
					kanji_offsets[i] += '|U'

			groups.append(','.join(kanji_offsets))
			if len(reading_indices) != len(entry.readings):
				groups[-1] += '#' + ','.join(map(str, reading_indices))

		'''
		Format ungrouped kanjis
		'''
		for ki, k in enumerate(entry.kanjis):
			if ki in seen: continue
			assert control_kanji_symbols.search(k.text) is None
			groups.append(k.text)
			if any_common_kanji and not k.common:
				groups[-1] += '|U'

		parts.append(';'.join(groups))
		del seen, groups

	'''
	Format readings
	'''
	readings = []
	for r in entry.readings:
		assert control_reading_symbols.search(r.text) is None
		readings.append(r.text)
		if any_common_kana and not r.common:
			readings[-1] += '|U'
	parts.append(';'.join(readings))
	del readings

	if type(entry) == dictionary.Entry:
		'''
		Format sense groups
		'''
		sense_groups = []
		for g in entry.sense_groups:
			# TODO use mecab to infer additional pos for exp entries
			sense_groups.append(','.join(g.pos) + ';' + '`'.join(map(lambda s: format_sense(s, entry), g.senses)))
		parts.append('\\'.join(sense_groups))
		del sense_groups

		# TODO per kanji/reading freq
		freq = freqs.get_frequency(entry)
		if freq is not None:
			parts.append(str(freq))
	else:
		transes = []
		for t in entry.transes:
			transes.append(format_trans(t, entry))
		parts.append('\\'.join(transes))
		del transes

		freq = freqs.get_frequency(entry)
		if freq is not None:
			parts.append(str(freq))

	return '\t'.join(parts)

common_unused_byte_pairs = set(bytes([v >> 8, v & 0xff]) for v in range(0, 2**16))
label2utf16_index = {}
def write_index(index, label):
	# try utf16
	index = list(index.items())
	index.sort()
	words_bytes = bytearray()
	offsets_bytes = bytearray()
	offsets_index = 0

	utf16_index = []
	unused_offsets_byte_pairs = set(bytes([v >> 8, v & 0xff]) for v in range(0, 2**16))
	unused_utf16_byte_pairs = set(bytes([v >> 8, v & 0xff]) for v in range(0, 2**16))
	for w, offsets in index:
		w_utf8 = w.encode('utf-8')
		assert w_utf8.find(0b11111000) == -1, w

		words_bytes.extend(w_utf8)
		assert offsets_index < 2**21

		'''
		# funny enough LZ4 compress 4 bytes offsets with 4 bytes markers better then
		# 3 bytes offsets with 2 bytes markers
		# Since we only really care for compressed index size AND extracting 4 bytes offset
		# is easier, let's leave it thus
		compressed_offsets_bytes = []
		for ofs in offsets:
			ofs = ofs // 2
			assert ofs < 2**24
			compressed_offsets_bytes.extend((ofs >> 16, (ofs >> 8) & 0xff, ofs & 0xff))
		compressed_offsets_bytes = struct.pack('B'*len(compressed_offsets_bytes), *compressed_offsets_bytes)
		'''
		compressed_offsets_bytes = struct.pack('<' + 'I' * len(offsets), *offsets)
		for i in range(0, len(compressed_offsets_bytes) - 1):
			common_unused_byte_pairs.discard(compressed_offsets_bytes[i:i+2])
		w_utf16 = w.encode('utf-16')
		for i in range(0, len(w_utf16) - 1):
			common_unused_byte_pairs.discard(w_utf16[i:i+2])
		utf16_index.append((w_utf16, compressed_offsets_bytes))

		# 0b11111000 is forbidden in current UTF-8
		words_bytes.extend(struct.pack('BBBB', 0b11111000,
			0b01111111 & offsets_index,
			0b01111111 & (offsets_index >> 7),
			0b01111111 & (offsets_index >> 14)
		))
		offsets_index += len(offsets)
		offsets_bytes.extend(struct.pack('<' + 'I' * len(offsets), *offsets))

	label2utf16_index[label] = utf16_index

	with open(f'data/{label}.idx', 'wb') as of:
		of.write(struct.pack('<I', 4 + len(offsets_bytes)))
		of.write(offsets_bytes)
		of.write(words_bytes)

def write_utf16_index():
	print('common unused byte pairs:', common_unused_byte_pairs)
	if len(common_unused_byte_pairs) < 2:
		print('Using 4 bytes markers')
		start_marker = b'\x01\x03\x03\x07'
		end_marker = b'\x48\x15\x16\x23'
	else:
		[start_marker, end_marker] = list(common_unused_byte_pairs)[:2]

	line_lengths = []
	for label, utf16_index in label2utf16_index.items():
		with open(f'data/{label}.u16.idx', 'wb') as of:
			for w, offsets in utf16_index:
				assert start_marker not in w
				assert end_marker not in w
				of.write(w)
				of.write(start_marker)
				assert start_marker not in offsets
				assert end_marker not in offsets
				of.write(offsets)
				of.write(end_marker)
				line_lengths.append(len(w) + len(start_marker) + len(offsets) + len(end_marker))

	line_lengths.sort()
	print(f'''utf16 index line stats:
		min={line_lengths[0]} max={line_lengths[-1]}
		mean={sum(line_lengths)/len(line_lengths)} med={line_lengths[len(line_lengths) // 2]}
	''')

	return start_marker, end_marker

def prepare_names():
	index = defaultdict(set)
	offset = 0
	combined_entries = {}
	line_lengths = []
	with open(f'data/names.dat', 'wb') as of:
		for entry in dictionary.dictionary_reader('JMnedict.xml.gz'):
			if len(entry.readings) == 1 and len(entry.transes) == 1 and len(entry.transes[0].glosses) == 1:
				key = entry.readings[0].text + ' - ' + ','.join(entry.transes[0].types)
				combined_entry = combined_entries.get(key)
				if combined_entry is None:
					combined_entries[key] = entry
				else:
					combined_entry.kanjis.extend(entry.kanjis)
				continue

			entry_index_keys = index_keys(entry, variate=False)
			for key in entry_index_keys:
				index[key].add(offset)

			l = format_entry(entry).encode('utf-8')
			line_lengths.append(len(l))
			of.write(l)
			of.write(b'\n')
			offset += len(l) + 1

		for combined_entry in combined_entries.values():
			entry_index_keys = index_keys(combined_entry, variate=False)
			for key in entry_index_keys:
				index[key].add(offset)

			l = format_entry(combined_entry).encode('utf-8')
			line_lengths.append(len(l))
			of.write(l)
			of.write(b'\n')
			offset += len(l) + 1

	line_lengths.sort()
	print('names line length:', max(line_lengths), sum(line_lengths)/len(line_lengths), line_lengths[len(line_lengths)//2])

	write_index(index, 'names')

def prepare_dict():
	index = defaultdict(set)
	offset = 0
	line_lengths = []
	with open(f'data/dict.dat', 'wb') as of:
		for entry in dictionary.dictionary_reader('JMdict_e.gz'):
			entry_index_keys = index_keys(entry, variate=True)
			for key in entry_index_keys:
				index[key].add(offset)

			l = format_entry(entry).encode('utf-8')
			line_lengths.append(len(l))
			of.write(l)
			of.write(b'\n')
			offset += len(l) + 1

	line_lengths.sort()
	print('dict line length:', max(line_lengths), sum(line_lengths)/len(line_lengths), line_lengths[len(line_lengths)//2])

	write_index(index, 'dict')

def index_kanji():
	index = []
	offset = 0

	entry_no = 0
	with open('data/kanji.dat', 'r') as f:
		for l in f:
			entry_no += 1
			if entry_no % 1000 == 0:
				print('kanji', entry_no)
			index.append((ord(l[0]), offset))
			offset += len(l.encode('utf-8'))

	index.sort()
	with open('data/kanji.idx', 'wb') as of:
		for kanji_code_point, offset in index:
			of.write(struct.pack('<II', kanji_code_point, offset))

freqs.initialize()
prepare_dict()
prepare_names()

start_marker, end_marker = write_utf16_index()
with open('cpp/client/config.h', 'w') as of:
	print(f'#define UNKNOWN_WORD_FREQ_ORDER', freqs.get_unknown_word_freq_order(), file=of)
	start = ''.join(f'{b:02X}' for b in start_marker)
	print(f'#define INDEX_OFFSETS_START 0x{start}', file=of)
	end = ''.join(f'{b:02X}' for b in end_marker)
	print(f'#define INDEX_OFFSETS_END 0x{end}', file=of)

# TODO generate kanji.dat
index_kanji()
