#!/usr/bin/env python3

import urllib.request
import subprocess
import os
import random
import sys
import re
import json
import traceback
import functools
import pickle
import xml.etree.ElementTree as ET
from collections import namedtuple
from enum import Enum
from utils import kata_to_hira
import dictionary
import corpus

def error(*args):
	print('\033[31m', end='', file=sys.stderr)
	print(*args, end='', file=sys.stderr)
	print('\033[0m', file=sys.stderr)

Deinflection = namedtuple('Deinflection', 'to, source_type, target_type, reason')
deinflection_rules = {}
all_deinflection_types = set()
max_deinflection_len = 0
for filename in ('data/deinflect.dat', 'data/tanaka-deinflect.dat'):
	with open(filename) as f:
		for l in f:
			l = l.strip().split('\t')
			if len(l) == 1 or l[0][0] == '#': continue
			d = Deinflection(l[1], set(l[2].split('|')), set(l[3].split('|')), l[4])
			max_deinflection_len = max(max_deinflection_len, len(l[0]))
			all_deinflection_types.update(d.source_type)
			deinflection_rules.setdefault(l[0], []).append(d)
		del l

def deinflect(w, targets=None):
	l = [(w, all_deinflection_types, [])]
	if w[0] in ['お', 'ご'] and len(w) > 1:
		l.append((w[1:], all_deinflection_types, []))
		#l.append((w[1:], all_deinflection_types, ['honorific']))
	seen = set([w])
	res = {}
	i = -1
	while i + 1 < len(l):
		i += 1
		curr_w, wtype, reasons_chain = l[i]
		if targets is None or curr_w in targets or kata_to_hira(curr_w) in targets:
			for t in wtype:
				res.setdefault(t, []).append((curr_w, reasons_chain))
			if targets is not None:
				continue

		for j in range(min(len(curr_w), max_deinflection_len), 0, -1):
			suffix_deinflection_rules = deinflection_rules.get(curr_w[-j:])
			if suffix_deinflection_rules is None: continue

			for d in suffix_deinflection_rules:
				if len(d.source_type.intersection(wtype)) == 0: continue
				new_w = curr_w[:-j] + d.to
				if new_w in seen: continue
				seen.add(new_w)
				#print('replacing', curr_w[-j:], 'with', d.to, 'due', d.reason)
				l.append((new_w, d.target_type, reasons_chain[:] + [d.reason]))

	return res

assert deinflect('して', ['する']) == {'vs-i': [('する', ['-te'])], 'vs-s': [('する', ['-te'])]}, deinflect('して', ['する'])
assert deinflect('戻り', {'戻る', 'もどる'}) == {'v5r': [('戻る', ['masu stem'])], 'v5r-i': [('戻る', ['masu stem'])]}

def deinflect_stems(w, targets):
	'''
	if w + 'る' in targets:
		return {
			'v1': set(['masu stem']),
			'v1-s': set(['masu stem']),
			'vk': set(['masu stem']),
			}
	'''
	res = {}
	if w + 'い' in targets:
		res['adj-i'] = set(['adjective stem'])
	for p, reasons in deinflect(w + 'ない', targets).items():
		if reasons[0][1] == ['negative']:
			res.setdefault(p, set()).add('negative stem')
	for p, reasons in deinflect(w + 'ば', targets).items():
		if reasons[0][1] == ['-ba']:
			res.setdefault(p, set()).add('provisional stem')

	return res

aux_pos =  set([
	'aux-v',
	'aux-adj',
	'aux',
# looks like we also need `suf`
	])

class ExpressionType(Enum):
	AUX = 1
	S_INF_EXP = 2
	PURE_EXP = 3

all_expressions = []

Expression = namedtuple('Expression', 'entry, base_forms, etype, sense_group_indices, elem, seen_forms')
pure_expressions = {}
# TODO sometimes s_inf is contained inside <gloss>
s_inf_regex = re.compile(r'\b(after|follows|attaches)\b.*?\b(form|stem|noun)s?\b', re.IGNORECASE)
def record_entry(entry, base_forms, elem):
	if entry.readings[0].text.endswith('だ') or entry.readings[0].text.endswith('です'):
		return

	sense_group_indices = []
	etype = None
	for i, sense_group in enumerate(entry.sense_groups):
		if 'arch' in sense_group.senses[0].misc:
			continue

		if len(aux_pos.intersection(sense_group.pos)) > 0:
			if etype != ExpressionType.AUX:
				etype = ExpressionType.AUX
				sense_group_indices.clear()
			sense_group_indices.append(i)
		if etype == ExpressionType.AUX:
			continue

		if 'exp' in sense_group.pos:
			for j, sense in enumerate(sense_group.senses):
				if sense.s_inf is None:
					continue
				if s_inf_regex.search(sense.s_inf) is None:
					continue
				if etype != ExpressionType.S_INF_EXP:
					etype = ExpressionType.S_INF_EXP
					sense_group_indices.clear()
				sense_group_indices.append((i, j))
		if etype == ExpressionType.S_INF_EXP:
			continue

		if i > 0 and etype is None:
			continue

		if len(sense_group.pos) == 1 and 'exp' in sense_group.pos:
			etype = ExpressionType.PURE_EXP
		else:
			etype = None

	if etype is None:
		return
	e = Expression(entry, base_forms, etype, sense_group_indices, ET.tostringlist(elem, encoding='unicode'), {})
	all_expressions.append(e)

	if e.etype == ExpressionType.PURE_EXP:
		keys = entry.readings if len(entry.kanjis) == 0 else entry.kanjis
		for key in keys:
			pure_expressions.setdefault(key.text, []).append(e)

def fullfill_pure_expressions():
	for expressions in list(pure_expressions.values()):
		for e in expressions:
			for r in e.entry.readings:
				if r.text not in pure_expressions:
					pure_expressions[r.text] = [e]

find_entry = functools.partial(dictionary.find_entry, d=pure_expressions)

def record_expression_form(expression, word):
	if word.form in expression.base_forms or kata_to_hira(word.form) in expression.base_forms:
		return

	deinflections = deinflect(word.form, expression.base_forms)
	for p, reasons in deinflections.items():
		for form, _ in reasons:
			expression.seen_forms.setdefault(form, set()).add(p)

	if len(deinflections) == 0:
		if word.dkanji == '無きゃいけない':
			word = word._replace(dkanji='無くてはいけない')
			record_expression_form(find_entry(word.dkanji, word.dreading)[0], word)
		else:
			error('Unknown inflection:', word)

def infer_from_corpus():
	for _, words in corpus.corpus_reader():
		for word in words:
			for e in find_entry(word.dkanji, word.dreading):
				record_expression_form(e, word)

s_inf_mapping = {
	}
for s_inf in [
		'after masu stem or adj-stem',
		'often used after adjective stems or the -masu stems of verbs',
		'after the root of an -i adjective or the -masu stem of a verb']:

	s_inf_mapping[s_inf] = {
			'after_pos': set(['v', 'adj-i']),
			'after_form': set(['masu stem', 'adjective stem'])
		}

for s_inf in [
		'masu stem',
		'after -masu stem of verb',
		'after -masu base of verb',
		'after a -masu stem',
		'after a -masu stem, esp. of a suru verb',
		'after the -masu stem of a verb',
		'after the -masu stem of a verb, often in the negative',
		'after the -masu stem of a verb, sometimes as っぱぐれる',
		"after the ren'youkei form of a verb",
		"after the ren'yōkei form of a verb",
		"as …たり…たり, after the ren'youkei forms of multiple verbs",
		"esp. 煩う, after the -masu stem of a verb",
		"imperative form often used after the -masu stem of a verb",
		'after the -masu stem of a humble verb to increase the level of humility',
		'usu. used after -masu stem of verb']:

	s_inf_mapping[s_inf] = {
			'after_pos': set('v'),
			'after_form': set(['masu stem'])
		}

for s_inf in [
		'negative stem',
		'after a -nai stem',
		'after a verb in negative form as 〜ずにはいられない、〜ないではいられない, etc.',
		'after neg. stem of verb',
		'after neg. verb stem',
		'after the -nai stem of a verb',
		'after the -nai stem of a verb, usu. accompanied by まい, esp. as 〜ざあなるまい',
		'after the -nai stem of a verb; ずは is now pronounced ずわ',
		'after the -nai stem of a verb, usu. as 〜も...ばこそ, 〜など...ばこそ']:

	s_inf_mapping[s_inf] = {
			'after_pos': set('v'),
			'after_form': set(['negative stem'])
		}

for s_inf in [
		'after the -te form of a verb',
		'after the -te form of a verb, indicates completion (and sometimes reluctance, accidentality, regret, etc.)',
		'after the -te form of a verb, indicates completion (and sometimes reluctance, regret, etc.)',
		'after the -te form of a verb, punning form of ちょうだい',
		'after the -te form of a verb, the い is sometimes dropped',
		'after 〜て／〜で form',
		'after て form, slightly pompous',
		'also used after -te forms',
		'follows a verb in "-te" form',
		'after a -te form, or the particle "de"']:

	s_inf_mapping[s_inf] = {
			'after_pos': set('v'),
			'after_form': set(['-te'])
		}

for s_inf in [
		'provisional stem',
		'after the -ba stem of a verb']:

	s_inf_mapping[s_inf] = {
			'after_pos': set('v'),
			'after_form': set(['provisional stem'])
		}

for s_inf in [
		'after the -ta form of a verb',
		'after the past tense form of a verb']:

	s_inf_mapping[s_inf] = {
			'after_pos': set('v'),
			'after_form': set(['past'])
		}


for s_inf in [
		'after a noun',
		'after a noun indicating a person',
		'after a noun, etc.',
		'after adjectival noun. e.g. 退屈極まる話',
		'after noun',
		'after a noun, usu. as 〜たる者, etc.']:

	s_inf_mapping[s_inf] = {
			'after_pos': set(['n']),
			'after_form': set('*')
		}

for s_inf in [
		'after plain form of verb',
		'after dictionary form verb',
		'after the dictionary form of verb',
		'after the dictionary form of a verb',
		# I don't know what `monosyllable` stands here for
		'after a monosyllable imperfective form verb',
		'attaches to the imperfective form',
		'attaches to the imperfective form; from ざり + べし']:

	s_inf_mapping[s_inf] = {
			'after_pos': set('v'),
			'after_form': set(['dict'])
		}

for s_inf in [
		'after a volitional form',
		'after the volitional form of verb']:

	s_inf_mapping[s_inf] = {
			'after_pos': set('v'),
			'after_form': set(['volitional'])
		}

s_inf_mapping['after the 〜ず negative form of a verb'] = {
		'after_pos': set('v'),
		'after_form': set(['-zu'])
	}

s_inf_mapping['after a noun or the -masu stem of a verb; also ったい'] = {
		'after_pos': set(['v', 'n']),
		'after_form': set(['masu stem'])
	}

for s_inf in [
		'after a noun or the root of an adjective',
		'after a noun or the stem of an -i adjective']:

	s_inf_mapping[s_inf] = {
			'after_pos': set(['adj-i', 'n']),
			'after_form': set(['adjective stem'])
		}

for s_inf in [
		'adjective stem',
		'after the stem of an adjective']:

	s_inf_mapping[s_inf] = {
			'after_pos': set(['adj-i']),
			'after_form': set(['adjective stem'])
		}

s_inf_mapping['after a noun, adjective stem, onomatopoeic-mimetic word, etc.'] = {
		'after_pos': set(['n', 'adj-i', 'on-mim']),
		'after_form': set(['adjective stem'])
	}

s_inf_mapping['after a noun, adverb or adjective stem'] = {
		'after_pos': set(['n', 'adv', 'adj-i']),
		'after_form': set(['adjective stem'])
	}

s_inf_mapping['after a noun, the -nai stem of a verb, or repetitive syllables'] = {
		'after_pos': set(['v', 'n', 'on-mim']),
		'after_form': set(['negative stem'])
	}

s_inf_mapping['after an adjective stem, onomatopoeic-mimetic word, etc.'] = {
		'after_pos': set(['adj-i', 'on-mim']),
		'after_form': set(['adjective stem'])
	}

# For now I'll just ignore information about o- and go- prefixes
s_inf_mapping['after te-form of a verb or a noun prefixed with o- or go-'] = {
		'after_pos': set(['v', 'n']),
		'after_form': set(['-te'])
	}

s_inf_mapping['after te-form of verbs and adj.'] = {
		'after_pos': set(['v', 'adj-i']),
		'after_form': set(['-te'])
	}

s_inf_mapping['after the -te form or -masu stem of a verb'] = {
		'after_pos': set('v'),
		'after_form': set(['-te', 'masu stem'])
	}

s_inf_mapping['after the imperfective form of certain verbs and adjectives'] = {
		'after_pos': set(['v', 'adj-i']),
		'after_form': set(['dict'])
	}

s_inf_mapping["after the ren'youkei form of an adjective"] = {
		'after_pos': set(['adj-i']),
		'after_form': set(['adv'])
	}

s_inf_mapping['after the volitional or dictionary form of verb'] = {
		'after_pos': set('v'),
		'after_form': set(['volitional', 'dict'])
	}

s_inf_mapping['usu. after a noun or na-adjective prefixed with お- or ご-'] = {
		'after_pos': set(['n', 'adj-na']),
		'after_form': set('*')
	}

# TODO *ないで; いらっしゃる after a -te form, or the particle "de"

s_inf_mapping['after -masu stems, onomatopoeic and mimetic words'] = {
		'after_pos': set(['v', 'on-mim']),
		'after_form': set(['masu stem'])
	}

s_inf_mapping['after -tara form or -ta form'] = {
		'after_pos': set('v'),
		'after_form': set(['-tara', 'past'])
	}

s_inf_mapping[''] = {
		'after_pos': set('*'),
		'after_form': set('*')
	}

inflecting_pos = set([
       "v1",
       "v1-s",
       "v5b",
       "v5g",
       "v5k",
       "v5k-s",
       "v5m",
       "v5n",
       "v5r",
       "v5aru",
       "v5r-i",
       "v5s",
       "v5t",
       "v5u",
       "v5u-s",
       "vk",
       "vs-s",
       "vs-i",
       "adj-i"
       ])

def possible_pos(entry):
	all_pos = []
	for sg in entry.sense_groups:
		all_pos.extend(sg.pos)
	return inflecting_pos.intersection(all_pos)

def pickle_unpickle():
	global all_expressions
	if len(all_expressions) > 0:
		fullfill_pure_expressions()
		infer_from_corpus()
		all_expressions.sort(key=lambda e: e.etype.value)
		with open('tmp/all_expressions.pkl', 'wb') as f:
			pickle.dump(all_expressions, f)
		with open('tmp/all_expressions.pkl', 'rb') as f:
			assert pickle.load(f)[0].etype is ExpressionType.AUX
	else:
		with open('tmp/all_expressions.pkl', 'rb') as f:
			all_expressions = pickle.load(f)
		assert all_expressions[0].etype is ExpressionType.AUX

def dump_expressions():
	pickle_unpickle()

	old = set()
	if os.path.exists('data/expressions.dat'):
		with open('data/expressions.dat') as f:
			for l in f:
				l = l.strip().split()
				if l[0].startswith('#') or len(l[0]) == 0:
					continue
				old.add(l[0])

	with open('tmp/expressions.raw.dat', 'w') as ofe, open('tmp/expr.xml', 'w') as ofx:
		print('<root>', file=ofx)
		print('# vi', ': tabstop=30', sep='', file=ofe)
		level = 0

		for e in all_expressions:
			if e.etype == ExpressionType.PURE_EXP and len(e.seen_forms) == 0:
				continue

			print(e.etype, e.etype.value, ExpressionType.AUX.value, e.etype is ExpressionType.AUX)
			if e.etype == ExpressionType.AUX:
				joined = {}
				for i in e.sense_group_indices:
					sg = e.entry.sense_groups[i]
					pos = inflecting_pos.intersection(sg.pos)
					if len(pos) == 0:
						pos = '|'.join(possible_pos(e.entry))
						pos = pos or '?'
					else:
						pos = '|'.join(pos)
					for j, sense in enumerate(sg.senses):
						all_writings = []
						restricted = len(sense.kanji_restriction) + len(sense.reading_restriction) > 0
						for ki in (sense.kanji_restriction if restricted else range(len(e.entry.kanjis))):
							all_writings.append(e.entry.kanjis[ki].text)
						for ri in (sense.reading_restriction if restricted else range(len(e.entry.readings))):
							all_writings.append(e.entry.readings[ri].text)
						print(all_writings)
						all_writings = list(filter(lambda writing: writing not in old, all_writings))
						print(all_writings)
						if len(all_writings) == 0:
							continue

						s_inf = s_inf_mapping.get(sense.s_inf or '')
						if s_inf is not None:
							s_inf = '|'.join(s_inf['after_pos']) + '\t' + '|'.join(s_inf['after_form'])
						else:
							s_inf = sense.s_inf

						forms = '\n'.join(all_writings)
						key = ('\t'.join([forms, pos]), s_inf)
						joined.setdefault(key, []).append('{},{}'.format(i, j))

				for k, v in joined.items():
					k, s_inf = k
					if '\t' not in s_inf:
						error('Unknown s_inf:', s_inf)
						print('#', s_inf, file=ofe)
						s_inf = '?\t?'
					print(k, s_inf, e.entry.id, '|'.join(v), sep='\t', file=ofe)
					print('# --------------------------------------------------------------', file=ofe)
			elif e.etype == ExpressionType.S_INF_EXP:
				for i, j in e.sense_group_indices:
					sg = e.entry.sense_groups[i]
					pos = inflecting_pos.intersection(sg.pos)
					if len(pos) == 0:
						pos = '|'.join(possible_pos(e.entry))
						pos = pos or '?'
					else:
						pos = '|'.join(pos)

					sense = sg.senses[j]
					s_inf = s_inf_mapping.get(sense.s_inf or '')
					if s_inf is None:
						error('Unknown s_inf:', sense.s_inf)
						print('#', sense.s_inf, file=ofe)
						s_inf = '?\t?'
					else:
						s_inf = '|'.join(s_inf['after_pos']) + '\t' + '|'.join(s_inf['after_form'])

					all_writings = []
					restricted = len(sense.kanji_restriction) + len(sense.reading_restriction) > 0
					for ki in (sense.kanji_restriction if restricted else range(len(e.entry.kanjis))):
						all_writings.append(e.entry.kanjis[ki].text)
					for ri in (sense.reading_restriction if restricted else range(len(e.entry.readings))):
						all_writings.append(e.entry.readings[ri].text)
					all_writings = list(filter(lambda writing: writing not in old, all_writings))
					if len(all_writings) == 0:
						continue

					print('\n'.join(all_writings), pos, s_inf, e.entry.id, '{},{}'.format(i, j), sep='\t', file=ofe)
				print('# --------------------------------------------------------------', file=ofe)
			else:
				all_senses = []
				for i, sg in enumerate(e.entry.sense_groups):
					for j in range(len(sg.senses)):
						all_senses.append('{},{}'.format(i, j))
				all_senses = '|'.join(all_senses)

				for form, pos in e.seen_forms.items():
					if form not in old:
						print(form, '|'.join(pos), '?', '?', e.entry.id, all_senses, sep='\t', file=ofe)

			for line in e.elem:
				if line.startswith('<'):
					if line[1] != '/':
						last_open = line[1:]
						level += 1
						print('\t'*level, end='', file=ofx)
					else:
						if line[2:-1] != last_open:
							print('\t'*level, end='', file=ofx)
						level -= 1
				print(line, sep='', end='', file=ofx)

		print('</root>', file=ofx)

if __name__ == "__main__":
	dump_expressions()
