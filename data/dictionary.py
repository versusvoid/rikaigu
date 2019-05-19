#!/usr/bin/env python3

from collections import namedtuple
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET
import gzip
import pickle
import os

from utils import download
from index import index_keys

class Kanji(namedtuple('Kanji', 'text, inf, common')):

	def __repr__(self):
		return f'Kanji(text=\033[1m{self.text}\033[0m, common={self.common})'

class Reading(namedtuple('Reading', 'text, nokanji, kanji_restriction, inf, common')):

	def __repr__(self):
		return f'Reading(text=\033[1m{self.text}\033[0m, common={self.common}, restriction={self.kanji_restriction})'

def _bold(strings):
	return ''.join(('[', ', '.join(map(lambda t: "'\033[1m" + t + "'\033[0m", strings)), ']'))

class Sense(namedtuple('Sense', 'kanji_restriction, reading_restriction, misc, lsource, dialect, glosses, s_inf')):

	def __repr__(self):
		return 'Sense(' + ', '.join([
			f'kanji_restriction={self.kanji_restriction}',
			f'reading_restriction={self.reading_restriction}',
			f'misc={self.misc}',
			f'dialect={self.dialect}',
			f'glosses={_bold(self.glosses)}',
			f's_inf={self.s_inf}'
		]) + ')'


Trans = namedtuple('Trans', 'types, glosses')
class SenseGroup(namedtuple('SenseGroup', 'pos, senses')):

	def is_archaic(self):
		for s in self.senses:
			if 'arch' not in s.misc:
				return False
		return True

	def _format(self, indent=2):
		res = ['\t'*indent + 'SenseGroup(']
		indent += 1
		res.append('\t'*indent + f'pos={_bold(self.pos)},')
		res.append('\t'*indent + 'senses=[')
		indent += 1
		for s in self.senses:
			res.append('\t'*indent + str(s) + ',')
		indent -= 1
		res.append('\t'*indent + ']')
		indent -= 1
		res.append('\t'*indent + ')')
		return '\n'.join(res)


class Entry(namedtuple('Entry', 'id, kanjis, readings, sense_groups')):

	def _format(self, indent=0):
		res = ['\t'*indent + f'Entry({self.id}']
		indent += 1
		res.append('\t'*indent + 'kanjis=[')
		indent += 1
		for k in self.kanjis:
			res.append('\t'*indent + str(k) + ',')
		indent -= 1
		res.append('\t'*indent + '],')
		res.append('\t'*indent + 'readings=[')
		indent += 1
		for r in self.readings:
			res.append('\t'*indent + str(r) + ',')
		indent -= 1
		res.append('\t'*indent + '],')
		res.append('\t'*indent + 'sense_groups=[')
		indent += 1
		for sg in self.sense_groups:
			res.append(sg._format(indent) + ',')
		indent -= 1
		res.append('\t'*indent + ']')
		indent -= 1
		res.append('\t'*indent + ')')
		return '\n'.join(res)

	def __repr__(self):
		return self._format()

	def is_common(self):
		return any(r.common for r in self.readings) or any(k.common for k in self.kanjis)

	def get_uk_readings(self):
		usually_kana = set()
		for sg in self.sense_groups:
			for s in sg.senses:
				if 'uk' in s.misc:
					if s.reading_restriction != ():
						usually_kana.update(s.reading_restriction)
					else:
						usually_kana.update(range(0, len(self.readings)))
						break
			else:
				continue

			break
		for i in usually_kana:
			yield self.readings[i]

Name = namedtuple('Name', 'id, kanjis, readings, transes')
def make_entry(elem, entities):
	entry = None
	all_kanjis = {}
	all_readings = {}
	last_tag = ''
	sense_group = None
	for child in elem:
		if child.tag == 'k_ele':
			assert last_tag == 'ent_seq' or last_tag == 'k_ele'

			kanji = child.find('keb').text
			inf = tuple(entities[el.text] for el in child.iter('ke_inf')) or None
			common = child.find('ke_pri') is not None
			entry.kanjis.append(Kanji(kanji, inf, common))
			all_kanjis[kanji] = len(entry.kanjis) - 1

		elif child.tag == 'r_ele':
			assert last_tag == 'ent_seq' or last_tag == 'k_ele' or last_tag == 'r_ele'

			reading = child.find('reb').text
			nokanji = child.find('re_nokanji') is not None
			kanji_restriction = tuple(all_kanjis[el.text] for el in child.iter('re_restr')) or None
			inf = tuple(entities[el.text] for el in child.iter('re_inf')) or None
			common = child.find('re_pri') is not None

			entry.readings.append(Reading(reading, nokanji, kanji_restriction, inf, common))
			all_readings[reading] = len(entry.readings) - 1

		elif child.tag == 'sense':
			assert last_tag == 'r_ele' or last_tag == 'sense'

			pos = tuple(entities[el.text] for el in child.iter('pos'))
			if len(pos) == 0:
				assert len(sense_group.pos) > 0
			else:
				if sense_group is not None:
					entry.sense_groups.append(sense_group)
				sense_group = SenseGroup(pos, [])

			kanji_restriction = tuple(all_kanjis[el.text] for el in child.iter('stagk')) or None
			readings_restriction = tuple(all_readings[el.text] for el in child.iter('stagr')) or None

			misc = tuple(entities[el.text] for el in child.iter('misc'))
			lsource = tuple(
				el.get('{http://www.w3.org/XML/1998/namespace}lang', 'eng') for el in child.iter('lsource')
			) or None
			dialect = tuple(entities[el.text] for el in child.iter('dial')) or None
			s_inf = tuple(el.text for el in child.iter('s_inf')) or None
			assert s_inf is None or len(s_inf) <= 1, ET.tostring(elem, encoding="unicode")
			if s_inf is not None:
				s_inf = s_inf[0]
			glosses = tuple(el.text for el in child.iter('gloss'))

			sense_group.senses.append(
				Sense(kanji_restriction, readings_restriction, misc, lsource, dialect, glosses, s_inf)
			)

		elif child.tag == 'trans':
			assert last_tag == 'r_ele' or last_tag == 'trans'
			if type(entry) == Entry:
				entry = Name(entry.id, entry.kanjis, entry.readings, [])

			types = list(map(lambda el: entities[el.text], child.iter('name_type')))
			glosses = list(map(lambda el: el.text, child.iter('trans_det')))
			entry.transes.append(Trans(types, glosses))
		else:
			assert child.tag == 'ent_seq'
			entry = Entry(int(child.text), [], [], [])

		last_tag = child.tag

	if type(entry) == Entry:
		entry.sense_groups.append(sense_group)
	del all_kanjis
	del all_readings

	return entry

def dictionary_reader(dictionary='JMdict_e.gz'):
	dictionary_path = download('http://ftp.monash.edu.au/pub/nihongo/' + dictionary, dictionary)
	entities = {}
	with gzip.open(dictionary_path, 'rt') as f:
		for l in f:
			if l.startswith('<JMdict>') or l.startswith('<JMnedict>'): break
			if l.startswith('<!ENTITY'):
				parts = l.strip().split(maxsplit=2)
				assert parts[2].startswith('"') and parts[2].endswith('">')
				assert parts[2][1:-2] not in entities
				entities[parts[2][1:-2]] = parts[1]

	entry_no = 0
	source = gzip.open(dictionary_path, 'rt')
	for _, elem in ET.iterparse(source):
		if elem.tag == 'entry':
			entry_no += 1
			if entry_no % 10000 == 0:
				print(dictionary, entry_no)
			entry = make_entry(elem, entities)
			yield entry
			elem.clear()
		elif elem.tag in ('JMdict', 'JMnedict'):
			elem.clear()

IndexedDictionaryType = Dict[str, List[Entry]]
def make_indexed_dictionary(
		entries,
		variate,
		convert_to_hiragana_for_index,
		agressive_conversion) -> IndexedDictionaryType:

	print('indexing dictionary')
	res = {}
	for e in entries:
		keys = index_keys(e,
			variate=variate,
			convert_to_hiragana=convert_to_hiragana_for_index,
			agressive_conversion=agressive_conversion
		)
		for key in keys:
			other_entries = res.setdefault(key, [])
			if len(other_entries) == 0 or other_entries[-1].id != e.id:
				other_entries.append(e)
	return res

DictionaryType = Dict[int, Entry]
def load_dictionary(
		dictionary='JMdict_e.gz',
		index=True,
		variate=False,
		convert_to_hiragana_for_index=True,
		agressive_conversion=True) -> Tuple[DictionaryType, IndexedDictionaryType]:

	print('loading dictionary', dictionary)
	filename = f'tmp/parsed-{dictionary}.pkl'
	if os.path.exists(filename):
		with open(filename, 'rb') as f:
			entries = pickle.load(f)
	else:
		entries = {e.id: e for e in dictionary_reader(dictionary)}
		with open(filename, 'wb') as f:
			pickle.dump(entries, f)

	if index:
		return entries, make_indexed_dictionary(
			entries.values(),
			variate,
			convert_to_hiragana_for_index,
			agressive_conversion
		)
	else:
		return entries
