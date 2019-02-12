#!/usr/bin/env python3
from __future__ import annotations


import os
import subprocess
import shlex
import sys
import pickle
import itertools
import gc
import re
from dataclasses import dataclass
from typing import Tuple, Set, List, Dict, DefaultDict, Union
from collections import namedtuple, defaultdict

import MeCab # https://github.com/SamuraiT/mecab-python3

from utils import download, is_katakana, is_kana, kata_to_hira, any, all, is_hiragana
import dictionary

FullUnidicLex = namedtuple('FullUnidicLex', '''
	surface, leftId, rightId, weight,
	pos1, pos2, pos3, pos4,
	cType, cForm,
	lForm, lemma,
	orth, pron, orthBase, pronBase,
	goshu,
	iType, iForm, fType, fForm, iConType, fConType,
	type, kana, kanaBase, form, formBase,
	aType, aConType, aModType,
	lid, lemma_id
''')
UnidicLex = namedtuple('UnidicLex', 'pos, orthBase, pronBase, lemma_id')
UnidicPosType = Tuple[str, str, str, str]
UnidicType = Dict[int, Set[UnidicLex]]
UnidicIndexType = DefaultDict[str, Set[int]]
UNIDIC_NAME_POS = ('名詞', '固有名詞')

def split_lex(l):
	if l.startswith('""'):
		assert l.count('"') == 2
		return l.split(',')

	res = []
	start = 0
	end = l.find('"')
	while end >= 0:
		if start < end:
			res.extend(l[start:end - 1].split(','))
		start = end + 1
		end = l.find('"', end + 1)
		res.append(l[start:end])
		start = end + 2
		end = l.find('"', start)
	res.extend(l[start:].split(','))

	return res

assert split_lex('a,,"d,e,f",h,,"k,l",m') == ['a', '', 'd,e,f', 'h', '', 'k,l', 'm']
assert split_lex('"a,,",d,"k,l",m') == ['a,,', 'd', 'k,l', 'm']

def download_dump():
	extracted_dump = 'tmp/jawiki-text.xz'
	if not os.path.exists(extracted_dump):
		wikiextractor = download(
			'https://github.com/versusvoid/wikiextractor/archive/master.tar.gz',
			'wikiextractor.tar.gz'
		)
		if not os.path.exists('tmp/wikiextractor-master'):
			subprocess.check_call(["tar", "-xf", wikiextractor, '-C', 'tmp'])

		download(
			'https://dumps.wikimedia.org/jawiki/latest/jawiki-latest-pages-articles.xml.bz2',
			'jawiki-articles.xml.bz2'
		)
		print("Stripping wiki markup")
		print("FIXME the extractor process will hang at the end")
		subprocess.check_call([' | '.join([
			'tmp/wikiextractor-master/WikiExtractor.py -q -o - --no-templates -s --lists tmp/jawiki-articles.xml.bz2',
			# 'head -n 400000',
			'egrep -v "^<"',
			'xz > tmp/jawiki-text.xz'])], shell=True)

	return extracted_dump

def download_unidic():
	files = ['char.bin', 'dicrc', 'matrix.bin', 'sys.dic', 'unk.dic', 'lex.csv']
	if all(map(lambda fn: os.path.exists('tmp/unidic-cwj-2.3.0/' + fn), files)):
		return

	filename = 'tmp/unidic-cwj-2.3.0.zip'
	download('https://unidic.ninjal.ac.jp/unidic_archive/cwj/2.3.0/unidic-cwj-2.3.0.zip', filename)

	print('Extracting unidic')
	subprocess.check_call(
		[
			'bsdtar', '-xv',
			'-C', 'tmp',
			'-f', filename,
		] + [f'unidic-cwj-2.3.0/{f}' for f in files],
		stderr=subprocess.PIPE,
		universal_newlines=True
	)


################# SIMPLE MAPPING #################

def u2j_simple_match(lex, jindex: dictionary.IndexedDictionaryType, uindex: UnidicIndexType):
	writing = kata_to_hira(lex.orthBase)
	reading = kata_to_hira(lex.pronBase)

	entries = jindex.get(writing, ())
	for entry in entries:
		if lex.pos[:2] == UNIDIC_NAME_POS and all('n' not in sg.pos for sg in entry.sense_groups):
			continue

		if reading == writing:
			condition1 = len(entry.kanjis) == 0
			condition2 = condition1 or any(r.text == lex.orthBase and r.nokanji for r in entry.readings)
			condition3 = condition2 or (len(entries) == 1 and any(
				any('uk' in s.misc for s in sg.senses)
				for sg in entry.sense_groups
				if not sg.is_archaic()
			))
			if condition3:
				yield entry, writing
		elif (
				any(kata_to_hira(r.text) == reading for r in entry.readings)
				# or # 取り鍋, but it's a strange thing
				# (len(entries) == 1 and len(uindex[writing]) == 1)
				):

			yield entry, writing

def find_one2ones(a2b, b2a):
	one2ones = []
	for k, vs in a2b.items():
		v = next(iter(vs))
		if len(vs) == 1 and len(b2a[v]) == 1:
			one2ones.append((k, v))

	return one2ones

def record_pos_mapping(entry: dictionary.Entry, lex: UnidicLex, unidic_pos2jmdict_pos):
	if sum(not sg.is_archaic() for sg in entry.sense_groups) > 1:
		return

	for sg in entry.sense_groups:
		if sg.is_archaic():
			continue

		if len(sg.pos) > 1 and 'exp' not in sg.pos:
			return

		for p in sg.pos:
			if p == 'exp':
				continue
			if lex.pos[:2] == UNIDIC_NAME_POS and not p.startswith('n'):
				continue

			unidic_pos2jmdict_pos.setdefault((lex.pos, p), (lex, entry.id))

PosMappingType = Set[Tuple[UnidicPosType, str]]
def match_unidic_jmdict_one2one(
		jmdict: dictionary.DictionaryType, jindex: dictionary.IndexedDictionaryType,
		unidic: UnidicType, uindex: UnidicIndexType) -> PosMappingType:

	jmdict2unidic = defaultdict(set)
	unidic2jmdict = defaultdict(set)

	print('simple matching')
	for lemma_lexes in unidic.values():
		for lex in lemma_lexes:
			for entry, _ in u2j_simple_match(lex, jindex, uindex):
				jmdict2unidic[entry.id].add(lex.lemma_id)
				unidic2jmdict[lex.lemma_id].add(entry.id)
	del lemma_lexes, lex

	print(f'mappings: j2u: {len(jmdict2unidic)}, u2j: {len(unidic2jmdict)}')

	# print(jmdict2unidic.get(1000430), jmdict2unidic.get(1000420))
	# print(unidic2jmdict.get(911), unidic2jmdict.get(912), unidic2jmdict.get(6965))

	print('computing unambiguous mappings')
	one2ones = find_one2ones(jmdict2unidic, unidic2jmdict)
	print(len(one2ones), 'unambiguouses')

	unidic_pos2jmdict_pos = {}
	for jmdict_id, lemma_id in one2ones:
		record_pos_mapping(jmdict[jmdict_id], next(iter(unidic[lemma_id])), unidic_pos2jmdict_pos)
	del one2ones

	with open('tmp/unidic_pos2jmdict_pos.dat', 'w') as of:
		print("# vi: tabstop=50", file=of)
		items = list(unidic_pos2jmdict_pos.items())
		items.sort(key=lambda p: p[0])
		for (upos, jpos), (lex, jid) in items:
			print(','.join(upos), jpos, ','.join(map(str, lex[1:])), jid, sep='\t', file=of)
		del items

	res = set(unidic_pos2jmdict_pos.keys())
	# somehow_mapped_jmdict_ids = set(jmdict2unidic.keys())
	del jmdict2unidic, unidic2jmdict, unidic_pos2jmdict_pos
	gc.collect()
	return res


################## POS AND REFINED MAPPING ##################

def u2j_match_pos_single(entry, lex, u2j_pos):
	for sg in entry.sense_groups:
		if sg.is_archaic():
			continue
		if any(((lex.pos, jpos) in u2j_pos) for jpos in sg.pos):
			return True
	return False

def u2j_match_pos_all(lex, jindex: dictionary.IndexedDictionaryType, uindex: UnidicIndexType, u2j_pos):
	for entry, writing in u2j_simple_match(lex, jindex, uindex):
		if u2j_match_pos_single(entry, lex, u2j_pos):
			yield entry, writing

SimpleU2JMappingType = Dict[int, Union[int, Set[Union[int, Tuple[str, int]]]]]
def compute_final_unambiguous_unidic2jmdict_mapping(
		jmdict2unidic, unidic2jmdict, lemma_id2writing2jmdict_id
		) -> SimpleU2JMappingType:

	mapping = {}
	for lemma_id, jmdict_ids in unidic2jmdict.items():
		assert len(jmdict_ids) > 0
		if len(jmdict_ids) == 1:
			mapping[lemma_id] = next(iter(jmdict_ids))
		elif all(len(jmdict2unidic[jmdict_id]) == 1 for jmdict_id in jmdict_ids):
			mapping[lemma_id] = jmdict_ids
		else:
			assert lemma_id in lemma_id2writing2jmdict_id, (lemma_id, unidic2jmdict.get(lemma_id))
			writing2jmdict_ids = lemma_id2writing2jmdict_id.get(lemma_id)
			for w, sub_jmdict_ids in writing2jmdict_ids.items():
				if len(sub_jmdict_ids) == 1:
					mapping.setdefault(lemma_id, []).append((w, next(iter(sub_jmdict_ids))))


	return mapping

def is_lemma_single_cover_for_entry(lemma_lexes, entry):
	all_orthbase = set(lex.orthBase for lex in lemma_lexes)
	return (
		all(r.text in all_orthbase for r in entry.readings)
		and
		all(k.text in all_orthbase for k in entry.kanjis)
	)

def is_entry_single_cover_for_lemma(entry, lemma_lexes):
	all_writings_and_readings = set(itertools.chain((r.text for r in entry.readings), (k.text for k in entry.kanjis)))
	return all(lex.orthBase in all_writings_and_readings for lex in lemma_lexes)

def is_single_cover(dict2_node, dict1_node):
	if type(dict1_node) == dictionary.Entry:
		assert len(dict2_node) > 0, (dict1_node, dict2_node)
		assert type(dict2_node) == set and type(next(iter(dict2_node))) == UnidicLex, (dict1_node, dict2_node)
		return is_lemma_single_cover_for_entry(dict2_node, dict1_node)
	else:
		assert len(dict1_node) > 0, (dict1_node, dict2_node)
		assert type(dict2_node) == dictionary.Entry and type(dict1_node) == set and type(next(iter(dict1_node))) == UnidicLex, (dict1_node, dict2_node)
		return is_entry_single_cover_for_lemma(dict2_node, dict1_node)

def find_single_cover(dict1_node, dict2, dict2_keys):
	single_covers = []
	for dict2_key in dict2_keys:
		if is_single_cover(dict2[dict2_key], dict1_node):
			single_covers.append(dict2_key)

	if len(single_covers) == 1:
		return single_covers[0]

def cut_out_redundunt_mappings_for_fully_covered_nodes(dict1, dict1_to_dict2, dict2, dict2_to_dict1):
	for dict1_key, dict2_keys in dict1_to_dict2.items():
		if len(dict2_keys) == 1:
			continue
		assert all(dict2_key in dict2_to_dict1 for dict2_key in dict2_keys)
		if all(len(dict2_to_dict1[dict2_key]) == 1 for dict2_key in dict2_keys): # already a star
			continue

		single_cover_dict2_key = find_single_cover(dict1[dict1_key], dict2, dict2_keys)
		if single_cover_dict2_key is None:
			continue

		for other_dict2_key in dict2_keys:
			if other_dict2_key != single_cover_dict2_key:
				dict1_keys = dict2_to_dict1.get(other_dict2_key)
				if len(dict1_keys) == 1:
					dict2_to_dict1.pop(other_dict2_key)
				else:
					dict1_keys.remove(dict1_key)

		dict2_keys.clear()
		dict2_keys.add(single_cover_dict2_key)

# records conjugated jmdict entries unambiguously mapped to unidic
def try_add_unmatched_entires(jmdict, jmdict2unidic, unidic2jmdict, uindex, lemma_id2writing2jmdict_id):
	for k, entry in jmdict.items():
		if k in jmdict2unidic:
			continue

		for text in itertools.chain((r.text for r in entry.readings), (k.text for k in entry.kanjis)):
			text = kata_to_hira(text)
			lemma_ids = uindex.get(text, ())
			if len(lemma_ids) == 1:
				lemma_id = next(iter(lemma_ids))
				jmdict2unidic[entry.id].add(lemma_id)
				unidic2jmdict[lemma_id].add(entry.id)
				lemma_id2writing2jmdict_id[lemma_id][text].add(entry.id)

def match_unidic_jmdict_with_refining(
		jmdict: dictionary.DictionaryType,
		jindex: dictionary.IndexedDictionaryType,
		unidic: UnidicType,
		uindex: UnidicIndexType,
		u2j_pos: Set[Tuple[UnidicPosType, str]]) -> SimpleU2JMappingType:

	jmdict2unidic = defaultdict(set)
	unidic2jmdict = defaultdict(set)
	lemma_id2writing2jmdict_id = defaultdict(lambda: defaultdict(set))

	print('pos matching')
	for lemma_lexes in unidic.values():
		for lex in lemma_lexes:
			for entry, writing in u2j_match_pos_all(lex, jindex, uindex, u2j_pos):
				jmdict2unidic[entry.id].add(lex.lemma_id)
				unidic2jmdict[lex.lemma_id].add(entry.id)
				lemma_id2writing2jmdict_id[lex.lemma_id][writing].add(entry.id)
	del lex

	try_add_unmatched_entires(jmdict, jmdict2unidic, unidic2jmdict, uindex, lemma_id2writing2jmdict_id)
	assert all(len(vs) > 0 for vs in jmdict2unidic.values())
	assert all(len(vs) > 0 for vs in unidic2jmdict.values())

	print(f'mappings: j2u: {len(jmdict2unidic)}, u2j: {len(unidic2jmdict)}')

	assert all(len(lexes) > 0 for lexes in unidic.values())

	cut_out_redundunt_mappings_for_fully_covered_nodes(jmdict, jmdict2unidic, unidic, unidic2jmdict)
	cut_out_redundunt_mappings_for_fully_covered_nodes(unidic, unidic2jmdict, jmdict, jmdict2unidic)

	print('computing mappings')
	mapping = compute_final_unambiguous_unidic2jmdict_mapping(jmdict2unidic, unidic2jmdict, lemma_id2writing2jmdict_id)
	print(len(mapping), 'unidic ids')

	del jmdict2unidic, unidic2jmdict, lemma_id2writing2jmdict_id
	return mapping


################## COMPLEX MAPPING ##################

# for magic numbers see `dicrc` file from unidic
NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM = 29
POS_INDEX = 1
ORTH_INDEX = 9
PRON_INDEX = 10
ORTH_BASE_INDEX = 11
PRON_BASE_INDEX = 12
# -1 'cos some fields in unidic may contain commas in them
# and mecab does not print them in unambiguous way (using quotes like in unidic/lex.csv),
# so lemma_id may be at position 28, 29 or 30, but it's always last
LEMMA_ID_INDEX = -1

def compute_reading(variant):
	is_regex = False
	reading = []
	for l in variant:
		if len(l) >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM:
			reading.append(l[PRON_INDEX])
		else:
			reading.append('.+')
			is_regex = True
	reading = kata_to_hira(''.join(reading))
	if is_regex:
		return re.compile(reading)
	else:
		return reading

def reading_matches(parsed_reading, dictionary_reading):
	#print(f'reading_matches({parsed_reading}, {dictionary_reading})')
	if type(parsed_reading) == str:
		return parsed_reading == dictionary_reading
	else:
		return parsed_reading.fullmatch(dictionary_reading) is not None

def variant_matches_reading(entry, kanji_index, variant):
	if len(variant) == 1 and len(variant[0]) < NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM:
		return True
	parsed_reading = compute_reading(variant)
	for r in entry.readings:
		if (
				not r.nokanji
				and
				(
					r.kanji_restriction is None
					or
					kanji_index in r.kanji_restriction
				)
				and
				reading_matches(parsed_reading, kata_to_hira(r.text))
			):

			return True

	return False

def match_reading_to_any_variant(entry, kanji_index, variants):
	for variant in variants:
		if variant_matches_reading(entry, kanji_index, variant):
			return variant
	return None

@dataclass
class ComplexMappingNode(object):
	jmdict_ids: int
	children: Dict[int, ComplexMappingNode]

def get_complex_mapping_key(parse_line):
	if len(parse_line) >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM:
		return parse_line[LEMMA_ID_INDEX]
	else:
		return parse_line[0]

ComplexMappingType = Dict[Union[str, int], ComplexMappingNode]
def record_complex_mapping(mapping: ComplexMappingType, parse, id, text):
	key = get_complex_mapping_key(parse[0])
	target = mapping.get(key)
	if target is None:
		target = ComplexMappingNode(set(), {})
		mapping[key] = target

	for l in parse[1:]:
		key = get_complex_mapping_key(l)
		new_target = target.children.get(key)
		if new_target is None:
			new_target = ComplexMappingNode(set(), {})
			target.children[key] = new_target
		target = new_target

	target.jmdict_ids.add(id)

def have_uk_for_reading(entry, reading_index):
	for sg in entry.sense_groups:
		for s in sg.senses:
			if s.reading_restriction is not None and reading_index not in s.reading_restriction:
				continue
			if 'uk' in s.misc:
				return True

def parse_mecab_variants(parse, one):
	if type(parse) == str:
		parse = parse.split('\n')[:(-1 if one else -2)]
	variants = [[]]
	for l in parse:
		if l.startswith('EOS'):
			variants.append([])
			continue

		l = l.split('\t')
		l.extend(l.pop().split(','))
		if len(l) >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM:
			l[LEMMA_ID_INDEX] = int(l[LEMMA_ID_INDEX])
		variants[-1].append(l)

	if one:
		return variants[0]
	else:
		return variants

def compute_complex_mapping(jmdict, already_mapped_jmdict_ids) -> Tuple[ComplexMappingType, Set[int]]:
	mapping = {}
	mecab = MeCab.Tagger('-d tmp/unidic-cwj-2.3.0')
	mapped_jmdict_ids = set()

	for entry_index, entry in enumerate(jmdict.values()):
		if (entry_index + 1) % 10000 == 0:
			print(f'complex mappings {entry_index + 1}/{len(jmdict)}')

		if entry.id in already_mapped_jmdict_ids:
			continue
		for i, k in enumerate(entry.kanjis):
			assert ',' not in k
			# correct parse for entry 1177810 appears after 15+ variants
			# similar at entry 1363410
			# entry 1269140 have alterations in reading preventing match
			# similar at entry 1379410
			parse = mecab.parseNBest(10, k.text)
			variants = parse_mecab_variants(parse, one=False)
			matching_variant = match_reading_to_any_variant(entry, i, variants)
			if matching_variant is None:
				#print('ERROR: unmatched reading:', k.text, entry, parse, sep='\n')
				continue
			record_complex_mapping(mapping, matching_variant, entry.id, kata_to_hira(k.text))
			mapped_jmdict_ids.add(entry.id)
			del k

		for i, r in enumerate(entry.readings):
			if (
					len(entry.kanjis) > 0
					and
					any(not is_katakana(c) for c in r.text)
					and
					not r.nokanji
					and
					not have_uk_for_reading(entry, i)
					):

				continue

			variant = parse_mecab_variants(mecab.parse(r.text), one=True)
			if any(len(l) < NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM for l in variant) and (len(variant) > 1 or not all(is_katakana(c) for c in r.text)):
				#print('WARNING: strange reading parse:', r.text)
				pass
			record_complex_mapping(mapping, variant, entry.id, kata_to_hira(r.text))
			mapped_jmdict_ids.add(entry.id)

	del mecab
	return mapping, mapped_jmdict_ids


################## JMNEDICT ##################

def unidic2jmnedict_simple_match(lex, jindex):
	writing = kata_to_hira(lex.orthBase)
	reading = kata_to_hira(lex.pronBase)

	entries = jindex.get(writing, ())
	for entry in entries:
		if reading == writing:
			if any(r.text == writing for r in entry.readings):
				yield entry
		elif any(kata_to_hira(r.text) == reading for r in entry.readings):
			yield entry

def match_unidic_jmnedict(
		jmnedict: dictionary.DictionaryType, jindex: dictionary.IndexedDictionaryType,
		unidic: UnidicType) -> Dict[int, Set[int]]:

	mapping = {}

	mapped = set()
	print('mapping jmnedict')
	for lemma_lexes in unidic.values():
		lemma_id = None
		for lex in lemma_lexes:
			lemma_id = lex.lemma_id
			if lex.pos[:2] != UNIDIC_NAME_POS:
				continue
			for entry in unidic2jmnedict_simple_match(lex, jindex):
				mapped.add(entry.id)

		if len(mapped) > 0:
			mapping[lemma_id] = mapped.copy()
		mapped.clear()

	gc.collect()
	return mapping


################## CORPUS PROCESSING ##################

def have_matching_writing(entry, orth, orth_base):
	return any(kata_to_hira(k.text) in (orth, orth_base) for k in entry.kanjis)

def have_matching_reading(entry, is_regex, pron, pron_base):
	global_precondition = len(entry.kanjis) == 0
	if is_regex:
		pron = re.compile(pron)
		pron_base = re.compile(pron_base)
	for i, r in enumerate(entry.readings):
		precondition = global_precondition or r.nokanji or have_uk_for_reading(entry, i)
		if precondition:
			text = kata_to_hira(r.text)
			for p in (pron, pron_base):
				if is_regex and p.fullmatch(text) is not None:
					return True
				if not is_regex and text == p:
					return True
	return False

def try_extract_and_record_complex_mapping(sentence, word_index, u2j_complex_mapping, jmdict, freqs) -> int:
	possible_ends = []
	current_level = u2j_complex_mapping
	current_index = word_index
	continuous_orth = ''
	continuous_orth_base = ''
	continuous_pron = ''
	continuous_pron_base = ''
	is_regex = False

	while current_index < len(sentence):
		current_key = get_complex_mapping_key(sentence[current_index])
		complex_mapping_node = current_level.get(current_key)
		if complex_mapping_node is None:
			break

		if len(sentence[current_index]) >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM:
			continuous_orth += sentence[current_index][ORTH_INDEX]
			continuous_orth_base += sentence[current_index][ORTH_BASE_INDEX]
			continuous_pron += sentence[current_index][PRON_INDEX]
			continuous_pron_base += sentence[current_index][PRON_BASE_INDEX]
		else:
			continuous_orth += sentence[current_index][0]
			continuous_orth_base += sentence[current_index][0]
			continuous_pron += '.+'
			continuous_pron_base += '.+'
			is_regex = True

		if complex_mapping_node.jmdict_ids is None:
			possible_ends.append(None)
		else:
			possible_ends.append((
				complex_mapping_node.jmdict_ids,
				kata_to_hira(continuous_orth),
				kata_to_hira(continuous_orth_base),
				is_regex,
				kata_to_hira(continuous_pron),
				kata_to_hira(continuous_pron_base),
			))
		current_index += 1
		current_level = complex_mapping_node.children

	for current_index in range(len(possible_ends) - 1, -1, -1):
		if possible_ends[current_index] is None:
			continue
		jmdict_ids, orth, orth_base, is_regex, pron, pron_base = possible_ends[current_index]
		if len(jmdict_ids) == 1:
			freqs[next(iter(jmdict_ids))] += 1
			return current_index

		for jmdict_id in jmdict_ids:
			entry = jmdict.get(jmdict_id)

			if have_matching_writing(entry, orth, orth_base):
				freqs[jmdict_id] += 1
				return current_index

			try_to_match_reading_precondition = continuous_orth == continuous_pron or is_regex
			if try_to_match_reading_precondition and have_matching_reading(entry, is_regex, pron, pron_base):
				freqs[jmdict_id] += 1
				return current_index

def try_record_simple_mapping(parse_line, unidic2jmdict_mapping: SimpleU2JMappingType, freqs):
	if len(parse_line) < NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM:
		return

	lemma_mapping = unidic2jmdict_mapping.get(parse_line[LEMMA_ID_INDEX])
	if lemma_mapping is None:
		return

	mapped = False
	if type(lemma_mapping) == int:
		freqs[lemma_mapping] += 1
		mapped = True
	elif type(lemma_mapping) == set:
		for jmdict_id in lemma_mapping:
			assert type(jmdict_id) == int
			freqs[jmdict_id] += 1
			mapped = True
	else:
		coerced_writing = kata_to_hira(parse_line[ORTH_BASE_INDEX])
		assert type(lemma_mapping) == list
		for writing, jmdict_id in lemma_mapping:
			if coerced_writing == writing:
				freqs[jmdict_id] += 1
				mapped = True

	return mapped

def try_record_jmnedict_mapping(parse_line, u2jmnedict_mapping, freqs):
	if len(parse_line) < NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM:
		return
	if parse_line[POS_INDEX:POS_INDEX+2] != UNIDIC_NAME_POS:
		return

	for jmnedict_id in u2jmnedict_mapping.get(parse_line[-1], ()):
		freqs[jmnedict_id] += 1

def process_sentence(sentence, unidic2jmdict_mapping, u2j_complex_mapping, u2jmnedict_mapping, jmdict, freqs):
	sentence = parse_mecab_variants(sentence, one=True)
	i = -1
	while i + 1 < len(sentence):
		i += 1

		if get_complex_mapping_key(sentence[i]) in u2j_complex_mapping:
			skip = try_extract_and_record_complex_mapping(sentence, i, u2j_complex_mapping, jmdict, freqs)
			if skip is not None:
				i += skip
				continue

		if try_record_simple_mapping(sentence[i], unidic2jmdict_mapping, freqs):
			continue

		try_record_jmnedict_mapping(sentence[i], u2jmnedict_mapping, freqs)

def process_corpus(unidic2jmdict_mapping, u2j_complex_mapping, u2jmnedict_mapping, jmdict):
	extracted_dump = download_dump()
	# with open('tmp/raw-corpus.txt', 'wb') as of:
	mecab = subprocess.Popen([f'unxz -c {extracted_dump} | mecab -d tmp/unidic-cwj-2.3.0'],
	#mecab = subprocess.Popen([f'cat tmp/test.dat | egrep -v "^#" | mecab'],
			shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)

	freqs = defaultdict(int)
	iterator = enumerate(mecab.stdout)
	sentence = []
	while True:
		try:
			line_no, l = next(iterator)
			if l.startswith('EOS'):
				if len(sentence) > 0:
					process_sentence(
						sentence,
						unidic2jmdict_mapping, u2j_complex_mapping, u2jmnedict_mapping,
						jmdict,
						freqs
					)
				sentence.clear()
			else:
				if '\t' not in l:
					print(f'strange parse line: "{l}"')
				else:
					sentence.append(l)

			if (line_no + 1) % 1000000 == 0:
				print(line_no + 1)
		except (StopIteration, KeyboardInterrupt):
			break
		except UnicodeDecodeError:
			continue
		except Exception:
			import traceback
			print('some error:')
			traceback.print_exc()
			input()
			continue

	return freqs

def load_unidic() -> Tuple[UnidicType, UnidicIndexType]:
	download_unidic()

	print('loading unidic')
	res = {}
	index = defaultdict(set)
	filename = 'tmp/unidic-cwj-2.3.0/lex.csv'
	with open(filename) as f:
		for l in f:
			l = FullUnidicLex(*split_lex(l.strip()))
			for k in (l.surface, l.lForm, l.lemma, l.orth, l.pron, l.orthBase, l.pronBase):
				index[kata_to_hira(k)].add(int(l.lemma_id))
			l = UnidicLex((l.pos1, l.pos2, l.pos3, l.pos4), l.orthBase, l.pronBase, int(l.lemma_id))
			res.setdefault(l.lemma_id, set()).add(l)

	return res, index

def load_additional_pos_mapping(u2j_pos: PosMappingType):
	with open('data/unidic-jmdict-pos-mapping.dat') as f:
		for l in f:
			l = l.strip()
			if len(l) == 0 or l.startswith('#'):
				continue
			upos, jpos = l.split()[:2]
			upos = tuple(upos.split(','))
			u2j_pos.add((upos, jpos))

def get_mapped_jmdict_ids(mapping):
	mapped_jmdict_ids = set()
	for v in mapping.values():
		if type(v) == int:
			mapped_jmdict_ids.add(v)
		else:
			for s in v:
				if type(s) == int:
					mapped_jmdict_ids.add(s)
				else:
					mapped_jmdict_ids.add(s[1])
	return mapped_jmdict_ids

def load_mappings(filename):
	with open(filename, 'rb') as f:
		mapping = pickle.load(f)
		complex_mapping = pickle.load(f)
		jmnedict_mapping = pickle.load(f)
		return mapping, complex_mapping, jmnedict_mapping

def compute_mappings():
	unidic, uindex = load_unidic()

	jmnedict, jmnedict_index = dictionary.load_dictionary('JMnedict.xml.gz')
	jmnedict_mapping = match_unidic_jmnedict(jmnedict, jmnedict_index, unidic)

	del jmnedict, jmnedict_index
	gc.collect()

	jmdict, jindex = dictionary.load_dictionary()

	u2j_pos = match_unidic_jmdict_one2one(jmdict, jindex, unidic, uindex)
	load_additional_pos_mapping(u2j_pos)

	mapping = match_unidic_jmdict_with_refining(jmdict, jindex, unidic, uindex, u2j_pos)

	del unidic, uindex, u2j_pos, jindex
	gc.collect()

	mapped_jmdict_ids = get_mapped_jmdict_ids(mapping)
	complex_mapping, new_mapped_jmdict_ids = compute_complex_mapping(jmdict, mapped_jmdict_ids)
	mapped_jmdict_ids.update(new_mapped_jmdict_ids)

	print(len(mapped_jmdict_ids), 'mapped jmdict entries')
	print(
		sum(1 for entry in jmdict.values() if entry.is_common() and entry.id not in mapped_jmdict_ids),
		'unmapped commons'
	)
	print('Here they are:')
	for entry in jmdict.values():
		if entry.is_common() and entry.id not in mapped_jmdict_ids:
			print(entry)

	del mapped_jmdict_ids, new_mapped_jmdict_ids
	gc.collect()

	return jmdict, mapping, complex_mapping, jmnedict_mapping

def dump_mappings(filename, jmdict_mapping, jmdict_complex_mapping, jmnedict_mapping):
	with open(filename, 'wb') as of:
		pickle.dump(jmdict_mapping, of)
		pickle.dump(jmdict_complex_mapping, of)
		pickle.dump(jmnedict_mapping, of)

def get_mappings_and_dictionaries():
	filename = 'tmp/unidic2jmdict-mapping.pkl'
	if os.path.exists(filename):
		jmdict = dictionary.load_dictionary(index=False)
		return (jmdict, *load_mappings(filename))
	else:
		jmdict, jmdict_mapping, jmdict_complex_mapping, jmnedict_mapping = compute_mappings()
		dump_mappings(filename, jmdict_mapping, jmdict_complex_mapping, jmnedict_mapping)
		return jmdict, jmdict_mapping, jmdict_complex_mapping, jmnedict_mapping

def compute_freqs():
	jmdict, mapping, complex_mapping, jmnedict_mapping = get_mappings_and_dictionaries()

	freqs = process_corpus(mapping, complex_mapping, jmnedict_mapping, jmdict)
	return list(freqs.items())

def save_freqs(freqs):
	with open('tmp/jmdict-freqs.dat', 'w') as of:
		for k, v in freqs:
			print(k, v, sep='\t', file=of)

def load_freqs():
	res = []
	with open('tmp/jmdict-freqs.dat') as f:
		for l in f:
			k, v = map(int, l.strip().split())
			res.append((k, v))
	return res

def compute_freq_order():
	if os.path.exists('tmp/jmdict-freqs.dat'):
		freqs = load_freqs()
	else:
		freqs = compute_freqs()
		save_freqs(freqs)

	freqs.sort(key=lambda p: p[1], reverse=True)
	return {k:i for i, (k, v) in enumerate(freqs) if v >= 77}

__freq_order = compute_freq_order()
def get_frequency(entry):
	return __freq_order.get(entry.id)

if __name__ == '__main__':
	a, b, c = load_mappings('tmp/unidic2jmdict-mapping.pkl')
	for k, vs in a.items():
		if type(vs) == int:
			if vs == 1135480:
				print(k)
		elif type(vs) == set:
			if 1135480 in vs:
				print(k)
		elif type(vs) == list:
			for w, v in vs:
				if v == 1135480:
					print(w, k)
		else:
			assert False
raise Exception('FIXME ent_seq 1135480 absolutely incorrectly maps to 37876 物,接頭辞')
raise Exception('FIXME ent_seq 1502390 does not displays')