#!/usr/bin/env python3

import os
import re
import sys
import struct
from collections import OrderedDict
from utils import *
from freqs import max_freq, get_frequency
from index import index_keys
from romaji import is_romajination
import expressions

control_sense_symbols = re.compile('[\\`]')
def format_sense(sense, entry):
	parts = []
	if len(sense.kanji_restriction) + len(sense.reading_restriction) > 0:
		restrictions = []
		for ki in sense.kanji_restriction:
			restrictions.append(entry.kanjis[ki].text)
		for ri in sense.reading_restriction:
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
	parts.append(';')
	if (len(trans.glosses) == 1 and len(name.readings) == 1
			and is_romajination(kata_to_hira(name.readings[0].text), trans.glosses[0])):
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

	freq = max_freq
	parts = []
	if len(entry.kanjis) > 0:
		'''
		Inverse restrictions, because it's easier to show entries this way.
		'''
		kanji_index_to_readings = {}
		for ri, r in enumerate(entry.readings):
			for ki in r.kanjis:
				kanji_index_to_readings.setdefault(ki, []).append(ri)

		grouped_readings_to_kanji_indices = {}
		for ki, reading_indices in kanji_index_to_readings.items():
			grouped_readings_to_kanji_indices.setdefault(','.join(map(str, reading_indices)), []).append(ki)
		del kanji_index_to_readings

		'''
		Format kanji groups
		'''
		groups = []
		seen = set()
		for readings, kanji_indices in grouped_readings_to_kanji_indices.items():
			for i, ki in enumerate(kanji_indices):
				seen.add(ki)
				k = entry.kanjis[ki]
				assert control_kanji_symbols.search(k.text) is None
				freq = min(freq, get_frequency(k.text))
				kanji_indices[i] = k.text
				if any_common_kanji and not k.common:
					kanji_indices[i] += '|U'

			groups.append(','.join(kanji_indices))
			if len(readings) != len(entry.readings)*2 - 1:
				groups[-1] += '#' + readings

		'''
		Format ungrouped kanjis
		'''
		for ki, k in enumerate(entry.kanjis):
			if ki in seen: continue
			assert control_kanji_symbols.search(k.text) is None
			freq = min(freq, get_frequency(k.text))
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
		freq = min(freq, get_frequency(r.text))
		readings.append(r.text)
		if any_common_kana and not r.common:
			readings[-1] += '|U'
	parts.append(';'.join(readings))
	del readings

	if type(entry) == Entry:
		'''
		Format sense groups
		'''
		sense_groups = []
		for g in entry.sense_groups:
			sense_groups.append(','.join(g.pos) + ';' + '`'.join(map(lambda s: format_sense(s, entry), g.senses)))
		parts.append('\\'.join(sense_groups))
		del sense_groups

		if freq != max_freq:
			parts.append(str(freq))
	else:
		transes = []
		for t in entry.transes:
			transes.append(format_trans(t, entry))
		parts.append('\\'.join(transes))
		del transes

	return '\t'.join(parts)

def write_index(index, label):
	index = list(index.items())
	index.sort()
	words_bytes = bytearray()
	indices_bytes = bytearray()
	weightw = 0
	weighti = 0
	weightw2 = 0
	weighti2 = 0
	indices_index = 0
	for w, indices in index:
		w_utf8 = w.encode('utf-8')
		assert w_utf8.find(0b11111000) == -1, w
		weightw += len(w.encode('utf-16')) + 4
		weighti += 4*len(indices)
		weightw2 += len(w_utf8) + 4
		weighti2 += 4*len(indices)

		words_bytes.extend(w_utf8)
		assert indices_index < 2**21
		# 0b11111000 is forbidden in current UTF-8
		words_bytes.extend(struct.pack('BBBB', 0b11111000,
			0b01111111 & indices_index,
			0b01111111 & (indices_index >> 7),
			0b01111111 & (indices_index >> 14)
		))
		indices_index += len(indices)
		indices_bytes.extend(struct.pack('<' + 'I' * len(indices), *indices))

	with open(f'data/{label}.idx', 'wb') as of:
		of.write(struct.pack('<I', 4 + len(indices_bytes)))
		of.write(indices_bytes)
		of.write(words_bytes)

	print(weightw / 2**20, '+', weighti / 2**20)
	print(weightw2 / 2**20, '+', weighti2 / 2**20)

def prepare_names():
	index = {}
	offset = 0
	combined_entries = {}
	with open(f'data/names.dat', 'wb') as of:
		for entry, _ in dictionary_reader('JMnedict.xml.gz'):
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
				index.setdefault(key, set()).add(offset)

			l = format_entry(entry).encode('utf-8')
			of.write(l)
			of.write(b'\n')
			offset += len(l) + 1

		for combined_entry in combined_entries.values():
			entry_index_keys = index_keys(combined_entry, variate=False)
			for key in entry_index_keys:
				index.setdefault(key, set()).add(offset)

			l = format_entry(combined_entry).encode('utf-8')
			of.write(l)
			of.write(b'\n')
			offset += len(l) + 1

	write_index(index, 'names')

def prepare_dict(process_expressions):
	index = {}
	offset = 0
	with open(f'data/dict.dat', 'wb') as of:
		for entry, elem in dictionary_reader('JMdict_e.gz'):
			entry_index_keys = index_keys(entry, variate=True)
			for key in entry_index_keys:
				index.setdefault(key, set()).add(offset)
			if process_expressions:
				expressions.record_entry(entry, entry_index_keys, elem, offset)

			l = format_entry(entry).encode('utf-8')
			of.write(l)
			of.write(b'\n')
			offset += len(l) + 1

	if process_expressions:
		expressions.dump_expressions()

	write_index(index, 'dict')


prepare_dict(False)
prepare_names()
