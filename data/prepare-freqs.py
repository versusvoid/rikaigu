#!/usr/bin/env python3

import sys
import os
import subprocess
import lzma
import gzip
import fcntl
from collections import namedtuple, defaultdict
import traceback
import pickle

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

	print('subparsing', string)
	print(string, file=mecab_no_neolog.stdin)
	mecab_no_neolog.stdin.flush()
	total = 0
	res = []
	for l in mecab_no_neolog.stdout:
		if l.startswith('EOS'):
			if total == len(string):
				break
		else:
			source, info = l.split('\t')
			res.append(Word(source, make_mecab_info(source, info)))
			total += len(source)
	return res

counts = defaultdict(int)
num_samples = 0
num_words = 0
def record_sample(sample, of):
	global num_samples
	global num_words

	num_samples += 1
	for chain in sample:
		word = chain

		while word is not None:
			num_words += 1

			if word.previous_link is not None:
				if len(word.previous_link.info.form_name) > 0:
					counts[(word.previous_link.info.form_name[-1], 'expr=' + word.info.base_form)] += 1
				if len(word.info.form_name) > 0:
					counts[('expr=' + word.info.base_form, word.info.form_name[0])] += 1

			if word.entry_keys is not None:
				for key in word.entry_keys:
					counts[('spelling', key)] += 1
				counts[('entry', word.entry.id)] += 1
			elif type(word.entry) == OneOff:
				for key_sources, entry in word.entry.entries:
					for key in key_sources:
						counts[('spelling', key)] += 1
					counts[('entry', entry.id)] += 1

			if len(word.info.form_name) == 0:
				word = word.previous_link
				continue

			if word.info.form_name[-1].startswith('--'):
				word.info.form_name.pop()
			if (word.info.pos == '形容詞' and word.info.form_name[-1] == '-te'
					and word.source[-1] == 'く'):
				word.info.form_name[-1] = 'adv'

			pos = mecab_pos_to_jmdict_pos(word.info.base_form, word.info)
			if 'aux-v' in pos:
				if len(pos) > 1:
					pos.discard('aux-v')
				else:
					input(word)
			pos = pos.pop()

			for i, fn in enumerate(word.info.form_name):
				counts[(pos, fn)] += 1
				counts[(fn)] += 1
				if i + 1 < len(word.info.form_name):
					counts[(pos, fn, word.info.form_name[i + 1])] += 1
					counts[(fn, word.info.form_name[i + 1])] += 1

			word = word.previous_link
	if len(sample) > 0:
		#input('\t.'.join(map(lambda w: f'{w.source} {",".join(w.info.form_name)}', sample)))
		#print(*map(lambda w: f'{w.source} {",".join(w.info.form_name)}', sample), sep='\t', file=of)
		#print(*map(lambda w: f'{w.source} {",".join(w.info.form_name)}', sample), sep='\t')
		pass

def mecab_pos_to_jmdict_pos(dkanji, info):
	if info.pos == '助詞':
		return set(['prt'])
	elif info.pos == '感動詞':
		return set(['int'])
	elif info.pos == '助動詞' and dkanji in ('ない', 'です'):
		if dkanji == 'ない':
			return set(['adj-i', 'suf'])
		elif dkanji == 'です':
			return set(['exp'])
	elif info.pos == '形容詞':
		return set(['adj-i'])
	elif info.pos == '接続詞':
		return set(['conj'])
	elif info.pos == '連体詞':
		return set(['adj-pn'])
	elif info.pos == '副詞':
		return set(['adv'])
	elif info.pos == '接頭詞':
		return set(['pref'])
	elif info.pos == 'フィラー':
		return set(['exp'])
	elif info.pos == '名詞':
		if info.category1 == '非自立':
			return set(['n-suf'])
		elif info.category1 == '代名詞':
			return set(['pn'])
		elif info.category1 == '接尾' and info.category2 in ('特殊', '人名'):
			return set(['suf'])
		else:
			return set(['n'])
	elif info.pos.endswith('動詞'):
		res = None
		if ord(info.inflection_type[0]) in range(ord('a'), ord('z') + 1):
			res = set([info.inflection_type])
		elif info.inflection_type == '一段':
			res = set(['v1'])
		elif info.inflection_type.startswith('サ変'):
			res = set(['vs-i'])
		elif info.inflection_type == '五段・ラ行':
			if dkanji.endswith('ある'):
				res = set(['v5r-i'])
			else:
				res = set(['v5r'])
		elif info.inflection_type == '五段・ラ行アル':
			return set(['v5r-i'])
		elif info.inflection_type == '五段・サ行':
			res = set(['v5s'])
		elif info.inflection_type == '五段・タ行':
			res = set(['v5t'])
		elif info.inflection_type == '五段・マ行':
			res = set(['v5m'])
		elif info.inflection_type == '五段・ワ行促音便':
			return set(['v5u'])
		elif info.inflection_type == '五段・カ行イ音便':
			return set(['v5k'])
		elif info.inflection_type == '五段・ガ行':
			return set(['v5g'])
		elif info.inflection_type.startswith('五段・カ行促音便'):
			return set(['v5k-s'])
		elif info.inflection_type in ('カ変・来ル', 'カ変・クル'):
			return set(['vk'])
		elif info.inflection_type == '五段・バ行':
			return set(['v5b'])
		elif info.inflection_type == '一段・クレル':
			return set(['v1-s'])
		elif info.inflection_type == '一段・得ル':
			return set(['suf'])

		if res is not None and (info.category1 in ('非自立', '接尾') or info.pos == '助動詞'):
			res.add('aux-v')

		if res is not None:
			return res

	raise EntryResolutionException(f"Don't know how to convert pos '{dkanji} {info}'")

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
	for key_sources, e in entries:
		for r in e.readings:
			i = longest_common_prefix + 1
			while i <= len(reading) and r.text[:i] == reading[:i]:
				i += 1
			longest_common_prefix = max(longest_common_prefix, i - 1)
	if longest_common_prefix > 0:
		return list(filter(lambda p: have_reading(reading[:longest_common_prefix], p[1]), entries))
	else:
		return entries

MecabInfo = namedtuple('MecabInfo', '''pos, category1, category2, category3,
	inflection_type, form_name, base_form, reading, pronunciation''')

class Word(object):
	def __init__(self, source, info, entry=None, entry_keys=None, previous_link=None):
		self.source = source
		self.info = info
		self.entry = entry
		self.entry_keys = entry_keys
		self.previous_link = previous_link

	def __str__(self):
		return f'Word({self.source}, {self.entry}, {self.info})'

def try_correct_v5m_informal_causative(word, next_word):
	if (word.info.pos == '名詞' and next_word.info.base_form == 'ます' and next_word.source.startswith('ま')
			and next_word.info.pos.endswith('動詞')):
		try:
			entries = dictionary.find_entry(word.info.base_form + 'む', None)
		except:
			pass
		entries = list(filter(lambda e: any(('v5m' in sg.pos) for sg in e.sense_groups), entries))
		if len(entries) > 0:
			dreading = entries[0].readings[0].text
			dkanji = dreading
			if len(entries[0].kanjis) > 0:
				dkanji = entries[0].kanjis[0].text

			word.source += 'ま'
			word.info = MecabInfo('動詞', '自立', '*', '*', '五段・マ行', ['negative stem'], dkanji, dreading, dreading)

			next_word.source = next_word.source[1:]
			next_word.info = MecabInfo('動詞', '接尾', '*', '*', '五段・サ行', next_word.info.form_name, 'す', 'ス', 'ス')

			return True

	return False

def try_correct_v5r_potential(word, next_word):
	if word.info.pos == '名詞' and next_word.info.pos == '動詞' and next_word.info.base_form == 'れる':
		try:
			entries = dictionary.find_entry(word.info.base_form + 'る', None)
		except:
			pass
		entries = list(filter(lambda e: any(('v5r' in sg.pos or 'v5r-i' in sg.pos) for sg in e.sense_groups), entries))
		if len(entries) > 0:
			dreading = entries[0].readings[0].text
			dkanji = dreading
			if len(entries[0].kanjis) > 0:
				dkanji = entries[0].kanjis[0].text

			word.source += next_word.source
			word.info = MecabInfo('動詞', '自立', '*', '*', '五段・ラ行', ['potential'], dkanji, dreading, dreading)

			next_word.source = None
			return True

	if (word.info.inflection_type == '五段・ラ行'
			and len(word.info.form_name) == 1 and word.info.form_name[0] == '-ba'
			and next_word.info.base_form == 'ます' and next_word.info.inflection_type == '特殊・マス'):
		word.info = word.info._replace(form_name=['potential', 'masu stem'])
		return True

	return False

def try_correct_split_potential(word, next_word):
	if word.info.inflection_type in ('五段・サ行', '五段・ワ行促音便'):
		if len(word.info.form_name) == 1 and word.info.form_name[0] == '-ba':
			if next_word.info.base_form == 'ます' and next_word.info.inflection_type == '特殊・マス':
				word.info.form_name[0] = 'potential'
				word.info.form_name.append('masu stem')
				return True
			if next_word.info.base_form == 'り' and next_word.info.pos == '助動詞':
				word.source += next_word.source
				word.info.form_name[0] = 'potential'
				next_word.source = None
				return True
		elif len(word.info.form_name) == 1 and word.info.form_name[0] == 'imperative' and next_word.info.base_form == 'ない':
			word.info.form_name[0] = 'potential'
			word.info.form_name.append('negative stem')
			return True

	return False

def try_correct_v5g(word, next_word):
	if word.info.pos == '名詞' and word.source.endswith('が'):
		try:
			entries = dictionary.find_entry(word.info.base_form[:-1] + 'ぐ', None)
		except:
			pass
		entries = list(filter(lambda e: any(('v5g' in sg.pos) for sg in e.sense_groups), entries))
		if len(entries) > 0:
			dreading = entries[0].readings[0].text
			dkanji = dreading
			if len(entries[0].kanjis) > 0:
				dkanji = entries[0].kanjis[0].text

			word.info = MecabInfo('動詞', '*', '*', '*', '五段・ガ行', ['negative stem'], dkanji, dreading, dreading)

			# 叫ばさない ('さ', '動詞,接尾,*,*,五段・サ行,未然形,す,サ,サ')
			# 仰がさない ('さ', '動詞,自立,*,*,サ変・スル,未然レル接続,する,サ,サ')
			if next_word.source == 'さ' and next_word.info.base_form == 'する' and next_word.info.form_name == ['passive']:
				next_word.info = MecabInfo('動詞', '接尾', '*', '*', '五段・サ行', ['negative stem'], 'す', 'サ', 'サ')

			return True

	return False

def load_masu_stem_rules():
	rules = {}
	with open('data/deinflect.dat') as f:
		for l in f:
			l = l.strip().split('\t')
			if l[-1] == 'masu stem':
				rules.setdefault(l[0], []).append(l[1:])
	return rules
masu_stem_rules = load_masu_stem_rules()

def try_correct_masu_stem(word):
	if word.info.pos == '名詞':
		masu_stem_verb_variants = masu_stem_rules.get(word.source[-1])
		if masu_stem_verb_variants is None:
			return False
		for to, _, pos, _ in masu_stem_verb_variants:
			pos = set(pos.split('|'))
			try:
				entries = dictionary.find_entry(word.source[:-1] + to, kata_to_hira(word.info.reading[:-1]) + to)
			except:
				continue
			if len(entries) == 1:
				word.info = word.info._replace(pos='動詞', inflection_type=entries[0].sense_groups[0].pos[0],
					form_name=['masu stem'], base_form=(word.source[:-1] + to))

				return True

	return False

def try_correct_verb_form_as_base_form_error(word, pos, inflection_type, form_name, correction_dict):
	for k in correction_dict:
		suffix_length = len(k)
		break
	if (word.info.pos == pos and word.info.inflection_type == inflection_type
			and word.info.base_form[-suffix_length:] in correction_dict):
		to, expected_pos = correction_dict[word.info.base_form[-suffix_length:]]
		dkanji = word.info.base_form[:-suffix_length] + to
		try:
			entries = dictionary.find_entry(dkanji, None)
		except:
			pass
		entries = list(filter(lambda e: any(len(expected_pos.intersection(sg.pos)) > 0 for sg in e.sense_groups),
			entries))
		if len(entries) > 0:
			dreading = entries[0].readings[0].text
			for sg in entries[0].sense_groups:
				for pos in expected_pos.intersection(sg.pos):
					expected_pos = pos
					break
				else:
					continue

				break

			word.info.form_name.insert(0, form_name)
			word.info = word.info._replace(pos='動詞', category1='*', inflection_type=expected_pos, base_form=dkanji)

			return True

	return False


v5_potentials = {
	'べる': ('ぶ', {'v5b'}),
	'げる': ('ぐ', {'v5g'}),
	'ける': ('く', {'v5k', 'v5k-s'}),
	'める': ('む', {'v5m'}),
	'ねる': ('ぬ', {'v5n'}),
	'れる': ('る', {'v5r'}),
	'せる': ('す', {'v5s'}),
	'てる': ('つ', {'v5t'}),
	'える': ('う', {'v5u'}),
}
def try_correct_potential(word):
	return try_correct_verb_form_as_base_form_error(word, '動詞', '一段', 'potential', v5_potentials)

v5_informal_causative = {
	'かす': ('く', {'v5k', 'v5k-s'}),
}
def try_correct_informal_causative(word):
	return try_correct_verb_form_as_base_form_error(word, '動詞', '五段・サ行', 'informal causative', v5_informal_causative)

v_imperative = {
	'ろ': ('る', {'v1'}),
}
def try_correct_imperative(word):
	return try_correct_verb_form_as_base_form_error(word, '名詞', '*', 'imperative', v_imperative)

def try_correct_v5u_s(word, next_word):
	if (word.info.inflection_type == '五段・ワ行促音便' and word.source == word.info.base_form
			and next_word.info.pos in ('助動詞', '助詞') and len(word.info.form_name) == 0):
		if next_word.info.base_form in ('た', 'たら', 'たり'):
			word.info.form_name.append('past')
			return True
		if next_word.info.base_form == 'て':
			word.info.form_name.append('-te')
			return True

	return False

def try_correct_vk_adj_pn(word, next_word):
	if (word.info.base_form == '来る' and word.info.pos == '連体詞' and (
			next_word.info.base_form in suf2form_name
			or
			any(map(lambda e: 'v' in e['after_pos'], known_expressions.get(next_word.info.base_form, ()))))):
		word.info = MecabInfo('動詞', '自立', '*', '*', 'カ変・来ル', word.info.form_name, '来る', 'クル', 'クル')
		return True

	return False

def try_correct_coalescent_expr(word):
	for i in range(len(word.info.base_form)-1, 1, -1):
		exp = word.info.base_form[-i:]
		exprs = known_expressions.get(exp)
		if exprs is None: continue
		separate_parse = mecab_parse_no_neolog(word.source[:len(word.info.base_form) - len(exp)])
		if len(separate_parse) != 1 or not meets_grammatical_requirements(separate_parse[0], exprs):
			continue

		try:
			resolve(separate_parse[0])
		except:
			continue

		join_expr(word, separate_parse[0])
		return True

	return False

def try_correct_vs_s_potential(word, next_word):
	if (word.info.inflection_type == '五段・サ行' and next_word.info.pos == '動詞'
			and next_word.info.base_form in ('える', 'うる')):
		try:
			entries = dictionary.find_entry(word.info.base_form + 'る', None)
		except:
			pass
		entries = list(filter(lambda e: any(('vs-s' in sg.pos) for sg in e.sense_groups), entries))
		if len(entries) > 0:
			dreading = entries[0].readings[0].text
			word.source += next_word.source
			word.info = word.info._replace(inflection_type='vs-s', form_name=['potential'],
					base_form=(word.info.base_form + 'る'), reading=None, pronunciation=None)

			next_word.source = None

			return True

	return False

def try_correct_vs_i_potential(word, next_word):
	if (word.info.pos == '名詞' and word.info.category1 == 'サ変接続'
			and next_word.info.base_form == 'できる' and next_word.info.pos == '動詞'):
		next_word.info.form_name.insert(0, 'potential')
		next_word.info = next_word.info._replace(
			inflection_type='サ変・スル',
			base_form='する'
		)

		return True

	return False

def try_correct_colloquial(word, next_word):
	if (len(word.info.form_name) > 0 and word.info.form_name[-1] in ('-te', 'past')
			and next_word.info.base_form == 'とく' and next_word.info.inflection_type == '五段・カ行イ音便'):
		word.info.form_name[-1] = 'past stem'
		return True

	if (len(word.info.form_name) > 0 and word.info.form_name[-1] in ('-te', 'past')
			and next_word.info.base_form in ('ちゃう', 'じゃう', 'ちまう', 'じまう')
			and next_word.info.inflection_type == '五段・ワ行促音便'):
		word.info.form_name[-1] = 'past stem'

		return True
	if (len(word.info.form_name) > 0 and word.info.form_name[-1] == 'masu stem'
			and next_word.info.base_form == 'てる' and next_word.info.inflection_type == '一段'):
		word.info.form_name[-1] = 'past stem'
		return True

	return False

def try_correct_mecab(word, next_word):
	if try_correct_potential(word):
		return True
	elif try_correct_informal_causative(word):
		return True
	elif try_correct_imperative(word):
		return True
	elif try_correct_masu_stem(word):
		return True
	elif try_correct_coalescent_expr(word):
		return True

	if next_word is None:
		return False

	if try_correct_v5m_informal_causative(word, next_word):
		return True
	elif try_correct_v5r_potential(word, next_word):
		return True
	elif try_correct_split_potential(word, next_word):
		return True
	elif try_correct_v5g(word, next_word):
		return True
	elif try_correct_v5u_s(word, next_word):
		return True
	elif try_correct_vk_adj_pn(word, next_word):
		return True
	elif try_correct_vs_s_potential(word, next_word):
		return True
	elif try_correct_vs_i_potential(word, next_word):
		return True
	elif try_correct_colloquial(word, next_word):
		return True

	return False

class EntryResolutionException(Exception):
	pass

class OneOff(object):
	def __init__(self, entries):
		self.entries = entries

def resolve(word):
	if word.info.inflection_type in ('特殊・ダ', '特殊・タ'):
		return # don't really need to
	if word.info.pos == '名詞' and word.info.category1 == '固有名詞':
		return

	word.entry = None
	word.entry_keys = None

	dkanji = word.source
	dreading = None
	if len(word.info.form_name) > 0:
		dkanji = word.info.base_form
	elif kata_to_hira(word.info.reading) != kata_to_hira(dkanji):
		dreading = word.info.reading

	while dkanji[0].isdigit():
		# TODO also slice reading
		dkanji = dkanji[1:]

	entries = []
	try:
		if len(entries) == 0:
			entries = dictionary.find_entry(dkanji, dreading, with_keys=True)
	except:
		traceback.print_exc()

	'''
	if len(entries) == 0 and is_katakana(dkanji[0]) and source[0] == info.base_form[0] and not is_katakana(dkanji[-1]):
		j = 1
		while j < len(dkanji) and word.info.base_form[j] == source[j] and is_katakana(dkanji[j]):
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

	if len(entries) > 1 and word.info.pos != '*':
		# TODO record matched sense groups
		pos = mecab_pos_to_jmdict_pos(dkanji, word.info)
		new_entries = []
		for key_sources, e in entries:
			if have_pos(pos, e):
				new_entries.append((key_sources, e))

		if len(new_entries) > 0:
			entries = new_entries

	if len(entries) > 1:
		entries = filter_by_reading(entries, kata_to_hira(word.info.reading))

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

	if len(entries) == 0:
		raise EntryResolutionException(f"Don't know how to resolve: {word.source}\n{word.info}\n{entries}")

	if len(entries) == 1:
		word.entry_keys, word.entry = entries[0]
	else:
		word.entry = OneOff(entries)

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
				"after_pos": set(parts[2].split('|')),
				"after_form": set(parts[3].split('|'))
			}
			if len(parts) == 7:
				requirements['form'] = parts[6]
			pos = parts[1]
			if pos.startswith('v'):
				requirements['pos'] = '動詞'
			elif pos == 'adj-i':
				requirements['pos'] = '形容詞'
			elif pos != 'raw':
				requirements['pos'] = '助動詞'

			for form in forms:
				max_len = max(max_len, len(form))
				expressions.setdefault(form, []).append(requirements)
			forms = []

	return max_len, expressions
max_expression_length, known_expressions = load_expressions()

def get_mecab_pos(info):
	if info.pos == '名詞':
		res = ['n']
		if info.category1 == 'サ変接続':
			res.append('vs')
		return res
	elif info.pos.endswith('動詞'):
		return ['v']
	elif info.pos == '形容詞':
		return ['adj-i']
	elif info.pos == '名容詞':
		return ['adj-na']
	else:
		return []

def meets_form_requirements(after_form, form_name):
	return (
		'*' in after_form
		or
		(
			'raw' in after_form
			and
			len(form_name) == 0
		)
		or
		(
			len(form_name) > 0
			and
			form_name[-1] in after_form
		)
	)

def meets_grammatical_requirements(word, per_expression_requirements):
	matched_expressions = []
	for requirements in per_expression_requirements:
		#print('Checking requirements', requirements, 'on word', word, sep='\n')
		if not meets_form_requirements(requirements['after_form'], word.info.form_name):
			#print(word.info.form_name, "doesn't match", requirements['after_form'])
			continue

		if ('*' not in requirements['after_pos'] and
				len(requirements['after_pos'].intersection(get_mecab_pos(word.info))) == 0):
			#print(word.info.pos, "doesn't match", requirements['after_pos'])
			continue

		matched_expressions.append(requirements)

	return matched_expressions

def meets_entry_requirements(word, per_expression_requirements):
	# Nothing to do here. Or is it?
	return per_expression_requirements

class InflectionSuffix(object):
	default_args = {
		'w1_pos': None, 'w1_category1': None, 'w1_inflection_type': None, 'w1_form_name': None, 'w1_base_form': None,
		'w2_pos': None, 'w2_category1': None, 'w2_inflection_type': None, 'w2_form_name': None, 'w2_source': None,
		'drop_form_names_from_w1': 0, 'additional_form_name': None, 'drop_form_names_from_w2': 0,
		'new_pos': None
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
		w1.info = w1.info._replace(pos=(w1.info.pos if self.new_pos is None else self.new_pos),
			form_name=form_name, reading=(w1.info.reading+w2.info.reading),
			pronunciation=(w1.info.pronunciation+w2.info.pronunciation))

suf2form_name = {
	'ない': [
		InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
			#w2_pos='助動詞', w2_inflection_type='特殊・ナイ',
			drop_form_names_from_w1=1, additional_form_name='negative'),
		InflectionSuffix(w1_pos='形容詞', w1_form_name='-te',
			w2_pos='助動詞', w2_inflection_type='特殊・ナイ',
			drop_form_names_from_w1=1, additional_form_name='negative'),
	],
	'ん': InflectionSuffix(w1_pos=set(['動詞', '助動詞']), w1_form_name='negative stem',
		w2_pos='助動詞', w2_inflection_type='不変化型',
		drop_form_names_from_w1=1, additional_form_name='casual negative'),
	'ぬ': [
		InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
			w2_pos='助動詞', w2_inflection_type='特殊・ヌ', w2_source='ぬ',
			drop_form_names_from_w1=1, additional_form_name='archaic negative'),
		InflectionSuffix(w1_pos='動詞', w1_form_name='negative stem',
			w2_pos='助動詞', w2_inflection_type='特殊・ヌ', w2_source='ず',
			drop_form_names_from_w1=1, additional_form_name='-zu'),
	],
	'ある': InflectionSuffix(w1_pos='形容詞', w1_form_name='-te',
		w2_pos='動詞', w2_form_name='masu stem',
		drop_form_names_from_w1=1, additional_form_name='polite',
		new_pos='動詞'),


	'た': [
		InflectionSuffix(w1_pos=set(['動詞', '助動詞']), w1_form_name='masu stem',
			w2_pos='助動詞', w2_inflection_type='特殊・タ',
			drop_form_names_from_w1=1, additional_form_name='past'),
		InflectionSuffix(w1_pos=set(['動詞', '助動詞', '形容詞']), w1_form_name='past',
			w2_pos='助動詞', w2_inflection_type='特殊・タ'),
	],
	'だ': InflectionSuffix(w1_pos='動詞', w1_form_name='past',
		w2_pos='助動詞', w2_inflection_type='特殊・タ'),

	'たら': InflectionSuffix(w1_pos=set(['動詞', '助動詞']), w1_form_name=set(['masu stem', 'past']),
		w2_pos='助動詞', w2_inflection_type='特殊・タ',
		drop_form_names_from_w1=1, additional_form_name='-tara'),
	'だら': InflectionSuffix(w1_pos='動詞', w1_form_name=set(['masu stem', 'past']),
		w2_pos='助動詞', w2_inflection_type='特殊・タ',
		drop_form_names_from_w1=1, additional_form_name='-tara'),

	'て': [
		InflectionSuffix(w1_pos='動詞', w1_form_name='masu stem',
			w2_pos='助詞', w2_category1='接続助詞',
			drop_form_names_from_w1=1, additional_form_name='-te'),
		InflectionSuffix(
			w1_pos='動詞', w1_inflection_type=set(['五段・カ行イ音便', '五段・カ行促音便', '五段・タ行', '五段・ワ行促音便', '五段・ラ行特殊', '五段・ラ行']), w1_form_name='past',
			w2_pos='助詞', w2_category1='接続助詞',
			drop_form_names_from_w1=1, additional_form_name='-te'),
		InflectionSuffix(w1_pos=set(['動詞', '助動詞', '形容詞']), w1_form_name='-te',
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
	'うる': InflectionSuffix(w1_pos='動詞', w1_form_name='masu stem',
		w2_pos='動詞', w2_category1='非自立',
		drop_form_names_from_w1=1, additional_form_name='potential'),
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
	'せる':	InflectionSuffix(w1_pos='動詞', w1_form_name=set(['negative stem', 'passive']),
		w2_pos='動詞', w2_category1='接尾',
		drop_form_names_from_w1=1, additional_form_name='causative'),
	'す': InflectionSuffix(w1_pos='動詞', w1_form_name=set(['negative stem', 'passive']),
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
		InflectionSuffix(w1_pos=set(['動詞', '助動詞']), w1_form_name='negative stem',
			w2_pos='助動詞', w2_inflection_type='不変化型',
			drop_form_names_from_w1=1, additional_form_name='volitional'),
	],

	'たり': [
		InflectionSuffix(w1_pos='動詞', w1_form_name=set(['masu stem', 'past']),
			w2_pos='助詞', w2_category1='並立助詞',
			drop_form_names_from_w1=1, additional_form_name='-tari'),
		InflectionSuffix(w1_pos=set(['動詞', '助動詞']), w1_form_name='masu stem',
			w2_pos='助動詞', w2_inflection_type='文語・ナリ',
			drop_form_names_from_w1=1, additional_form_name='-tari'),
	],
	'だり': InflectionSuffix(w1_pos='動詞', w1_form_name=set(['masu stem', 'past']),
		w2_pos='助詞', w2_category1='並立助詞',
		drop_form_names_from_w1=1, additional_form_name='-tari'),

	'さ': InflectionSuffix(w1_pos='形容詞', w1_form_name='adjective stem',
		w2_pos='名詞', w2_category1='接尾',
		drop_form_names_from_w1=1, additional_form_name='noun'),

}
class JoinException(Exception):
	pass

def join_expr(w1, w2):
	w1.previous_link = Word(w1.source, w1.info, w1.entry, w1.entry_keys, w1.previous_link)
	w1.source = w2.source
	w1.info = w2.info
	w1.entry = w2.entry
	w1.entry_keys = w2.entry_keys

def try_join(w1, w2):
	if w1.info.inflection_type in ('特殊・ダ', '特殊・タ') and w2.info.inflection_type in ('特殊・ダ', '特殊・タ'):
		w1.source += w2.source
		w1.info = w1.info._replace(base_form=w1.source, reading=(w1.info.reading + w2.info.reading),
			pronunciation=(w1.info.pronunciation + w2.info.pronunciation))
		return True

	cases = suf2form_name.get(w2.info.base_form)
	if type(cases) == InflectionSuffix:
		if cases.satisfy(w1, w2):
			resolve(w1)
			cases.combine(w1, w2)
			return True
	elif type(cases) == list:
		for case in cases:
			if case.satisfy(w1, w2):
				resolve(w1)
				case.combine(w1, w2)
				return True

	exp = w2.info.base_form
	if exp not in known_expressions and len(w2.source) >= 3 and w2.source in known_expressions:
		exp = w2.source
	if exp in known_expressions and w1.info.pos != '助詞': # TODO check entry match
		expressions = meets_grammatical_requirements(w1, known_expressions[exp])
		if len(expressions) > 0:
			resolve(w1)
			expressions = meets_entry_requirements(w1, expressions)
			if len(expressions) > 0:
				join_expr(w1, w2)
				if 'form' in expressions[0] and (len(w1.info.form_name) == 0 or w1.info.form_name[-1] != expressions[0]['form']):
					w1.info.form_name.append(expressions[0]['form'])
				return True

	if len(w1.info.form_name) > 0 and w1.info.form_name[-1] == 'masu stem' and w2.info.pos.endswith('動詞'):
		combined = w1.source + w2.info.base_form
		pos = mecab_pos_to_jmdict_pos(combined, w2.info)
		entries = []
		for entry in dictionary.find_entry(combined, None):
			if have_pos(pos, entry):
				entries.append(entries)
		if len(entries) > 0:
			w1.info = w2.info._replace(base_form=w1.source+w2.info.base_form)
			w1.source += w2.source
			w1.entry = entries[0] if len(entries) == 1 else OneOff(entities)
			return True

	resolve(w1)
	resolve(w2)

	if len(w1.info.form_name) == 0 or w2.info.pos in ('助詞',):
		return False

	raise JoinException(f"Don't know if should join\n{w1}\nand\n{w2}")

def try_join_with_mecab_correction(w1, w2):
	try:
		return try_join(w1, w2)
	except (EntryResolutionException, JoinException):
		if not try_correct_mecab(w1, w2):
			#raise
			return False

	if w2.source is None: # was joined in try_correct_mecab
		return True

	try:
		return try_join(w1, w2)
	except  (EntryResolutionException, JoinException):
		#raise
		return False

mecab_form_name2rikaigu_form_name = {
	'*': [],
	'基本形': [],
	'連用デ接続': [],
	'連用形': ['masu stem'],
	'未然レル接続': ['passive'],
	'未然形': ['negative stem'],
	'未然ヌ接続': ['negative stem'],
	'連用タ接続': ['past'],
	'体言接続': ['--mecab suffix--'],
	'仮定形': ['-ba'],
	'連用テ接続': ['-te'],
	'連用ニ接続': [],	#assert source == 'ず'
	'未然ウ接続': ['volitional'],
	'命令ｒｏ': ['imperative'],
	'命令ｅ': ['imperative'],
	'命令ｙｏ': ['imperative'],
	'命令ｉ': [],
	'文語基本形': [],
	'ガル接続': ['adjective stem'],
	'体言接続特殊２': ['--non existent--'],
	'仮定縮約１': [],
}

def filter_expressions(prefix, previous_word_form_name):
	for exp, infos in known_expressions.items():
		if not exp.startswith(prefix):
			continue

		for info in infos:
			if (all(form_name.endswith('stem') for form_name in info['after_form'])
					and previous_word_form_name not in info):
				continue

			yield exp
			break


def try_join_into_expression(words, i):
	source = words[i].source
	reading = words[i].info.reading
	previous_word_form_name = None
	if i > 0 and len(words[i - 1].info.form_name) > 0:
		previous_word_form_name = words[i - 1].info.form_name[-1]
	pronunciation = words[i].info.pronunciation
	candidate = words[i].info.base_form
	candidates = set(filter_expressions(candidate, previous_word_form_name))
	if len(candidates) == 0 and candidate != words[i].source:
		candidate = words[i].source
		candidates = set(filter_expressions(candidate, previous_word_form_name))

	j = i
	while j + 1 < len(words) and len(candidate) < max_expression_length:
		new_candidate = candidate + words[j + 1].info.base_form
		new_candidates = set(exp for exp in candidates if exp.startswith(new_candidate))
		if len(new_candidates) == 0:
			new_candidate = candidate + words[j + 1].source
			new_candidates = set(exp for exp in candidates if exp.startswith(new_candidate))

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
	words[i].entry = None

	for _ in range(i + 1, j + 1):
		words.pop(i + 1)

def make_mecab_info(source, info):
	info = info.split(',')
	while len(info) < 9:
		info.append('*')
	if info[6] in ('た', 'だ') and info[4] in ('特殊・タ', '特殊・ダ'):
		info[6] = source
		info[5] = '*'
	form_name = mecab_form_name2rikaigu_form_name.get(info[5])
	if form_name is not None:
		info[5] = form_name[:]
	else:
		info[5] = [info[5]]
		#print(source, info)
		#raise Exception(f"Don't know how to convert mecab's form_name '{info[5]}' to ours")

	return MecabInfo(*info)

def transform_sample(words, recurse=True):
	#print('--------------------------------')
	#print(*words, sep='\n')
	for i in range(len(words)):
		source, info = words[i]
		words[i] = Word(source, make_mecab_info(source, info))

	i = 0
	while i < len(words):
		try_join_into_expression(words, i)
		i += 1

	#print(*words, sep='\n')

	i = 0
	while i + 1 < len(words):
		try:
			if try_join_with_mecab_correction(words[i], words[i+1]):
				words.pop(i + 1)
			else:
				i += 1
		except Exception as e:
			print('After:', *words[:i-1], sep='\n', end='\n\n')
			print(words[i-1], words[i], sep='\n', end='\n\n')
			print('Followed by:', *words[i+1:], sep='\n')
			traceback.print_exc()
			if type(e) != JoinException or len(input('Continue? [Y]: ').strip()) > 0:
				raise
			else:
				i += 1

	i = -1
	while i + 1 < len(words):
		i += 1
		w = words[i]
		try:
			resolve(w)
			continue
		except:
			pass

		try_correct_mecab(w, words[i+1] if i+1 < len(words) else None)
		if i+1 < len(words) and words[i+1].source is None:
			words.pop(i+1)
		try:
			resolve(w)
		except:
			if w.info.pos != '名詞':
				print("Can't resolve", w)

	#print('================================')
	#print(*words, sep='\n')

def main():
	dictionary.load_dictionary()
	with open('tmp/raw-corpus.txt', 'wb') as of:
		mecab = subprocess.Popen([f'unxz -c {extracted_dump} | mecab -d /usr/lib/mecab/dic/mecab-ipadic-neologd'],
		#mecab = subprocess.Popen([f'cat tmp/test.dat | egrep -v "^#" | mecab'],
				shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
		continuous_japanese = []
		for line_no, l in enumerate(mecab.stdout):
			if num_words >= 10**5:
				break
			if (line_no + 1) % 2:#000 == 0:
				print(line_no + 1)

			if l.startswith('EOS'):
				transform_sample(continuous_japanese)
				record_sample(continuous_japanese, of)
				continuous_japanese = []
				continue

			if '\t' not in l:
				raise Exception(l)
			source, info = l.strip('\n').split('\t')
			japanese_characters_flags = [is_japanese_character(c) for c in source]
			if not any(japanese_characters_flags):
				transform_sample(continuous_japanese)
				record_sample(continuous_japanese, of)
				continuous_japanese = []
				continue
			continuous_japanese.append((source, info))

		pickle.dump(counts, of)
		#for k, v in counts.items():
			#print(k, '->', v, file=of)
main()
