#!/usr/bin/env python3
from utils import *
from index import index_keys
import xml.etree.ElementTree as ET
import gzip
import pickle
import os

Kanji = namedtuple('Kanji', 'text, common')
Reading = namedtuple('Reading', 'text, common, kanjis')
Sense = namedtuple('Sense', 'kanji_restriction, reading_restriction, misc, dialect, glosses, s_inf')
Trans = namedtuple('Trans', 'types, glosses')
class SenseGroup(namedtuple('SenseGroup', 'pos, senses')):

	def _format(self, indent=2):
		res = ['\t'*indent + 'SenseGroup(']
		indent += 1
		res.append('\t'*indent + 'pos=' + str(self.pos) + ',')
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
		res = ['\t'*indent + 'Entry(']
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

Name = namedtuple('Name', 'kanjis, readings, transes')
def make_entry(elem, entities):
	entry = None
	all_kanjis = {}
	all_kanji_indexes = None
	all_readings = {}
	all_reading_indexes = None
	last_tag = ''
	sense_group = None
	for child in elem:
		if child.tag == 'k_ele':
			assert last_tag == 'ent_seq' or last_tag == 'k_ele'

			kanji = child.find('keb').text

			# TODO take &uk; into account
			entry.kanjis.append(Kanji(kanji, child.find('ke_pri') is not None))
			all_kanjis[entry.kanjis[-1].text] = len(entry.kanjis) - 1

		elif child.tag == 'r_ele':
			assert last_tag == 'ent_seq' or last_tag == 'k_ele' or last_tag == 'r_ele'
			if all_kanji_indexes is None:
				all_kanji_indexes = range(len(entry.kanjis))

			kanjis_restriction = []
			for el in child.iter('re_restr'):
				kanjis_restriction.append(all_kanjis[el.text])
			if len(kanjis_restriction) == 0:
				kanjis_restriction = all_kanji_indexes

			'''
			FIXME somewhat strange
			'''
			common = child.find('re_pri') is not None

			original_text = child.find('reb').text
			common_text = kata_to_hira(original_text)
			ri = all_readings.get(common_text)
			if ri is not None:
				reading = entry.readings[ri]

				combined_restriction = set(reading.kanjis)
				combined_restriction.update(kanjis_restriction)
				if len(combined_restriction) == len(all_kanjis):
					combined_restriction = all_kanji_indexes

				entry.readings[ri] = Reading(common_text, reading.common or common, combined_restriction)
			else:
				entry.readings.append(Reading(original_text, common, kanjis_restriction))
				all_readings[common_text] = len(entry.readings) - 1

		elif child.tag == 'sense':
			assert last_tag == 'r_ele' or last_tag == 'sense'
			if all_reading_indexes is None:
				all_reading_indexes = range(len(entry.readings))

			pos = list(map(lambda el: entities[el.text], child.iter('pos')))
			if len(pos) == 0:
				assert len(sense_group.pos) > 0
			else:
				if sense_group is not None:
					entry.sense_groups.append(sense_group)
				sense_group = SenseGroup(pos, [])

			kanjis_restriction = list(map(lambda el: all_kanjis[el.text], child.iter('stagk')))

			readings_restriction = set(map(lambda el: all_readings[kata_to_hira(el.text)], child.iter('stagr')))

			misc = list(map(lambda el: entities[el.text], child.iter('misc')))
			dialect = list(map(lambda el: entities[el.text], child.iter('dial')))
			s_inf = list(map(lambda el: el.text, child.iter('s_inf')))
			assert len(s_inf) <= 1, ET.tostring(elem, encoding="unicode")
			if len(s_inf) == 0:
				s_inf = None
			else:
				s_inf = s_inf[0]
			glosses = list(map(lambda el: el.text, child.iter('gloss')))

			sense_group.senses.append(Sense(kanjis_restriction, readings_restriction, misc, dialect, glosses, s_inf))

		elif child.tag == 'trans':
			assert last_tag == 'r_ele' or last_tag == 'trans'
			if type(entry) == Entry:
				entry = Name(entry.kanjis, entry.readings, [])

			types = list(map(lambda el: entities[el.text], child.iter('name_type')))
			glosses = list(map(lambda el: el.text, child.iter('trans_det')))
			entry.transes.append(Trans(types, glosses))
		else:
			assert child.tag == 'ent_seq'
			entry = Entry(child.text, [], [], [])

		last_tag = child.tag

	if type(entry) == Entry:
		entry.sense_groups.append(sense_group)
	del all_kanjis
	del all_readings

	return entry

_dictionary = {}
#record_entry_hooks = []
def _record_entry(entry):
	for key in index_keys(entry, variate=False):
		_dictionary.setdefault(key, []).append(entry)

	#for hook in record_entry_hooks:
		#hook(entry)

def find_entry(k, r, d=None):
	if d is None:
		d = _dictionary
	entries = d.get(k)
	if entries is None:
		entries = d.get(kata_to_hira(k))
	if entries is None:
		return []
	if len(entries) == 1 or r is None:
		return entries
	r = kata_to_hira(r)
	for e in entries:
		for reading in e.readings:
			if kata_to_hira(reading.text) == r:
				return [e]
	raise Exception(f'Unknown entry {k}|{r}:\n{entries}')

def dictionary_reader(dictionary='JMdict_e.gz', store_in_memory=False):
	dictionary_path = download('http://ftp.monash.edu.au/pub/nihongo/' + dictionary, dictionary)
	entities = {}
	with gzip.open(dictionary_path, 'rt') as f:
		for l in f:
			if l.startswith('<JMdict>'): break
			if l.startswith('<!ENTITY'):
				parts = l.strip().split(maxsplit=2)
				assert parts[2].startswith('"') and parts[2].endswith('">')
				entities[parts[2][1:-2]] = parts[1]

	entry_no = 0
	source = gzip.open(dictionary_path, 'rt')
	for ev, elem in ET.iterparse(source):
		if elem.tag == 'entry':
			entry_no += 1
			if entry_no % 1000 == 0:
				print(dictionary, entry_no)
			entry = make_entry(elem, entities)
			yield entry, elem
			elem.clear()
			if store_in_memory:
				_record_entry(entry)
		elif elem.tag == 'JMdict':
			elem.clear()

def load_dictionary(dictionary='JMdict_e.gz'):
	global _dictionary
	if len(_dictionary) > 0:
		return
	if os.path.exists('tmp/parsed-jmdict.pkl'):
		with open('tmp/parsed-jmdict.pkl', 'rb') as f:
			_dictionary = pickle.load(f)
		return
	for _ in dictionary_reader(dictionary, True):
		pass
	with open('tmp/parsed-jmdict.pkl', 'wb') as f:
		pickle.dump(_dictionary, f)

