#!/usr/bin/env python3

import dictionary
import os
import subprocess
import sys
import pickle
import itertools
import MeCab # https://github.com/SamuraiT/mecab-python3
from collections import namedtuple
from utils import download, is_katakana, is_kana, kata_to_hira, any, all

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
			'head -n 400000',
			'egrep -v "^<"',
			'xz > tmp/jawiki-text.xz'])], shell=True)

	return extracted_dump

def download_unidic():
	files = ['char.bin', 'dicrc', 'matrix.bin', 'sys.dic', 'unk.dic', 'lex.csv']
	if all(map(lambda fn: os.path.exists('tmp/unidic-cwj-2.3.0/' + fn), files)):
		return
	print("Downloading unidic...")
	subprocess.check_call(f'''
		curl https://unidic.ninjal.ac.jp/unidic_archive/cwj/2.3.0/unidic-cwj-2.3.0.zip
		| bsdtar -xv -C tmp f- unidic-cwj-2.3.0/{{{','.join(files)}}}
		''',
		shell=True, stderr=subprocess.PIPE, universal_newlines=True)

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

def match_variants(all_variants, all_readings, jmdict_pos, entry, ask_for_pos_match):
	for variant in all_variants:
		variant_props = variant.split('\t')[1].split(',')
		assert len(variant_props) >= 28

		if all_readings is not None:
			unidic_readings = (
				variant_props[11],
				variant_props[9],
				variant_props[6],
			)
			if all(lambda r: kata_to_hira(r) not in all_readings, unidic_readings):
				continue

		unidic_pos = variant_props[:4]
		if not match_pos(jmdict_pos, unidic_pos, ask_for_pos_match, variant, entry):
			continue
		# for magic numbers see `dicrc` file from unidic
		orthBase = variant_props[10]
		pronBase = variant_props[11]
		# -1 'cos some fields in unidic may contain commas in them
		# and mecab does not print them in unambiguous way (using quotes like in unidic/lex.csv),
		# so lemma_id may be at position 28, 29 or 30, but it's always last
		lemma_id = int(variant_props[-1])

		return (orthBase, pronBase, lemma_id)

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
		if l.startswith(unsplit_parse_prefix) and l.count(',') >= 28:
			all_variants.append(l.strip())

	res = match_variants(all_variants, all_readings, jmdict_pos, entry, ask_for_pos_match=False)
	if res is None:
		return match_variants(all_variants, all_readings, jmdict_pos, entry, ask_for_pos_match=True)
	else:
		return res

def match_unidic_ids_with_jmdict():
	download_unidic()
	mecab = MeCab.Tagger('-d tmp/unidic-cwj-2.3.0')

	load_unidic2jmdict_pos()

	seen_entries = set()
	unidic2jmdict_id_mapping = {}

	skip = 0
	if os.path.exists('tmp/u2j.skip'):
		with open('tmp/u2j.skip') as f:
			skip = int(f.read() or 0)
	skip_f = open('tmp/u2j.skip', 'w')
	print('skip:', skip)

	# TODO parse directly from JMdict.xml and utilize all the meta-info for matching
	# (lsource, misc, maybe even s_inf)
	# TODO 2 collaborative filtering: other lexes for same lemma (other readings, writings)
	# help each other filter out impossible candidates
	iterator = itertools.islice(
		enumerate(itertools.chain.from_iterable(dictionary._dictionary.values())),
		skip, None
	)
	for entry_index, (_, entry) in iterator:
		skip_f.flush()
		skip_f.seek(0)
		skip_f.write(str(entry_index))

		if entry.id in seen_entries: continue
		seen_entries.add(entry.id)
		if len(seen_entries) % 10000 == 0:
			print(f'Processing {len(seen_entries)} entry #{entry.id}')

		archaic = False
		usually_kana = set()
		for sg in entry.sense_groups:
			for s in sg.senses:
				archaic = archaic or 'arch' in s.misc
				if 'uk' in s.misc:
					if s.reading_restriction != ():
						usually_kana.update(s.reading_restriction)
					else:
						usually_kana.update(range(0, len(entry.readings)))
		if archaic: continue

		pos = set()
		pos.update(*map(lambda sg: sg.pos, entry.sense_groups))

		all_readings = set()
		for i, r in enumerate(entry.readings):
			all_readings.add(kata_to_hira(r.text))
			if is_katakana(r.text[0]) or i in usually_kana or len(entry.kanjis) == 0:
				try:
					unidic_id = synthesize_mapping(r.text, mecab, pos, entry)
				except KeyError:
					print(f'Entry at position #{entry_index}')
					raise
				if unidic_id is not None:
					unidic2jmdict_id_mapping.setdefault(unidic_id, entry.id)

		for k in entry.kanjis:
			try:
				unidic_id = synthesize_mapping(k.text, mecab, pos, entry, all_readings)
			except KeyError:
				print(f'Entry at position #{entry_index}')
				raise
			if unidic_id is not None:
				unidic2jmdict_id_mapping.setdefault(unidic_id, entry.id)

	print("That's all, folks!")
	del mecab

	return unidic2jmdict_id_mapping

def process_token(l, unidic2jmdict_ids):
	raise NotImplementedError()

def process_corpus(unidic2jmdict_ids):
	extracted_dump = download_dump()
	# with open('tmp/raw-corpus.txt', 'wb') as of:
	mecab = subprocess.Popen([f'unxz -c {extracted_dump} | mecab -d tmp/unidic-cwj-2.3.0'],
	#mecab = subprocess.Popen([f'cat tmp/test.dat | egrep -v "^#" | mecab'],
			shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
	for line_no, l in enumerate(mecab.stdout):
		process_token(l, unidic2jmdict_ids)
		if (line_no + 1) % 2000 == 0:
			print(line_no + 1)

def main():
	dictionary.load_dictionary()
	unidic2jmdict_ids = match_unidic_ids_with_jmdict()

	process_corpus(unidic2jmdict_ids)

main()
