#!/usr/bin/env python3
from __future__ import annotations


import os
import subprocess
import shlex
import sys
import pickle
import itertools
import gc
import regex
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

unidic_pos2jmdict_pos = {}
def add_mapping(unidic_pos, jmdict_pos, mapped):
	d = unidic_pos2jmdict_pos
	for p in unidic_pos:
		if p in ('*', ''):
			break
		d = d.setdefault(p, {})
	d[jmdict_pos] = mapped

def load_unidic2jmdict_pos():
	with open('data/unidic-jmdict-pos-mapping.dat') as f:
		for l in f:
			l = l.strip().split('\t')
			if len(l) > 1 and not l[0].startswith('#'):
				assert l[5] in ('True', 'False')
				add_mapping(l[:4], l[4], l[5] == 'True')

def dump_submapping(of, d, path):
	items = list(d.items())
	items.sort(key=lambda p:p[0])
	for k, v in items:
		if type(v) == bool:
			filler = ['*'] * (4 - len(path))
			print(*path, *filler, k, v, sep='\t', file=of)
		else:
			dump_submapping(of, v, (*path, k))

	if len(path) == 1:
		print(file=of)

def dump_unidic2jmdict_pos():
	with open('data/unidic-jmdict-pos-mapping.dat', 'w') as of:
		dump_submapping(of, unidic_pos2jmdict_pos, ())

def grep_unidic_lemma(lemma, lemma_id):
	os.system(f"rg ',{lemma_id}$' tmp/unidic-cwj-2.3.0/lex.csv")
	print()
	os.system(f"rg '^{lemma},' tmp/unidic-cwj-2.3.0/lex.csv")

def ask_for_pos_mapping_update(possible_jmdict_pos, full_unidic_pos, variant, entry):
	print(f"Can't map\n{entry}")
	grep_unidic_lemma(variant.split('\t')[0], variant.split(',')[-1])

	possible_jmdict_pos = list(possible_jmdict_pos)
	jmdict_pos = possible_jmdict_pos[0]
	if len(possible_jmdict_pos) > 1:
		print('Select jmdict pos:')
		for i, p in enumerate(possible_jmdict_pos):
			print(f"[{i + 1}] {p}")
		i = None
		while i is None:
			i = input("[1]: ").strip()
			if len(i) == 0:
				i = 0
			elif i.isdigit() and int(i) > 0 and int(i) <= len(possible_jmdict_pos):
				i = int(i) - 1
			else:
				i = None
		jmdict_pos = possible_jmdict_pos[i]

	mapped = None
	while mapped is None:
		mapped = input("Mapped? [y/N]: ").strip().lower()
		if mapped in ('y', 'yes', '1', 'true'):
			mapped = True
		elif mapped in ('n', 'no', '0', 'false', ''):
			mapped = False
		else:
			mapped = None

	if len(full_unidic_pos[1]) > 0:
		n = None
		while n is None:
			for i, p in enumerate(full_unidic_pos):
				if len(p) == 0:
					i = i - 1
					break
				print(f'[{i+1}]', ','.join(full_unidic_pos[:i+1]))
			n = input(f'How much? [{i + 1}]:').strip()
			if n == '':
				n = i + 1
			elif n.isdigit() and int(n) > 0 and int(n) <= i + 1:
				n = int(n)
			else:
				n = None
		full_unidic_pos = full_unidic_pos[:n]
	else:
		full_unidic_pos = full_unidic_pos[:1]

	return full_unidic_pos, jmdict_pos, mapped

def update_mapping(unidic_pos, jpos, mapped, entry_id):
	add_mapping(unidic_pos, jpos, mapped)
	# dump_unidic2jmdict_pos()
	with open('data/unidic-jmdict-pos-mapping.dat', 'a') as of:
		filler = ['*'] * (4 - len(unidic_pos))
		print(*unidic_pos, *filler, jpos, mapped, entry_id, sep='\t', file=of)

def match_pos(possible_jmdict_pos, full_unidic_pos, ask_for_pos_match, variant, entry):
	have_some = False
	for jpos in possible_jmdict_pos:
		if jpos == 'exp':
			have_some = True
			continue
		d = unidic_pos2jmdict_pos
		for upos in full_unidic_pos:
			if upos == '' or d is None or jpos in d:
				break
			d = d.get(upos)

		if d is not None:
			assert type(d) == dict
			allowed = d.get(jpos)
			if allowed is True:
				return True
			elif allowed is False:
				have_some = True

	if have_some:
		return False
	if ask_for_pos_match:
		upos, jpos, mapped = ask_for_pos_mapping_update(possible_jmdict_pos, full_unidic_pos, variant, entry)
		update_mapping(upos, jpos, mapped, entry.id)
		return mapped

# for magic numbers see `dicrc` file from unidic
NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM = 28
ORTH_INDEX = 9
PRON_INDEX = 9
ORTH_BASE_INDEX = 10
PRON_BASE_INDEX = 11
# -1 'cos some fields in unidic may contain commas in them
# and mecab does not print them in unambiguous way (using quotes like in unidic/lex.csv),
# so lemma_id may be at position 28, 29 or 30, but it's always last
LEMMA_ID_INDEX = -1

def get_unidic_lexem_key(properties):
	return (properties[ORTH_BASE_INDEX], properties[PRON_BASE_INDEX], int(properties[LEMMA_ID_INDEX]))

def match_variants(all_variants, all_readings, jmdict_pos, entry, ask_for_pos_match):
	for variant in all_variants:
		variant_properties = variant.split('\t')[1].split(',')
		assert len(variant_properties) >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM

		if all_readings is not None:
			unidic_readings = (
				variant_properties[11],
				variant_properties[9],
				variant_properties[6],
			)
			if all(lambda r: kata_to_hira(r) not in all_readings, unidic_readings):
				continue

		unidic_pos = variant_properties[:4]
		if not match_pos(jmdict_pos, unidic_pos, ask_for_pos_match, variant, entry):
			continue

		return get_unidic_lexem_key(variant_properties)

def synthesize_mapping(lexeme, mecab, jmdict_pos, entry, all_readings=None):
	all_variants = []
	unsplit_parse_prefix = lexeme + '\t'
	if len(lexeme) == 1:
		N = 10
	elif len(lexeme) == 2:
		N = 5
	else:
		N = 3
	for l in mecab.parseNBest(N, lexeme).split('\n')[:-1]:
		if l.startswith(unsplit_parse_prefix) and l.count(',') >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM:
			all_variants.append(l.strip())

	res = match_variants(all_variants, all_readings, jmdict_pos, entry, ask_for_pos_match=False)
	if res is None:
		return match_variants(all_variants, all_readings, jmdict_pos, entry, ask_for_pos_match=True)
	else:
		return res

def u2j_simple_match(lex, jindex: dictionary.IndexedDictionaryType, uindex: UnidicIndexType):
	writing = kata_to_hira(lex.orthBase)
	reading = kata_to_hira(lex.pronBase)

	entries = jindex.get(writing, ())
	if lex.pos[:2] == ('名詞', '固有名詞') and len(entries) > 1:
		return
	for entry in entries:
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
			if p != 'exp':
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

	test_jmdict_ids = ()
	test_unidic_ids = ()
	print(*(f'{i}:{jmdict2unidic.get(i)}' for i in test_jmdict_ids))
	print(*(f'{i}:{unidic2jmdict.get(i)}' for i in test_unidic_ids))

	for uid in set(itertools.chain.from_iterable(jmdict2unidic.get(i, ()) for i in test_jmdict_ids)):
		print(*unidic[uid], sep='\n')
	for jid in set(itertools.chain.from_iterable(unidic2jmdict.get(i, ()) for i in test_unidic_ids)):
		print(jmdict[jid], sep='\n')
	if len(test_jmdict_ids) + len(test_unidic_ids) > 0:
		input()

	print('computing mappings')
	mapping = compute_final_unambiguous_unidic2jmdict_mapping(jmdict2unidic, unidic2jmdict, lemma_id2writing2jmdict_id)
	print(len(mapping), 'unidic ids')

	del jmdict2unidic, unidic2jmdict, lemma_id2writing2jmdict_id
	return mapping

def match_unidic_ids_with_jmdict_old():
	download_unidic()
	mecab = MeCab.Tagger('-d tmp/unidic-cwj-2.3.0')

	load_unidic2jmdict_pos()

	seen_entries = set()
	unidic2jmdict_id_mapping = {}

	skip = 0
	if DEBUG:
		if os.path.exists('tmp/u2j.skip'):
			with open('tmp/u2j.skip') as f:
				skip = int(f.read() or 0)
		skip_f = open('tmp/u2j.skip', 'w')
		print('skip:', skip)

	# TODO JMnedict too
	# TODO parse directly from JMdict.xml and utilize all the meta-info for matching
	# (lsource, misc, maybe even s_inf)
	# TODO 2 collaborative filtering: other lexes for same lemma (other readings, writings)
	# help each other filter out impossible candidates
	iterator = itertools.islice(
		enumerate(itertools.chain.from_iterable(dictionary._dictionary.values())),
		skip, None
	)
	missing_commons = 0
	print('Matching jmdict entries with unidic lexemes')
	for entry_index, (_, entry) in iterator:
		if DEBUG:
			skip_f.flush()
			skip_f.seek(0)
			skip_f.write(str(entry_index))

		if entry.id in seen_entries: continue
		seen_entries.add(entry.id)
		if len(seen_entries) % 10000 == 0:
			print(f'Processing {len(seen_entries)} entry #{entry.id}')

		all_archaic = True
		usually_kana = set()
		for sg in entry.sense_groups:
			for s in sg.senses:
				all_archaic = all_archaic and 'arch' in s.misc
				if 'uk' in s.misc:
					if s.reading_restriction != ():
						usually_kana.update(s.reading_restriction)
					else:
						usually_kana.update(range(0, len(entry.readings)))
		if all_archaic: continue

		pos = set()
		pos.update(*map(lambda sg: sg.pos, entry.sense_groups))

		any_common = False
		any_map = False

		all_readings = set()
		for i, r in enumerate(entry.readings):
			all_readings.add(kata_to_hira(r.text))
			if is_katakana(r.text[0]) or i in usually_kana or len(entry.kanjis) == 0:
				try:
					unidic_id = synthesize_mapping(r.text, mecab, pos, entry)
				except KeyError:
					print(f'Entry at position #{entry_index}')
					raise

				if r.common:
					any_common = True

				if unidic_id is not None:
					unidic2jmdict_id_mapping.setdefault(unidic_id, entry.id)
					any_map = True


		for k in entry.kanjis:
			try:
				unidic_id = synthesize_mapping(k.text, mecab, pos, entry, all_readings)
			except KeyError:
				print(f'Entry at position #{entry_index}')
				raise

			if k.common:
				any_common = True

			if unidic_id is not None:
				unidic2jmdict_id_mapping.setdefault(unidic_id, entry.id)
				any_map = True

		if any_common and not any_map:
			missing_commons += 1

	del mecab
	print(missing_commons, 'commons missing mapping from unidic')
	print(len(unidic2jmdict_id_mapping), 'unidic lexemes mapped to jmdict')
	return unidic2jmdict_id_mapping

def have_matching_writing(entry, orth, orth_base):
	return any(kata_to_hira(k.text) in (orth, orth_base) for k in entry.kanjis)

def have_matching_reading(entry, pron, pron_base):
	global_precondition = len(entry.kanjis) == 0
	for i, r in enumerate(entry.readings):
		precondition = global_precondition or r.nokanji or have_uk_for_reading(entry, i)
		if precondition and kata_to_hira(r.text) in (pron, pron_base):
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

	while current_index < len(sentence):
		current_key = get_complex_mapping_key(sentence[current_index])
		complex_mapping_node = current_level.get(current_key)
		if complex_mapping_node is None:
			break

		if len(sentence[current_index]) >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM + 1:
			continuous_orth += sentence[current_index][ORTH_INDEX + 1]
			continuous_orth_base += sentence[current_index][ORTH_BASE_INDEX + 1]
			continuous_pron += sentence[current_index][PRON_INDEX + 1]
			continuous_pron_base += sentence[current_index][PRON_BASE_INDEX + 1]
		else:
			continuous_orth += sentence[current_index][0]
			continuous_orth_base += sentence[current_index][0]
			# TODO? regex for unknown prons as in mapping
			continuous_pron += sentence[current_index][0]
			continuous_pron_base += sentence[current_index][0]

		if complex_mapping_node.jmdict_ids is None:
			possible_ends.append(None)
		else:
			possible_ends.append((
				complex_mapping_node.jmdict_ids,
				kata_to_hira(continuous_orth),
				kata_to_hira(continuous_orth_base),
				kata_to_hira(continuous_pron),
				kata_to_hira(continuous_pron_base),
			))
		current_index += 1
		current_level = complex_mapping_node.children

	for current_index in range(len(possible_ends) - 1, -1, -1):
		if possible_ends[current_index] is None:
			continue
		jmdict_ids, orth, orth_base, pron, pron_base = possible_ends[current_index]
		if len(jmdict_ids) == 1:
			freqs[next(iter(jmdict_ids))] += 1
			return current_index

		for jmdict_id in jmdict_ids:
			entry = jmdict.get(jmdict_id)

			if have_matching_writing(entry, orth, orth_base):
				freqs[jmdict_id] += 1
				return current_index

			if continuous_orth == continuous_pron and have_matching_reading(entry, pron, pron_base):
				freqs[jmdict_id] += 1
				return current_index

def try_record_simple_mapping(parse_line, unidic2jmdict_mapping: SimpleU2JMappingType, freqs):
	if len(parse_line) < NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM + 1:
		return

	lemma_mapping = unidic2jmdict_mapping.get(parse_line[-1])
	if lemma_mapping is None:
		return

	if type(lemma_mapping) == int:
		freqs[lemma_mapping] += 1
		return
	elif type(lemma_mapping) == set:
		for jmdict_id in lemma_mapping:
			assert type(jmdict_id) == int
			freqs[jmdict_id] += 1
	else:
		coerced_writing = kata_to_hira(parse_line[ORTH_BASE_INDEX + 1])
		assert type(lemma_mapping) == list
		for writing, jmdict_id in lemma_mapping:
			if coerced_writing == writing:
				freqs[jmdict_id] += 1

def process_sentence(sentence, unidic2jmdict_mapping, u2j_complex_mapping, jmdict, freqs):
	sentence = parse_mecab_variants(sentence, one=True)
	i = -1
	while i + 1 < len(sentence):
		i += 1

		if get_complex_mapping_key(sentence[i]) in u2j_complex_mapping:
			skip = try_extract_and_record_complex_mapping(sentence, i, u2j_complex_mapping, jmdict, freqs)
			if skip is not None:
				i += skip
				continue

		try_record_simple_mapping(sentence[i], unidic2jmdict_mapping, freqs)

def process_corpus(unidic2jmdict_mapping, u2j_complex_mapping, jmdict):
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
					process_sentence(sentence, unidic2jmdict_mapping, u2j_complex_mapping, jmdict, freqs)
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

def compute_reading(variant):
	is_regex = False
	reading = []
	for l in variant:
		if len(l) >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM + 1:
			reading.append(l[PRON_INDEX + 1])
		else:
			reading.append('.+')
			is_regex = True
	reading = kata_to_hira(''.join(reading))
	if is_regex:
		return regex.compile(reading)
	else:
		return reading

def reading_matches(parsed_reading, dictionary_reading):
	#print(f'reading_matches({parsed_reading}, {dictionary_reading})')
	if type(parsed_reading) == str:
		return parsed_reading == dictionary_reading
	else:
		return parsed_reading.fullmatch(dictionary_reading) is not None

def variant_matches_reading(entry, kanji_index, variant):
	if len(variant) == 1 and len(variant[0]) < NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM + 1:
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
	if len(parse_line) >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM + 1:
		return parse_line[-1]
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
		if len(l) >= NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM + 1:
			l[-1] = int(l[-1])
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
			if any(len(l) < NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM + 1 for l in variant) and (len(variant) > 1 or not all(is_katakana(c) for c in r.text)):
				#print('WARNING: strange reading parse:', r.text)
				pass
			record_complex_mapping(mapping, variant, entry.id, kata_to_hira(r.text))
			mapped_jmdict_ids.add(entry.id)

	del mecab
	return mapping, mapped_jmdict_ids

def compute_freqs():
	jmdict, jindex = dictionary.load_dictionary()

	filename = 'tmp/unidic2jmdict-mapping.pkl'
	if os.path.exists(filename):
		with open(filename, 'rb') as f:
			mapping = pickle.load(f)
			complex_mapping = pickle.load(f)
	else:
		unidic, uindex = load_unidic()
		u2j_pos = match_unidic_jmdict_one2one(jmdict, jindex, unidic, uindex)
		load_additional_pos_mapping(u2j_pos)
		mapping = match_unidic_jmdict_with_refining(jmdict, jindex, unidic, uindex, u2j_pos)
		del unidic, uindex, u2j_pos
		gc.collect()

		mapped_jmdict_ids = get_mapped_jmdict_ids(mapping)
		complex_mapping, new_mapped_jmdict_ids = compute_complex_mapping(jmdict, mapped_jmdict_ids)
		mapped_jmdict_ids.update(new_mapped_jmdict_ids)
		print(len(mapped_jmdict_ids), 'mapped jmdict entries')
		print(sum(1 for entry in jmdict.values() if entry.is_common() and entry.id not in mapped_jmdict_ids), 'unmapped commons')
		for entry in jmdict.values():
			if entry.is_common() and entry.id not in mapped_jmdict_ids:
				print(entry)
				input()
		del mapped_jmdict_ids, new_mapped_jmdict_ids
		gc.collect()

		with open(filename, 'wb') as of:
			pickle.dump(mapping, of)
			pickle.dump(complex_mapping, of)

	del jindex
	gc.collect()

	print(len(mapping), len(complex_mapping))

	freqs = process_corpus(mapping, complex_mapping, jmdict)
	return [(k,v) for k, v in freqs.items() if v >= 77]

def save_freqs(freqs):
	with open('tmp/jmdict-freqs.dat', 'w') as of:
		for k, v in freqs:
			print(k, v, sep='\t', file=of)

def load_freqs():
	res = []
	with open('tmp/jmdict-freqs.dat') as f:
		for l in f:
			k, v = l.strip().split()
			res.append((k, v))
	return res

def compute_freq_order():
	if os.path.exists('tmp/jmdict-freqs.dat'):
		freqs = load_freqs()
	else:
		freqs = compute_freqs()
		save_freqs(freqs)

	freqs.sort(key=lambda p: int(p[1]), reverse=True)
	return {k:i for i, (k, _) in enumerate(freqs)}

__freq_order = compute_freq_order()
def get_frequency(entry):
	return __freq_order.get(entry.id)
