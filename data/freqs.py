#!/usr/bin/env python3
'''
	Computes entries frequency list, mapping UniDic lemmas and lexemes
	to JMdict entries and then applying this mapping to ja.wikipedia
	dump processed by mecab.

	Glossary:
	entry - <entry> from JMdict
	reading - <r_ele> from JMdict
	writing, kanji - <k_ele> from JMdict
	lexem - one line from UniDic's lex.csv
		when refering to the mecab's output may also mean a part of text,
		parsed by mecab as unknown
	lemma - all lexems with same lemma_id
	jmdict_id - <ent_seq> from JMdict
'''

from __future__ import annotations

import os
import subprocess
import pickle
import itertools
import functools
import gc
import re
import multiprocessing
import lzma
import csv
import random
from dataclasses import dataclass
from typing import Tuple, Set, List, Dict, DefaultDict, Union
from collections import namedtuple, defaultdict

import MeCab # https://github.com/SamuraiT/mecab-python3

from utils import download, is_katakana, is_kana, kata_to_hira, any, all, is_hiragana
import dictionary

'''
Full representation for lines from UniDic's lex.csv
'''
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
'''
Minimal representation for lines from UniDic's lex.csv
'''
UnidicLex = namedtuple('UnidicLex', 'pos, orthBase, pronBase, lemma_id')

UnidicPosType = Tuple[str, str, str, str]
UnidicType = Dict[int, Set[UnidicLex]]
UnidicIndexType = DefaultDict[str, Set[int]]

UNIDIC_NAME_POS = ('名詞', '固有名詞')

def download_dump():
	'''
		Downloads, extracts and strips markup from ja.wikipedia dump
		Lazy at every stage, but does not handle aborts and will happily
		use incomplete dump if download was previously aborted
	'''
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
	'''
		Downloads and extracts unidic
		Lazy at every stage, but does not handle aborts and will happily
		use incomplete dump if download was previously aborted
	'''
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
	'''
		Very simple match unidic lexem to JMdict entries.
	'''
	writing = kata_to_hira(lex.orthBase)
	reading = kata_to_hira(lex.pronBase)

	entries = jindex.get(writing, ())
	for entry in entries:

		'''
			There are a lot of false matches between unidic proper nouns and
			different JMdict entries, but we can't simply skip them, as such common
			names like "Asia" are in JMdict and we want to match them,
			so we explicitely process proper nouns here.
		'''
		if lex.pos[:2] == UNIDIC_NAME_POS and all('n' not in sg.pos for sg in entry.sense_groups):
			continue

		if reading == writing:
			'''
				Lexem with "surface" in (one or another or both) kana
			'''

			''' Excluding false katakana lex - hiragana entry matches'''
			if all(r.text != lex.orthBase for r in entry.readings):
				continue

			''' Heuristic conditions on possibility seeing this word in kana in real texts '''
			condition1 = len(entry.kanjis) == 0
			condition2 = condition1 or any(r.text == lex.orthBase and r.nokanji for r in entry.readings)
			condition3 = condition2 or (len(entries) == 1 and any(
				any('uk' in s.misc for s in sg.senses)
				for sg in entry.sense_groups
				if not sg.is_archaic()
			))
			if condition3:
				''' Returning orthBase to prevent false katakana - hiragana matches on next stages '''
				yield entry, lex.orthBase

		elif any(kata_to_hira(r.text) == reading for r in entry.readings):
			''' For lexem with kanji in "surface" we only need to find matching reading '''
			yield entry, writing

def find_unique_unidic2jmdict(unidic2jmdict) -> List[Tuple[int, int]]:
	'''
		Return list of (lemma_id, ent_seq) for all lemma_id
		having only one mapping to JMdict
	'''
	unique = []
	for lemma_id, jmdict_ids in unidic2jmdict.items():
		if len(jmdict_ids) == 1:
			unique.append((lemma_id, next(iter(jmdict_ids))))

	return unique

def record_pos_mapping(entry: dictionary.Entry, lex: UnidicLex, unidic_pos2jmdict_pos):
	'''
		Records unidic->jmdict POS tag mapping when there is absolutely
		no room for error
	'''

	'''
		If there are more than one sense group (we always ignore archaic)
		then there will be no unambiguous POS mapping
	'''
	if sum(not sg.is_archaic() for sg in entry.sense_groups) > 1:
		return

	for sg in entry.sense_groups:
		if sg.is_archaic():
			continue

		'''
			If there are more than one POS tag on this sense group,
			then there will be no unambiguous POS mapping.
			Note: "exp" isn't a POS tag, really. More like misc grammar info
		'''
		if len(sg.pos) > 1 and 'exp' not in sg.pos:
			return

		for p in sg.pos:
			''' Nope, not mapping "exp" to anything, sorry '''
			if p == 'exp':
				continue

			''' Mapping proper nouns to nouns only '''
			if lex.pos[:2] == UNIDIC_NAME_POS and not p.startswith('n'):
				continue

			''' Recording lex and ent_seq for possible future analysis '''
			unidic_pos2jmdict_pos.setdefault((lex.pos, p), (lex, entry.id))

PosMappingType = Set[Tuple[UnidicPosType, str]]
def match_unidic_jmdict_pos(
		jmdict: dictionary.DictionaryType, jindex: dictionary.IndexedDictionaryType,
		unidic: UnidicType, uindex: UnidicIndexType) -> PosMappingType:

	unidic2jmdict = defaultdict(set)

	print('simple matching')
	for lemma_lexes in unidic.values():
		for lex in lemma_lexes:
			for entry, _ in u2j_simple_match(lex, jindex, uindex):
				unidic2jmdict[lex.lemma_id].add(entry.id)
	del lemma_lexes, lex

	print('mappings u2j:', len(unidic2jmdict))

	print('computing unique mappings')
	unidic2jmdict_unique = find_unique_unidic2jmdict(unidic2jmdict)
	print(len(unidic2jmdict_unique), 'unique')

	unidic_pos2jmdict_pos = {}
	for lemma_id, jmdict_id in unidic2jmdict_unique:
		record_pos_mapping(jmdict[jmdict_id], next(iter(unidic[lemma_id])), unidic_pos2jmdict_pos)
	del unidic2jmdict_unique

	with open('tmp/unidic_pos2jmdict_pos.dat', 'w') as of:
		print("# vi: tabstop=50", file=of)
		items = list(unidic_pos2jmdict_pos.items())
		items.sort(key=lambda p: p[0])
		for (upos, jpos), (lex, jid) in items:
			print(','.join(upos), jpos, ','.join(map(str, lex[1:])), jid, sep='\t', file=of)
		del items

	res = set(unidic_pos2jmdict_pos.keys())
	del unidic2jmdict, unidic_pos2jmdict_pos
	gc.collect()

	return res


################## POS AND REFINED MAPPING ##################

def check_u2j_pos_match(entry, lex, u2j_pos):
	'''
		Tests if any POS tag in entry has mapping from UniDic pos
	'''
	for sg in entry.sense_groups:
		if sg.is_archaic():
			continue
		if any(((lex.pos, jpos) in u2j_pos) for jpos in sg.pos):
			return True
	return False

def u2j_match_with_pos(lex, jindex: dictionary.IndexedDictionaryType, uindex: UnidicIndexType, u2j_pos):
	'''
		Like `u2j_simple_match()`, but additionaly checks POS mapping.
	'''
	for entry, writing in u2j_simple_match(lex, jindex, uindex):
		if check_u2j_pos_match(entry, lex, u2j_pos):
			yield entry, writing

SimpleU2JMappingType = Dict[int, Union[int, Set[Union[int, Tuple[str, int]]]]]
def compute_final_unambiguous_unidic2jmdict_mapping(
		jmdict2unidic, unidic2jmdict, lemma_id2writing2jmdict_id
		) -> SimpleU2JMappingType:
	'''
		Computes plain (one lexem to one entry) UniDic->JMdict mapping
	'''

	mapping = {}
	for lemma_id, jmdict_ids in unidic2jmdict.items():
		assert len(jmdict_ids) > 0

		if len(jmdict_ids) == 1:
			''' One2one mapping case '''
			mapping[lemma_id] = next(iter(jmdict_ids))

		elif all(len(jmdict2unidic[jmdict_id]) == 1 for jmdict_id in jmdict_ids):
			'''
				Star mapping case: one UniDic lemma maps unambiguously
				to several JMdict entries
			'''
			mapping[lemma_id] = jmdict_ids

		else:
			'''
				Ambiguous star case
			'''
			assert lemma_id in lemma_id2writing2jmdict_id, (lemma_id, unidic2jmdict.get(lemma_id))

			''' Recording mappings to entries uniquely identified by writing '''
			writing2jmdict_ids = lemma_id2writing2jmdict_id.get(lemma_id)
			for w, sub_jmdict_ids in writing2jmdict_ids.items():
				if len(sub_jmdict_ids) == 1:
					mapping.setdefault(lemma_id, []).append((w, next(iter(sub_jmdict_ids))))

	return mapping

def is_lemma_single_cover_for_entry(lemma_lexes, entry):
	''' Checks if UniDic lemma contains all readings and writings of `entry` '''

	all_orthbase = set(lex.orthBase for lex in lemma_lexes)
	return (
		all(r.text in all_orthbase for r in entry.readings)
		and
		all(k.text in all_orthbase for k in entry.kanjis)
	)

def is_entry_single_cover_for_lemma(entry, lemma_lexes):
	''' Checks if JMdict entry contains all orthBases of `lemma` '''
	all_writings_and_readings = set(itertools.chain(
		(r.text for r in entry.readings),
		(k.text for k in entry.kanjis)
	))
	return all(lex.orthBase in all_writings_and_readings for lex in lemma_lexes)

def is_single_cover(dict2_node, dict1_node):
	'''
		Generic function to check if lemma is completely coverd by entry
		or vise versa
	'''
	if type(dict1_node) == dictionary.Entry:
		assert len(dict2_node) > 0, (dict1_node, dict2_node)
		assert type(dict2_node) == set and type(next(iter(dict2_node))) == UnidicLex, (dict1_node, dict2_node)
		return is_lemma_single_cover_for_entry(dict2_node, dict1_node)
	else:
		assert len(dict1_node) > 0, (dict1_node, dict2_node)
		assert type(dict2_node) == dictionary.Entry and type(dict1_node) == set and type(next(iter(dict1_node))) == UnidicLex, (dict1_node, dict2_node)
		return is_entry_single_cover_for_lemma(dict2_node, dict1_node)

def find_single_cover(dict1_node, dict2, dict2_keys):
	'''
		Generic function to find unique complete cover for lemma by entry
		or vise versa
	'''
	single_covers = []
	for dict2_key in dict2_keys:
		if is_single_cover(dict2[dict2_key], dict1_node):
			single_covers.append(dict2_key)

	if len(single_covers) == 1:
		return single_covers[0]

def cut_out_redundunt_mappings_for_fully_covered_nodes(dict1, dict1_to_dict2, dict2, dict2_to_dict1):
	'''
		Symmetric generic functions. Checks lemma->entry (or vise versa)
		mapping to see if there exists _single_ entry (lemma), which has
		all orthBases as readings and writings (all readings and writings
		as orthBases).
		If such entry (lemma) was found, removes all mappings to other
		entries (lemmas).

		Logic here is if there is such entry which includes all orthBase
		of some lemma, then we are pretty sure this is one and only entry
		corresponding to this lemma. And vise versa.
	'''
	for dict1_key, dict2_keys in dict1_to_dict2.items():
		if len(dict2_keys) == 1:
			''' Already unique '''
			continue

		assert all(dict2_key in dict2_to_dict1 for dict2_key in dict2_keys)
		if all(len(dict2_to_dict1[dict2_key]) == 1 for dict2_key in dict2_keys):
			''' Already a star case, no need to reduce further '''
			continue

		single_cover_dict2_key = find_single_cover(dict1[dict1_key], dict2, dict2_keys)
		if single_cover_dict2_key is None:
			continue

		''' Removing mapping and back-mapping to other entries (lemmas) '''
		for other_dict2_key in dict2_keys:
			if other_dict2_key != single_cover_dict2_key:
				dict1_keys = dict2_to_dict1.get(other_dict2_key)
				if len(dict1_keys) == 1:
					dict2_to_dict1.pop(other_dict2_key)
				else:
					dict1_keys.remove(dict1_key)

		dict2_keys.clear()
		dict2_keys.add(single_cover_dict2_key)

def try_add_unmatched_entires(jmdict, jmdict2unidic, unidic2jmdict, uindex, lemma_id2writing2jmdict_id):
	'''
		Records unmapped JMdict entries which have unique
		writing or reading match in UniDic.

		It helps with entries which are conjugated forms of other words,
		as `uindex` has records for "surface", "pron" and "orth"
		fields, which are not used during simple matching.
	'''

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
		u2j_pos: Set[Tuple[UnidicPosType, str]]
		) -> SimpleU2JMappingType:
	'''
		Computes plain (one lexem to one entry) UniDic->JMdict mapping,
		performing additional heuristical refinement
	'''

	jmdict2unidic = defaultdict(set)
	unidic2jmdict = defaultdict(set)
	lemma_id2writing2jmdict_id = defaultdict(lambda: defaultdict(set))

	print('pos matching')
	for lemma_lexes in unidic.values():
		for lex in lemma_lexes:
			for entry, writing in u2j_match_with_pos(lex, jindex, uindex, u2j_pos):
				jmdict2unidic[entry.id].add(lex.lemma_id)
				unidic2jmdict[lex.lemma_id].add(entry.id)
				lemma_id2writing2jmdict_id[lex.lemma_id][writing].add(entry.id)
	del lex

	try_add_unmatched_entires(jmdict, jmdict2unidic, unidic2jmdict, uindex, lemma_id2writing2jmdict_id)
	assert all(len(vs) > 0 for vs in jmdict2unidic.values())
	assert all(len(vs) > 0 for vs in unidic2jmdict.values())

	print(f'mappings: j2u: {len(jmdict2unidic)}, u2j: {len(unidic2jmdict)}')

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

def is_known_lexem(parse_line):
	return len(parse_line) >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM

def compute_reading(variant) -> Union[re.Pattern, str]:
	'''
		Computes expected entry reading from several mecab's parse lines.
		If all lines represents known lexems, returns string,
		otherwise returns regex with wildcards in place of unknown
		lexems' readings
	'''

	is_regex = False
	reading = []
	for l in variant:
		if is_known_lexem(l):
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
	''' Checks if `parsed_reading` from mecab matches `dictionary_reading` from JMdict '''
	if type(parsed_reading) == str:
		return parsed_reading == dictionary_reading
	else:
		return parsed_reading.fullmatch(dictionary_reading) is not None

def variant_matches_reading(entry, kanji_index, variant):
	'''
		Checks if reading from mecab's parsed `variant` matches any
		reading (<r_ele>) of writing (<k_ele>) at `kanji_index` in `entry`
	'''
	if len(variant) == 1 and not is_known_lexem(variant[0]):
		''' Unknown parse matches any readings '''
		return True

	parsed_reading = compute_reading(variant)
	for r in entry.readings:
		''' Matching only readings appliable to writing at `kanji_index` '''
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
	'''
		Returns first parse variant from `variants` with parsed reading
		matching any reading of writing at `kanji_index` in `entry`
	'''
	for variant in variants:
		if variant_matches_reading(entry, kanji_index, variant):
			return variant
	return None

@dataclass
class ComplexMappingNode(object):
	jmdict_ids: Set[int]
	children: Dict[Union[str, int], ComplexMappingNode]

def get_complex_mapping_key(parse_line):
	''' Returns lemma_id for known lexems and surface for unknown '''
	if is_known_lexem(parse_line):
		return parse_line[LEMMA_ID_INDEX]
	else:
		return parse_line[0]

ComplexMappingType = Dict[Union[str, int], ComplexMappingNode]
def record_complex_mapping(mapping: ComplexMappingType, parse, jmdict_id):
	'''
		Records complex mapping from sequence of lexems `parse`
		to entry `jmdict_id`
	'''

	''' Complex mapping is basicly a tree, so here we create new path '''
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

	target.jmdict_ids.add(jmdict_id)

def have_uk_for_reading(entry, reading_index):
	''' Checks if `uk` tag is appliable to reading at `reading_index` in entry '''
	for sg in entry.sense_groups:
		for s in sg.senses:
			if s.reading_restriction is not None and reading_index not in s.reading_restriction:
				continue
			if 'uk' in s.misc:
				return True

KnownMecabLexem = namedtuple('KnownMecabLexem', '''
	surface,
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
UnknownMecabLexem = namedtuple('UnknownMecabLexem', 'surface, pos1, pos2, pos3, pos4, cType, cForm')
def parse_mecab_variants(parse, one):
	'''
		Splits several mecab's parse variants and every parse line.
		For known lexems converts lemma_id to `int`

		`one` - return first variant
	'''

	if type(parse) == str:
		parse = parse.split('\n')[:(-1 if one else -2)]
	variants = [[]]
	for l in parse:
		if l.startswith('EOS'):
			variants.append([])
			continue

		l = l.split('\t')
		l.extend(l.pop().split(','))
		if is_known_lexem(l):
			l[LEMMA_ID_INDEX] = int(l[LEMMA_ID_INDEX])
		variants[-1].append(l)

	if one:
		return variants[0]
	else:
		return variants

def compute_complex_mapping(jmdict, already_mapped_jmdict_ids) -> Tuple[ComplexMappingType, Set[int]]:
	'''
		Uses mecab to parse previously unmapped JMdict entries
		and map to sequence of UniDic lexems
	'''
	mapping = {}
	mecab = MeCab.Tagger('-d tmp/unidic-cwj-2.3.0')
	mapped_jmdict_ids = set()

	for entry_index, entry in enumerate(jmdict.values()):
		if (entry_index + 1) % 10000 == 0:
			print(f'complex mappings {entry_index + 1}/{len(jmdict)}')

		''' Skipping already mapped entries '''
		if entry.id in already_mapped_jmdict_ids:
			continue

		for i, k in enumerate(entry.kanjis):
			assert ',' not in k
			# correct parse for entry 1177810 appears after 15+ variants
			# similar at entry 1363410
			# entry 1269140 have alterations in reading preventing match
			# similar at entry 1379410
			''' Using 10 best parses and mapping first with matching reading '''
			parse = mecab.parseNBest(10, k.text)
			variants = parse_mecab_variants(parse, one=False)
			matching_variant = match_reading_to_any_variant(entry, i, variants)
			if matching_variant is None:
				#print('ERROR: unmatched reading:', k.text, entry, parse, sep='\n')
				continue
			record_complex_mapping(mapping, matching_variant, entry.id)
			mapped_jmdict_ids.add(entry.id)
			del k

		for i, r in enumerate(entry.readings):
			''' Checking if this reading could appear in texts by itself '''
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
			if any(not is_known_lexem(l) for l in variant) and (len(variant) > 1 or not all(is_katakana(c) for c in r.text)):
				''' Very peculiar indeed, but alas, quite common '''
				#print('WARNING: strange reading parse:', r.text)
				pass
			record_complex_mapping(mapping, variant, entry.id)
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
		jindex: dictionary.IndexedDictionaryType,
		unidic: UnidicType
		) -> Dict[int, Set[int]]:
	'''
		Computes plain (one lemma -> one entry) UniDic->JMnedict mappings
	'''

	mapping = {}

	mapped = set()
	print('mapping jmnedict')
	for lemma_lexes in unidic.values():
		lemma_id = None
		for lex in lemma_lexes:
			lemma_id = lex.lemma_id

			''' Ignoring non proper noun lexems '''
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
	''' Checks if `entry` has reading matching `pron` or `pron_base` '''
	global_precondition = len(entry.kanjis) == 0

	if is_regex:
		pron = re.compile(pron)
		pron_base = re.compile(pron_base)

	for i, r in enumerate(entry.readings):
		precondition = global_precondition or r.nokanji or have_uk_for_reading(entry, i)
		if not precondition:
			continue

		text = kata_to_hira(r.text)
		for p in (pron, pron_base):
			if is_regex and p.fullmatch(text) is not None:
				return True
			if not is_regex and text == p:
				return True

	return False

def try_extract_and_record_complex_mapping(sentence, word_index, u2j_complex_mapping, jmdict, freqs) -> int:
	'''
		Searches for matching complex mapping in `sentence` starting at
		`word_index`, records to `freqs` if found and returns length of
		matched complex mapping (number of parse lines)
	'''
	possible_ends = []
	current_level = u2j_complex_mapping
	current_index = word_index
	continuous_orth = ''
	continuous_orth_base = ''
	continuous_pron = ''
	continuous_pron_base = ''
	is_regex = False

	''' Computing intermidate results while descending in complex mapping tree '''
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
			''' There is not entries we can match here '''
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

	''' Searching for mapping match checking from longest to shortest '''
	for offset in range(len(possible_ends) - 1, -1, -1):
		if possible_ends[offset] is None:
			continue

		jmdict_ids, orth, orth_base, is_regex, pron, pron_base = possible_ends[offset]
		if len(jmdict_ids) == 1:
			'''
				There is exactly one possible match.
				No need to check for writing or reading
			'''
			freqs[next(iter(jmdict_ids))] += 1
			return offset

		for jmdict_id in jmdict_ids:
			entry = jmdict.get(jmdict_id)

			if have_matching_writing(entry, orth, orth_base):
				freqs[jmdict_id] += 1
				return offset

			'''
				If we are unable to match writing we should try
				to match reading only in special cases
			'''
			try_to_match_reading_precondition = continuous_orth == continuous_pron or is_regex
			if try_to_match_reading_precondition and have_matching_reading(entry, is_regex, pron, pron_base):
				freqs[jmdict_id] += 1
				return offset

def try_record_simple_mapping(parse_line, unidic2jmdict_mapping: SimpleU2JMappingType, freqs):
	'''
		Searches for entries mapped from lemma in `parse_line` and
		records to `freqs` if found
	'''
	if not is_known_lexem(parse_line):
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
		assert type(lemma_mapping) == list
		for coerced_writing in (parse_line[ORTH_BASE_INDEX], kata_to_hira(parse_line[ORTH_BASE_INDEX])):
			for writing, jmdict_id in lemma_mapping:
				if coerced_writing == writing:
					freqs[jmdict_id] += 1
					mapped = True

			if mapped:
				break

	return mapped

def try_record_jmnedict_mapping(parse_line, u2jmnedict_mapping, freqs):
	if not is_known_lexem(parse_line):
		return
	if parse_line[POS_INDEX:POS_INDEX+2] != UNIDIC_NAME_POS:
		return

	for jmnedict_id in u2jmnedict_mapping.get(parse_line[-1], ()):
		freqs[jmnedict_id] += 1

def process_sentence(
		sentence,
		unidic2jmdict_mapping, u2j_complex_mapping, u2jmnedict_mapping,
		jmdict,
		freqs,
		token_processor):
	'''
		Searches for mapped lemmas or sequences in `sentence` and records
		them to `freqs`
	'''

	sentence = parse_mecab_variants(sentence, one=True)
	i = -1
	while i + 1 < len(sentence):
		i += 1

		if get_complex_mapping_key(sentence[i]) in u2j_complex_mapping:
			skip = try_extract_and_record_complex_mapping(sentence, i, u2j_complex_mapping, jmdict, freqs)
			if skip is not None:
				token_processor(sentence, i, i + skip + 1)

				i += skip
				continue

		token_processor(sentence, i, i + 1)

		if try_record_simple_mapping(sentence[i], unidic2jmdict_mapping, freqs):
			continue

		try_record_jmnedict_mapping(sentence[i], u2jmnedict_mapping, freqs)

	token_processor(None)

def write_token_to_split_corpus(of, sentence, start=None, end=None):
	if sentence is None:
		print(file=of)
		return

	for j in range(start, end):
		print(sentence[j][0], end='', file=of)
	print(end=' ', file=of)

def drop(*args):
	pass

def process_corpus(unidic2jmdict_mapping, u2j_complex_mapping, u2jmnedict_mapping, jmdict):
	extracted_dump = download_dump()
	# with open('tmp/raw-corpus.txt', 'wb') as of:
	mecab = subprocess.Popen([f'unxz -c {extracted_dump} | mecab -d tmp/unidic-cwj-2.3.0'],
	#mecab = subprocess.Popen([f'cat tmp/test.dat | egrep -v "^#" | mecab'],
			shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)

	split_corpus_of = lzma.open('tmp/corpus.txt.xz', 'wt')
	split_corpus_writer = functools.partial(write_token_to_split_corpus, split_corpus_of)

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
						freqs,
						split_corpus_writer if random.random() < 0.001 else drop,
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

	split_corpus_of.close()

	return freqs

def load_unidic() -> Tuple[UnidicType, UnidicIndexType]:
	download_unidic()

	print('loading unidic')
	res = {}
	index = defaultdict(set)
	filename = 'tmp/unidic-cwj-2.3.0/lex.csv'
	with open(filename, newline='') as f:
		reader = csv.reader(f, delimiter=',', quotechar='"')
		for l in reader:
			assert len(l) == 33
			if l[0] == '':
				assert l[31] == '23697232981271040'
				l[0] = '"'

			l = FullUnidicLex(*l)
			for k in (l.surface, l.lForm, l.lemma, l.orth, l.pron, l.orthBase, l.pronBase):
				index[kata_to_hira(k)].add(int(l.lemma_id))
			l = UnidicLex((l.pos1, l.pos2, l.pos3, l.pos4), l.orthBase, l.pronBase, int(l.lemma_id))
			res.setdefault(l.lemma_id, set()).add(l)

	return res, index

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
	jmnedict_mapping = match_unidic_jmnedict(jmnedict_index, unidic)
	del jmnedict, jmnedict_index
	gc.collect()

	jmdict, jindex = dictionary.load_dictionary()
	u2j_pos = match_unidic_jmdict_pos(jmdict, jindex, unidic, uindex)
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
		# Using `multiprocessing` to reduce memory consumption after mappings computation
		with multiprocessing.Pool(1) as p:
			jmdict, jmdict_mapping, jmdict_complex_mapping, jmnedict_mapping = p.apply(compute_mappings)
		dump_mappings(filename, jmdict_mapping, jmdict_complex_mapping, jmnedict_mapping)
		return jmdict, jmdict_mapping, jmdict_complex_mapping, jmnedict_mapping

def compute_freqs():
	jmdict, mapping, complex_mapping, jmnedict_mapping = get_mappings_and_dictionaries()

	print('lemma 37562:',mapping.get(37562))
	jmdict_id = 2028940
	for k, v in mapping.items():
		if type(v) == int:
			if v == jmdict_id:
				print(f'entry {jmdict_id}: {k}')
		elif type(v) == set:
			if 1502390 in v:
				print(f'entry {jmdict_id}: {k}')
		elif type(v) == list:
			for w, v in v:
				if v == jmdict_id:
					print(f'entry {jmdict_id}: {k} {w}')
		else:
			assert False
	print('lemma 37562:', complex_mapping[37562])

	freqs = process_corpus(mapping, complex_mapping, jmnedict_mapping, jmdict)

	del jmdict, mapping, complex_mapping, jmnedict_mapping
	gc.collect()

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

__freq_order = None
def initialize():
	global __freq_order
	if __freq_order is None:
		__freq_order = compute_freq_order()

def get_frequency(entry):
	return __freq_order.get(entry.id)

if __name__ == '__main__':
	initialize()
