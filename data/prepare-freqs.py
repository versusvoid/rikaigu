#!/usr/bin/env python3

import sys
import os
import subprocess
import lzma
import gzip
import fcntl
from collections import namedtuple
import traceback

from utils import *
import dictionary

extracted_dump = 'tmp/jawiki-text.xz'
if not os.path.exists(extracted_dump):
	wikiextractor = download('https://github.com/versusvoid/wikiextractor/archive/master.tar.gz', 'wikiextractor.tar.gz')
	if not os.path.exists('tmp/wikiextractor-master'):
		subprocess.check_call(["tar", "-xf", wikiextractor, '-C', 'tmp'])

	jawiki_dump = download('https://dumps.wikimedia.org/jawiki/latest/jawiki-latest-pages-articles.xml.bz2',
		'jawiki-articles.xml.bz2')
	print("Stripping wiki markup")
	subprocess.check_call([' | '.join([
		'tmp/wikiextractor-master/WikiExtractor.py -q -o - --no-templates -s --lists tmp/jawiki-articles.xml.bz2',
		'head -n 400000',
		'egrep -v "^<"',
		'xz > tmp/jawiki-text.xz'])], shell=True)

titles_file = download('https://dumps.wikimedia.org/jawiki/latest/jawiki-latest-all-titles-in-ns0.gz',
	'jawiki-article-titles.gz')
article_titles = set()
with gzip.open(titles_file, 'rt') as f:
	for l in f:
		article_titles.add(l.strip())

mecab_no_neolog = None
def mecab_parse_no_neolog(string):
	global mecab_no_neolog
	if mecab_no_neolog is None:
		mecab_no_neolog = subprocess.Popen(['mecab'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
			universal_newlines=True)

	print(string, file=mecab_no_neolog.stdin)
	mecab_no_neolog.stdin.flush()
	total = 0
	res = []
	for l in mecab_no_neolog.stdout:
		res.append(l)
		if l.startswith('EOS'):
			if total == len(string):
				break
		else:
			total += len(l.split('\t')[0])
	return res

counts = {}

def record_sample(sample, of):
	if len(sample) > 0:
		print(*map(lambda w: f'{w.source} {",".join(w.info.form_name)}', sample), sep='\t', file=of)

def mecab_pos_to_jmdict_pos(dkanji, info):
	if info.pos == '助詞':
		return set(['prt'])
	elif info.pos == '助動詞':
		if dkanji == 'ない':
			return set(['adj-i', 'suf'])
		elif dkanji == 'です':
			return set(['exp'])
		else:
			return set(['aux-v'])
	elif info.pos == '接続詞':
		return set(['conj'])
	elif info.pos == '連体詞':
		return set(['adj-pn'])
	elif info.pos == '名詞':
		if info.category1 == '非自立':
			return set(['n-suf'])
		elif info.category1 == '代名詞':
			return set(['pn'])
		elif info.category1 == '接尾' and info.category2 == '特殊':
			return set(['suf'])
	elif info.pos == '動詞':
		res = None
		if info.inflection_type == '一段':
			res = set(['v1'])
		elif info.inflection_type.startswith('サ変'):
			res = set(['vs-i'])
		elif info.inflection_type == '五段・ラ行':
			if dkanji.endswith('ある'):
				res = set(['v5r-i'])
			else:
				res = set(['v5r'])
		elif info.inflection_type == '五段・サ行':
			res = set(['v5s'])

		if res is not None and info.category1 in ('非自立', '接尾'):
			res.add('aux-v')

		if res is not None:
			return res

	raise Exception(f"Don't know how to convert pos '{dkanji} {info}'")

def have_pos(pos, entry):
	for sg in entry.sense_groups:
		if len(pos.intersection(sg.pos)) == len(pos):
			return True

	return False

def have_reading(reading, entry):
	for r in entry.readings:
		if r.text[:len(reading)] == reading:
			return True

	return False

def filter_by_reading(entries, reading):
	longest_common_prefix = 0
	for e in entries:
		for r in e.readings:
			i = longest_common_prefix + 1
			while i <= len(reading) and r.text[:i] == reading[:i]:
				i += 1
			longest_common_prefix = max(longest_common_prefix, i - 1)
	if longest_common_prefix > 0:
		return list(filter(lambda e: have_reading(reading[:longest_common_prefix], e), entries))
	else:
		return entries

MecabInfo = namedtuple('MecabInfo', '''pos, category1, category2, category3,
	inflection_type, form_name, base_form, reading, pronunciation''')
Word = namedtuple('Word', 'source, entry, info')

class Word(object):
	def __init__(self, source, info):
		self.source = source
		self.info = info
		self._entry = None

	@property
	def entry(self):
		if self._entry is None:
			self._resolve()
		return self._entry

	def __str__(self):
		return f'Word({self.source}, {self._entry}, {self.info})'

	def _resolve(self):
		dkanji = self.source
		dreading = None
		if len(self.info.form_name) > 0:
			dkanji = self.info.base_form
		elif kata_to_hira(self.info.reading) != kata_to_hira(dkanji):
			dreading = self.info.reading

		while dkanji[0].isdigit():
			# TODO also slice reading
			dkanji = dkanji[1:]

		try:
			entries = dictionary.find_entry(dkanji, dreading)
		except:
			traceback.print_exc()
			entries = []

		'''
		if len(entries) == 0 and is_katakana(dkanji[0]) and source[0] == info.base_form[0] and not is_katakana(dkanji[-1]):
			j = 1
			while j < len(dkanji) and self.info.base_form[j] == source[j] and is_katakana(dkanji[j]):
				j += 1
			entries = dictionary.find_entry(dkanji[:j], None)
			if len(entries) == 0:
				entries.append(UnknownEntry)
			words.insert(i + 1, (source[j:], info._replace(base_form=info.base_form[j:], reading=info.reading[j:],
				pronunciation=info.pronunciation[j:])))
			source = source[:j]
			info = info._replace(base_form=info.base_form[:j], reading=info.reading[:j],
				pronunciation=info.pronunciation[:j])
		'''

		if len(entries) > 1 and self.info.pos != '*':
			# TODO record matched sense groups
			pos = mecab_pos_to_jmdict_pos(dkanji, self.info)
			entries = list(filter(lambda e: have_pos(pos, e), entries))

		if len(entries) > 1:
			entries = filter_by_reading(entries, kata_to_hira(self.info.reading))

		'''
		if len(entries) != 1 and i + 1 < len(words):
			next_source, next_info = words[i+1]
			if source == 'よう' and info.category1 == '非自立' and info.category2 == '助動詞語幹':
				if next_source == 'な' and next_info.form_name[-1] == '--mecab suffix--':
					source = 'ような'
					entries = dictionary.find_entry(source, None)
					info = MecabInfo('連体詞', '*', '*', '*', '*', [], source, info.reading+next_info.reading,
						info.reading+next_info.reading)
					words.pop(i + 1)
				elif next_source == 'に' and next_info.category1 == '副詞化':
					source = 'ように'
					entries = dictionary.find_entry('様に', source)
					info = MecabInfo('副詞', '*', '*', '*', '*', [], source, info.reading+next_info.reading,
						info.reading+next_info.reading)
					words.pop(i + 1)

		if len(entries) == 0 and i - 1 >= 0:
			prev_source, prev_entry, prev_info = words[i-1]
			if prev_source == 'で' and info.base_form == 'ある' and info.pos == '助動詞':
				words.pop(i)
				i = i - 1
				entries = dictionary.find_entry('である', None)
				source = prev_source + source
				info = info._replace(base_form='である', inflection_type=(info.inflection_type[:-2] + 'デアル'),
					reading=('デ' + info.reading), pronunciation=('デ' + info.pronunciation))

		if len(entries) == 0 and dkanji in article_titles:
			entries.append(UnknownEntry)

		if len(entries) == 0 and recurse and info.category1 == '固有名詞' and any(not is_kanji(c) for c in source):
			other_parse = mecab_parse_no_neolog(source)
			assert len(other_parse) > 1 and other_parse[-1] == 'EOS\n' and other_parse.count('EOS\n') == 1
			if len(other_parse) > 2:
				other_parse = list(map(lambda s: s.strip().split('\t'), other_parse[:-1]))
				transform_sample(other_parse, False)
				words.pop(i)
				for j, w in enumerate(other_parse):
					words.insert(i + j, w)
				source, entry, info = other_parse[0]
				entries.append(entry)
		'''

		if len(entries) != 1:
			raise Exception(f"Don't know how to resolve: {self.source}\n{self.info}\n{entries}")

		self._entry = entries[0]

def load_expressions():
	expressions = {}
	max_len = 0
	with open('data/expressions.dat.in') as f:
		forms = []
		for l in f:
			l = l.strip()
			if l.startswith('#'): continue
			parts = l.split('\t')
			forms.append(parts[0])
			if len(parts) == 1:
				continue

			requirements = {
				"pos": parts[1],
				"after_pos": set(parts[2].split('|')),
				"after_form": set(parts[3].split('|'))
			}
			for form in forms:
				max_len = max(max_len, len(form))
				expressions.setdefault(form, []).append(requirements)
			forms = []

	return max_len, expressions
max_expression_length, known_expressions = load_expressions()

def get_pos(word):
	res = set(word.entry.sense_groups[0].pos).union(*map(lambda sg: sg.pos, word.entry.sense_groups[1:]))
	for pos in res:
		if pos.startswith('v'):
			res.add('v')
			break
	return res

def load_masu_stem_rules():
	rules = {}
	with open('data/deinflect.dat') as f:
		for l in f:
			l = l.strip().split('\t')
			if l[-1] == 'masu stem':
				rules.setdefault(l[0], []).append(l[1:])
	return rules
masu_stem_rules = load_masu_stem_rules()

def check_and_change_if_masu_stem(word):
	if word.info.pos == '名詞':
		masu_stem_verb_variants = masu_stem_rules.get(word.source[-1])
		if masu_stem_verb_variants is None:
			return
		for to, _, pos, _ in masu_stem_verb_variants:
			pos = set(pos.split('|'))
			try:
				entries = dictionary.find_entry(word.source[:-1] + to, kata_to_hira(word.info.reading[:-1]) + to)
			except:
				continue
			if len(entries) == 1:
				word.info = word.info._replace(pos='動詞', form_name=['masu stem'], base_form=(word.source[:-1] + to))

				return

def meets_requirements(word, per_expression_requirements):
	checked_masu_stem = False
	for requirements in per_expression_requirements:
		if 'masu stem' in requirements['after_form'] and not checked_masu_stem:
			check_and_change_if_masu_stem(word)
			checked_masu_stem = True

		#print('Checking requirements', requirements, 'on word', word, sep='\n')
		if ('*' not in requirements['after_pos'] and
				len(requirements['after_pos'].intersection(get_pos(word))) == 0):
			continue

		if ('*' not in requirements['after_form']
				and not ('raw' in requirements['after_form'] and (
					len(word.info.form_name) == 0
					or
					word.info.form_name[-1].startswith('expr=')
					)
				)
				and not (len(word.info.form_name) > 0 and word.info.form_name[-1] in requirements['after_form'])):
			continue

		# TODO record
		return True

	return False

class InflectionSuffix(object):
	default_args = {
		'w1_pos': None, 'w1_category1': None, 'w1_inflection_type': None, 'w1_form_name': None, 'w1_base_form': None,
		'w2_pos': None, 'w2_category1': None, 'w2_inflection_type': None, 'w2_form_name': None, 'w2_source': None,
		'drop_form_names_from_w1': 0, 'additional_form_name': None, 'drop_form_names_from_w2': 0
	}
	def __init__(self, **kwargs):
		for k, v in InflectionSuffix.default_args.items():
			setattr(self, k, kwargs.get(k, v))

	def satisfy(self, w1, w2):
		to_check = [
			(w1.info.pos, self.w1_pos),
			(w1.info.category1, self.w1_category1),
			(w1.info.inflection_type, self.w1_inflection_type),
			(w1.info.base_form, self.w1_base_form),
			(w2.info.pos, self.w2_pos),
			(w2.info.category1, self.w2_category1),
			(w2.info.inflection_type, self.w2_inflection_type),
			(w2.source, self.w2_source),
		]
		for v, gold in to_check:
			if gold is None: continue
			if type(gold) == str:
				if v != gold:
					return False
			elif callable(gold):
				if not gold(v):
					return False
			elif v not in gold:
				return False
		for v, gold in [(w1.info.form_name, self.w1_form_name), (w2.info.form_name, self.w2_form_name)]:
			if gold is None: continue
			if len(v) == 0:
				return False
			if type(gold) == str:
				if v[-1] != gold:
					return False
			elif v[-1] not in gold:
				return False

		return True

	def combine(self, w1, w2):
		form_name = w1.info.form_name # it's okey to reuse list
		form_name = form_name[:len(form_name) - self.drop_form_names_from_w1]
		if self.additional_form_name is not None:
			form_name.append(self.additional_form_name)
		form_name.extend(w2.info.form_name[self.drop_form_names_from_w2:])
		w1.source += w2.source
		w1.info = w1.info._replace(form_name=form_name, reading=(w1.info.reading+w2.info.reading),
			pronunciation=(w1.info.pronunciation+w2.info.pronunciation))

suf2form_name = {
	'ます': InflectionSuffix(w1_pos='動詞', w1_form_name='masu stem',
		w2_pos='助動詞', w2_inflection_type='特殊・マス',
		drop_form_names_from_w1=1, additional_form_name='polite'),

	'ない': InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
		w2_pos='助動詞', w2_inflection_type='特殊・ナイ',
		drop_form_names_from_w1=1, additional_form_name='negative'),
	'ん': InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
		w2_pos='助動詞', w2_inflection_type='不変化型',
		drop_form_names_from_w1=1, additional_form_name='negative'),
	'ぬ': [
		InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
			w2_pos='助動詞', w2_inflection_type='特殊・ヌ', w2_source='ぬ',
			drop_form_names_from_w1=1, additional_form_name='archaic negative'),
		InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
			w2_pos='助動詞', w2_inflection_type='特殊・ヌ', w2_source='ず',
			drop_form_names_from_w1=1, additional_form_name='-zu'),
	],

	'た': [
		InflectionSuffix(w1_pos='動詞', w1_form_name='masu stem',
			w2_pos='助動詞', w2_inflection_type='特殊・タ',
			drop_form_names_from_w1=1, additional_form_name='past'),
		InflectionSuffix(w1_pos='動詞', w1_form_name='past',
			w2_pos='助動詞', w2_inflection_type='特殊・タ'),
	],
	'だ': InflectionSuffix(w1_pos='動詞', w1_form_name='past',
		w2_pos='助動詞', w2_inflection_type='特殊・タ'),

	'たら': InflectionSuffix(w1_pos='動詞', w1_form_name=set(['masu stem', 'past']),
		w2_pos='助動詞', w2_inflection_type='特殊・タ',
		drop_form_names_from_w1=1, additional_form_name='-tara'),
	'だら': InflectionSuffix(w1_pos='動詞', w1_form_name=set(['masu stem', 'past']),
		w2_pos='助動詞', w2_inflection_type='特殊・タ',
		drop_form_names_from_w1=1, additional_form_name='-tara'),

	'て': [
		InflectionSuffix(w1_pos='動詞', w1_form_name='masu stem',
			w2_pos='助詞', w2_category1='接続助詞',
			drop_form_names_from_w1=1, additional_form_name='-te'),
		InflectionSuffix(w1_pos='動詞', w1_form_name='-te',
			w2_pos='助詞', w2_category1='接続助詞'),
	],
	'で': InflectionSuffix(w1_pos='動詞', w1_form_name='past',
		w2_pos='助詞', w2_category1='接続助詞',
		drop_form_names_from_w1=1, additional_form_name='-te'),

	'ば': InflectionSuffix(w1_pos='動詞', w1_form_name='-ba',
		w2_pos='助詞', w2_category1='接続助詞'),

	'られる': InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
		w2_pos='動詞', w2_category1='接尾',
		drop_form_names_from_w1=1, additional_form_name='potential or passive'),
	'れる': [
		InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
			w2_pos='動詞', w2_category1='接尾',
			drop_form_names_from_w1=1, additional_form_name='passive'),
		InflectionSuffix(w1_pos='動詞', w1_form_name='passive',
			w2_pos='動詞', w2_category1='接尾'),
	],

	'させる': InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
		w2_pos='動詞', w2_category1='接尾',
		drop_form_names_from_w1=1, additional_form_name='causative'),
	'せる': InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
		w2_pos='動詞', w2_category1='接尾',
		drop_form_names_from_w1=1, additional_form_name='causative'),
	'す': InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
		w2_pos='動詞', w2_category1='接尾',
		drop_form_names_from_w1=1, additional_form_name='informal causative'),

	'さ': InflectionSuffix(w1_pos='動詞', w1_form_name='masu stem',
		w2_pos='名詞', w2_category1='接尾',
		drop_form_names_from_w1=1, additional_form_name='informal causative'),

	'する': [
		InflectionSuffix(w1_pos='動詞', w1_form_name='informal causative',
			w2_pos='動詞', w2_category1='自立'),
		InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
			w1_inflection_type=(lambda s: s.startswith('五段・')),
			w2_pos='動詞', w2_category1='自立',
			drop_form_names_from_w1=1, additional_form_name='informal causative'),
	],

	'う': [
		InflectionSuffix(w1_pos='動詞', w1_form_name='volitional',
			w2_pos='助動詞', w2_inflection_type='不変化型'),
		InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
			w2_pos='助動詞', w2_inflection_type='不変化型',
			drop_form_names_from_w1=1, additional_form_name='volitional'),
	],

	'たり': [
		InflectionSuffix(w1_pos='動詞', w1_form_name=set(['masu stem', 'past']),
			w2_pos='助詞', w2_category1='並立助詞',
			drop_form_names_from_w1=1, additional_form_name='-tari'),
		InflectionSuffix(w1_pos='動詞', w1_form_name='masu stem',
			w2_pos='助動詞', w2_inflection_type='文語・ナリ',
			drop_form_names_from_w1=1, additional_form_name='-tari'),
	],
	'だり': InflectionSuffix(w1_pos='動詞', w1_form_name=set(['masu stem', 'past']),
		w2_pos='助詞', w2_category1='並立助詞',
		drop_form_names_from_w1=1, additional_form_name='-tari'),
}
def try_join(w1, w2):
	cases = suf2form_name.get(w2.info.base_form)
	if type(cases) == InflectionSuffix:
		if cases.satisfy(w1, w2):
			cases.combine(w1, w2)
			return True
	elif type(cases) == list:
		for case in cases:
			if case.satisfy(w1, w2):
				case.combine(w1, w2)
				return True

	exp = w2.info.base_form
	if exp in known_expressions: # TODO check entry match
		if meets_requirements(w1, known_expressions[exp]):
			# TODO record?
			w1.source += w2.source
			w1.info = w1.info._replace(form_name=(w1.info.form_name + ['expr=' + exp] + w2.info.form_name),
					reading=(w1.info.reading+w2.info.reading),
					pronunciation=(w1.info.pronunciation+w2.info.pronunciation))
			return True

	#if len(w1.info.form_name) == 0:
	#	return False

	raise Exception(f"Don't know if should join\n{w1}\nand\n{w2}")

mecab_form_name2rikaigu_form_name = {
	'*': [],
	'基本形': [],
	'連用デ接続': [],
	'連用形': ['masu stem'],
	'未然レル接続': ['passive'],
	'未然形': ['negative stem'],
	'連用タ接続': ['past'],
	'体言接続': ['--mecab suffix--'],
	'仮定形': ['-ba'],
	'連用テ接続': ['-te'],
	'連用ニ接続': ['whatever'],	#assert source == 'ず'
	'未然ウ接続': ['volitional'],
	'命令ｒｏ': ['imperative'],
	'命令ｉ': [],
}
def try_join_into_expression(words, i):
	source = words[i].source
	reading = words[i].info.reading
	pronunciation = words[i].info.pronunciation
	candidate = words[i].info.base_form
	candidates = set(exp for exp in known_expressions if exp.startswith(candidate))
	j = i
	while j + 1 < len(words) and len(candidate) < max_expression_length:
		new_candidate = candidate + words[j + 1].info.base_form
		new_candidates = set(exp for exp in known_expressions if exp.startswith(new_candidate))
		if len(new_candidates) == 0:
			break
		else:
			j += 1
			source += words[j].source
			reading += words[j].info.reading
			pronunciation += words[j].info.pronunciation
			candidate = new_candidate
			candidates = new_candidates

	if j == i or candidate not in candidates:
		return None

	words[i].source = source
	words[i].info = words[j].info._replace(base_form=candidate,
		reading=reading,
		pronunciation=pronunciation)
	words[i]._entry = None

	for _ in range(i + 1, j + 1):
		words.pop(i + 1)


def transform_sample(words, recurse=True):
	print('--------------------------------')
	print(*words, sep='\n')
	for i in range(len(words)):
		source, info = words[i]
		info = info.split(',')
		if info[6] in ('た', 'だ') and info[4] in ('特殊・タ', '特殊・ダ'):
			info[6] = source
			info[5] = '*'
		form_name = mecab_form_name2rikaigu_form_name.get(info[5])
		if form_name is not None:
			info[5] = form_name[:]
		else:
			if i > 0:
				print("After:", *words[:i], sep='\n')
			print(source, info)
			raise Exception(f"Don't know how to convert mecab's form_name '{info[5]}' to ours")
		words[i] = Word(source, MecabInfo(*info))

	i = 0
	while i < len(words):
		try_join_into_expression(words, i)
		i += 1

	i = 0
	while i < len(words):
		while i > 0:
			try:
				if try_join(words[i-1], words[i]):
					words.pop(i)
					i -= 1
					continue
			except:
				print('After:', *words[:i-1], sep='\n', end='\n\n')
				print(words[i-1], words[i], sep='\n', end='\n\n')
				print('Followed by:', *words[i+1:], sep='\n')
				raise

			break

		i += 1

	print('================================')
	print(*words, sep='\n')

def main():
	dictionary.load_dictionary()
	with open('tmp/raw-corpus.txt', 'w') as of:
		#mecab = subprocess.Popen([f'unxz -c {extracted_dump} | mecab -d /usr/lib/mecab/dic/mecab-ipadic-neologd'],
		#mecab = subprocess.Popen([f'cat data/inflection-samples.dat | mecab -d /usr/lib/mecab/dic/mecab-ipadic-neologd'],
		mecab = subprocess.Popen([f'cat data/inflection-samples3.dat | mecab'],
				shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
		continuous_japanese = []
		for line_no, l in enumerate(mecab.stdout):
			if True:#(line_no + 1) % 10 == 0:
				print(line_no + 1)

			if l.startswith('EOS'):
				transform_sample(continuous_japanese)
				record_sample(continuous_japanese, of)
				continuous_japanese = []
				continue

			source, info = l.strip().split('\t')
			japanese_characters_flags = [is_japanese_character(c) for c in source]
			if not any(japanese_characters_flags):
				transform_sample(continuous_japanese)
				record_sample(continuous_japanese, of)
				continuous_japanese = []
				continue
			continuous_japanese.append((source, info))

main()
raise Exception('Collect sample sentences with all the expressions from expressions.dat and all kind of inflections from inflections.dat and make sure they are parsed like expected than move to Wikipedia')
