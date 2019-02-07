#!/usr/bin/env python3

import os
import subprocess
import shlex
import sys
import pickle
import itertools
import gc
from typing import Tuple, Set, List, DefaultDict
from collections import namedtuple, defaultdict

import MeCab # https://github.com/SamuraiT/mecab-python3

from utils import download, is_katakana, is_kana, kata_to_hira, any, all
import dictionary

FullUnidicLex = namedtuple('FullUnidicLex', '''
	text_form, leftId, rightId, weight,
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
UnidicType = DefaultDict[int, Set[UnidicLex]]
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

def filter_matching_entries(lex, writing, reading, entries):
	for entry in entries:
		if reading == writing:
			condition1 = len(entry.kanjis) == 0
			condition2 = condition1 or any(r.text == lex.orthBase and r.nokanji for r in entry.readings)
			condition3 = condition2 or any(
				any('uk' in s.misc for s in sg.senses)
				for sg in entry.sense_groups
				if not sg.is_archaic()
			)
			if condition3:
				yield entry
		elif (
				any(kata_to_hira(r.text) == reading for r in entry.readings)
				# or # 取り鍋, but it's a strange thing
				# (len(entries) == 1 and len(uindex[writing]) == 1)
				):

			yield entry

def u2j_simple_match(lex, jindex: dictionary.IndexedDictionaryType, uindex: UnidicIndexType):
	writing = kata_to_hira(lex.orthBase)
	reading = kata_to_hira(lex.pronBase)

	yield from filter_matching_entries(lex, writing, reading, jindex.get(writing, ()))

	writing = '御' + writing
	entries = jindex.get(writing)
	if entries is not None:
		yield from filter_matching_entries(lex, writing, 'お' + reading, entries)

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
			return # 65460 -> 65425 stars, but looks interesting for meanwhile

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
			for entry in u2j_simple_match(lex, jindex, uindex):
				jmdict2unidic[entry.id].add(lex.lemma_id)
				unidic2jmdict[lex.lemma_id].add(entry.id)
	del lemma_lexes, lex
	print(f'mappings: j2u: {len(jmdict2unidic)}, u2j: {len(unidic2jmdict)}')
	if DEBUG:
		print(jmdict2unidic)
		print(unidic2jmdict)
		print(*itertools.chain.from_iterable(unidic.values()), sep='\n')
		print(*map(jmdict.__getitem__, jmdict2unidic.keys()), sep='\n')

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
	somehow_mapped_jmdict_ids = set(jmdict2unidic.keys())
	del jmdict2unidic, unidic2jmdict, unidic_pos2jmdict_pos
	gc.collect()
	return res, somehow_mapped_jmdict_ids

def u2j_match_pos_single(entry, lex, u2j_pos):
	for sg in entry.sense_groups:
		if sg.is_archaic():
			continue
		if any(((lex.pos, jpos) in u2j_pos) for jpos in sg.pos):
			return True
	return False

def u2j_match_pos_all(lex, jindex: dictionary.IndexedDictionaryType, uindex: UnidicIndexType, u2j_pos):
	for entry in u2j_simple_match(lex, jindex, uindex):
		if u2j_match_pos_single(entry, lex, u2j_pos):
			yield entry

def find_stars(a2b, b2a):
	stars = []
	for k, vs in a2b.items():
		assert len(vs) > 0
		if all(len(b2a[v]) == 1 for v in vs):
			stars.append(((k,), vs))

	for k, vs in b2a.items():
		if len(vs) == 1: continue
		assert len(vs) > 0
		if all(len(a2b[v]) == 1 for v in vs):
			stars.append((vs, (k,)))
	return stars

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
		return is_lemma_single_cover_for_entry(dict2_node, dict1_node)
	else:
		assert type(dict2_node) == dictionary.Entry and type(dict1_node) == set and type(next(iter(dict1_node))) == UnidicLex
		return is_entry_single_cover_for_lemma(dict2_node, dict1_node)

def find_single_cover(dict1_node, dict2, dict2_keys):
	single_covers = []
	for lemma_id in dict2_keys:
		if is_single_cover(dict2[lemma_id], dict1_node):
			single_covers.append(lemma_id)

	if len(single_covers) == 1:
		return lemma_id

def cut_out_redundunt_mappings_for_fully_covered_nodes(dict1, dict1_to_dict2, dict2, dict2_to_dict1):
	for dict1_key, dict2_keys in dict1_to_dict2.items():
		if len(dict2_keys) == 1:
			continue
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

def match_unidic_jmdict_stars_refining_pos(
		jmdict: dictionary.DictionaryType,
		jindex: dictionary.IndexedDictionaryType,
		unidic: UnidicType,
		uindex: UnidicIndexType,
		u2j_pos: Set[Tuple[UnidicPosType, str]]):

	jmdict2unidic = defaultdict(set)
	unidic2jmdict = defaultdict(set)

	print('pos matching')
	for lemma_lexes in unidic.values():
		for lex in lemma_lexes:
			for entry in u2j_match_pos_all(lex, jindex, uindex, u2j_pos):
				jmdict2unidic[entry.id].add(lex.lemma_id)
				unidic2jmdict[lex.lemma_id].add(entry.id)
	del lex
	print(f'mappings: j2u: {len(jmdict2unidic)}, u2j: {len(unidic2jmdict)}')
	if DEBUG:
		print(jmdict2unidic)
		print(unidic2jmdict)

	cut_out_redundunt_mappings_for_fully_covered_nodes(jmdict, jmdict2unidic, unidic, unidic2jmdict)
	cut_out_redundunt_mappings_for_fully_covered_nodes(unidic, unidic2jmdict, jmdict, jmdict2unidic)

	print("TODO: utilize xref to merge jmdict's 2835613 and 1007130")

	test_jmdict_ids = (1000920,)
	test_unidic_ids = (2547,)
	print(*(jmdict2unidic.get(i) for i in test_jmdict_ids))
	print(*(unidic2jmdict.get(i) for i in test_unidic_ids))

	for uid in set(itertools.chain.from_iterable(jmdict2unidic.get(i, ()) for i in test_jmdict_ids)):
		print(*unidic[uid], sep='\n')
	for jid in set(itertools.chain.from_iterable(unidic2jmdict.get(i, ()) for i in test_unidic_ids)):
		print(jmdict[jid], sep='\n')
	input()

	print('computing stars')
	stars = find_stars(jmdict2unidic, unidic2jmdict)
	print(len(stars), 'stars')
	print(len(set(itertools.chain.from_iterable(map(lambda p: p[0], stars)))), 'jmdict ids')
	print(len(set(itertools.chain.from_iterable(map(lambda p: p[1], stars)))), 'unidic ids')

	del jmdict2unidic#, unidic2jmdict
	return stars, set(unidic2jmdict.keys())

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

def process_token(l, unidic2jmdict_ids, freqs):
	if l.startswith('EOS'):
		return
	properties = l.split('\t')[1].split(',')
	if len(properties) < NUMBER_OF_PROPERTIES_OF_KNOWN_UNIDIC_LEXEM:
		return
	jmdict_id = unidic2jmdict_ids.get(get_unidic_lexem_key(properties))
	if jmdict_id is not None:
		freqs[jmdict_id] = freqs.get(jmdict_id, 0) + 1

def process_corpus(unidic2jmdict_ids):
	extracted_dump = download_dump()
	# with open('tmp/raw-corpus.txt', 'wb') as of:
	mecab = subprocess.Popen([f'unxz -c {extracted_dump} | mecab -d tmp/unidic-cwj-2.3.0'],
	#mecab = subprocess.Popen([f'cat tmp/test.dat | egrep -v "^#" | mecab'],
			shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)

	freqs = {}
	iterator = enumerate(mecab.stdout)
	while True:
		try:
			line_no, l = next(iterator)

			process_token(l, unidic2jmdict_ids, freqs)
			if (line_no + 1) % 1000000 == 0:
				print(line_no + 1)
		except (StopIteration, KeyboardInterrupt):
			break
		except Exception as e:
			import traceback
			print('some error:')
			traceback.print_exc()
			continue

	return freqs

def load_unidic() -> Tuple[UnidicType, UnidicIndexType]:
	download_unidic()

	print('loading unidic')
	res = defaultdict(set)
	index = defaultdict(set)
	# print("\n\tWARNING!!! SKIPPING NAMES, FIXMEPLEASE!\n")
	filename = 'tmp/unidic-cwj-2.3.0/lex.csv'
	if DEBUG:
		filename = 'tmp/test-lex.csv'
	with open(filename) as f:
		for l in f:
			l = FullUnidicLex(*split_lex(l.strip()))
			# if l.pos1 == '名詞' and l.pos2 == '固有名詞':
			# 	continue
			l = UnidicLex((l.pos1, l.pos2, l.pos3, l.pos4), l.orthBase, l.pronBase, int(l.lemma_id))
			res[l.lemma_id].add(l)
			index[kata_to_hira(l.orthBase)].add(l.lemma_id)
			index[kata_to_hira(l.pronBase)].add(l.lemma_id)
			del l

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

DEBUG = False
def compute_freqs():
	jmdict, jindex = dictionary.load_dictionary()
	unidic, uindex = load_unidic()
	u2j_pos, mapped_jmdict_ids = match_unidic_jmdict_one2one(jmdict, jindex, unidic, uindex)
	# load_additional_pos_mapping(u2j_pos)
	# stars, somehow_matched_lemma_ids = match_unidic_jmdict_stars_refining_pos(jmdict, jindex, unidic, uindex, u2j_pos)

	if DEBUG:
		print(stars)
		print(somehow_matched_lemma_ids)
		exit()

	# mapped_jmdict_ids = set(itertools.chain.from_iterable(map(lambda p: p[0], stars)))
	def stupidly_unmapped(entry):
		if all('exp' in sg.pos for sg in entry.sense_groups):
			return True
		if all('conj' in sg.pos for sg in entry.sense_groups):
			return True
		if any(k.text.startswith('御') for k in entry.kanjis):
			return True

		if any(any(k.text.endswith(suf) for suf in ['ます', '様', 'さん', 'ない', 'でも', 'なら']) for k in entry.kanjis):
			return True

		return False

	num_unmapped_commons = 0
	num_commons = 0
	for entry in jmdict.values():
		if entry.is_common():
			num_commons += 1
			if entry.id not in mapped_jmdict_ids and not stupidly_unmapped(entry):
				num_unmapped_commons += 1
				continue
	print(f'unmapped commons: {num_unmapped_commons}/{num_commons}')
	for entry in jmdict.values():
		if entry.id in mapped_jmdict_ids:
			continue
		if entry.is_common() and not stupidly_unmapped(entry):
			# patterns = list(itertools.chain.from_iterable(
				# [('-e', k.text) for k in entry.kanjis] + [('-e', r.text) for r in entry.readings]
			# ))
			# assert len(patterns) > 0
			# command = ['rg', '-F', '-w'] + patterns + ['tmp/unidic-cwj-2.3.0/lex.csv']
			# if subprocess.call(command, stdout=subprocess.PIPE) == 0:
			print('Unmapped common:\n', entry)
			input()

	for lemma_id in somehow_matched_lemma_ids:
		unidic.pop(lemma_id, None)
	import random
	all_lemmas = list(unidic.keys())
	while True:
		lemma = next(iter(unidic[random.choice(all_lemmas)]))
		# lemma = next(iter(unidic[194862]))
		pattern1 = shlex.quote(f'>{lemma.orthBase}<')
		pattern2 = shlex.quote(f'>{lemma.pronBase}<')
		if subprocess.call(f'gunzip -c tmp/JMdict_e.gz | rg -F -q -e {pattern1} -e {pattern2}', shell=True) == 0:
			pattern = shlex.quote(f',{lemma.lemma_id}$')
			os.system(f'rg {pattern} tmp/unidic-cwj-2.3.0/lex.csv')
			input('continue?')

	exit()

	if DEBUG:
		exit()
	freqs = process_corpus(unidic2jmdict_ids)
	return [(k,v) for k, v in freqs.items() if v >= 77]

def save_freqs(freqs):
	with open('tmp/jmdict-freqs.dat', 'w') as of:
		for k, v in freqs.items():
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
		save_freqs(_freq_order)

	freqs.sort(key=lambda p: int(p[1]), reverse=True)
	return {k:i for i, (k, _) in enumerate(freqs)}

__freq_order = compute_freq_order()
def get_frequency(entry):
	return __freq_order.get(entry.id)
