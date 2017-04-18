#!/usr/bin/env python3

import os
import random
import sys
from collections import namedtuple
mydir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(mydir + '/../data')
from expressions import parse, sentences_file, deinflect, deinflection_rules, inflecting_pos
from index import index_keys
from utils import *

# Right (suffix) samples
rsamples = []
# Left (prefix) samples (each sample in reverse direction)
lsamples = []
def record_samples(sentence):
	sentence = ' ' + ' '.join(sentence)
	for i in range(2, len(sentence)):
		if sentence[i] == ' ': continue
		lsamples.append(sentence[max(i - 14, 0):i + 1][::-1])

Inflection = namedtuple('Inflection', 'to, source_type, target_type, reason')
inflection_rules = {}
max_inflection_length = 0
for source, rules in deinflection_rules.items():
	for rule in rules:
		max_inflection_length = max(max_inflection_length, len(rule.to))
		inflection_rule = Inflection(source, rule.target_type, rule.source_type, rule.reason)
		inflection_rules.setdefault(rule.to, []).append(inflection_rule)

def inflect(word, all_pos):
	inflections = [(word, all_pos, [])]
	seen = set([word])
	i = -1
	while i + 1 < len(inflections):
		i += 1
		form, form_pos, inflection_reasons = inflections[i]

		for j in range(min(len(form), max_inflection_length), 0, -1):
			suffix_inflection_rules = inflection_rules.get(form[-j:])
			if suffix_inflection_rules is None: continue

			for rule in suffix_inflection_rules:
				if len(rule.source_type.intersection(form_pos)) == 0: continue
				if rule.reason in inflection_reasons: continue
				new_form = form[:-j] + rule.to

				if new_form in seen: continue
				seen.add(new_form)

				if len(inflection_reasons) < 2: # max - 3 inflections (current being third)
					inflections.append((new_form, rule.target_type, inflection_reasons + [rule.reason]))

	seen = list(seen)
	return random.choice(seen)

def load_expressions():
	expressions = {}
	with open('data/expressions.dat') as f:
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
				other_requirements = expressions.get(form)
				if other_requirements is None:
					expressions[form] = requirements
				else:
					other_requirements['after_pos'].update(requirements['after_pos'])
					other_requirements['after_form'].update(requirements['after_form'])

	return expressions

def load_dictionary():
	dictionary = {}
	all_forms = set()
	for entry, _ in dictionary_reader():
		all_pos = set().union(*[sg.pos for sg in entry.sense_groups])
		inflecting = len(inflecting_pos.intersection(all_pos)) > 0
		for form in index_keys(entry, variate=True, convert_to_hiragana=False):
			dictionary.setdefault(kata_to_hira(form), set()).update(all_pos)

			if form in all_forms: continue

			# TODO can be optimized because every form would have same
			# inflecting ending, so we really need to call inflect() once per entry
			# Moreover to reduce memory usage we can have list of pairs
			# (entry's form's prefixes, pos) and compute inflected forms only when needed
			# But anyway we will hit resource starvation during learning before we
			# hit it here
			if inflecting:
				all_forms.add(inflect(form, all_pos))
			else:
				all_forms.add(form)

	for entry, _ in dictionary_reader('JMnedict.xml.gz'):
		for form in index_keys(entry, variate=False, convert_to_hiragana=False):
			all_forms.add(form)

	return dictionary, list(all_forms)

def get_dictionary_pos(word):
	return dictionary.get(kata_to_hira(word.dkanji), set())

def get_expression_requirements(word):
	requirements = known_expressions.get(word.dkanji)
	if requirements is not None:
		return requirements

	for pos, reasons in deinflect(word.form).items():
		for dictionary_form, _ in reasons:
			requirements = known_expressions.get(dictionary_form)
			if requirements is None: continue

			if requirements['pos'] == pos:
				return requirements

	return None

def meets_requirements(word, requirements):

	if ('*' not in requirements['after_pos'] and
			len(requirements['after_pos'].intersection(get_dictionary_pos(word))) == 0):
		return False

	if '*' in requirements['after_form']:
		return True

	for _, reasons in deinflect(word.form).items():
		for _, reason_chain in reasons:
			if 'raw' in requirements['after_form'] and len(reason_chain) == 0:
				return True
			if len(reason_chain) > 0 and reason_chain[0] in requirements['after_form']:
				return True

	return False


def should_join(word1, word2):
	requirements = get_expression_requirements(word2)
	if requirements is None:
		return False

	return meets_requirements(word1, requirements)

def generate_samples_from_dictionaries():
	for form in all_forms:
		#record_samples([form])

		prefix = random.choice(all_forms)
		record_samples([prefix, form])

		#suffix = random.choice(all_forms)
		#record_samples([form, suffix])

known_expressions = load_expressions()
dictionary, all_forms = load_dictionary()
generate_samples_from_dictionaries()

line_no = 0
with open(sentences_file, 'r') as f:
	for ls in f:
		line_no += 1
		if line_no % 1000 == 0:
			print(sentences_file, line_no)
			#if len(lsamples) >= 10000: break
		sentence = [parse(w) for w in ls.split()[2:]]

		i = 0
		while i + 1 < len(sentence):
			# TODO test
			if should_join(sentence[i], sentence[i + 1]):
				sentence[i] = sentence[i]._replace(form=sentence[i].form + sentence[i + 1].form)
				sentence.pop(i + 1)
			else:
				i += 1

		record_samples([w.form for w in sentence])


del dictionary
del known_expressions
del all_forms


random.shuffle(rsamples)
random.shuffle(lsamples)
#lsamples = lsamples[:10000]


def char_class(c):
	if is_kanji(c):
		return 'K'
	elif is_hiragana(c):
		return 'h'
	elif is_katakana(c):
		return 'k'
	else:
		return 'm'

def make_crfpp_sample(sample):
	res = []
	for c in sample:
		if c == ' ':
			res[-1] = res[-1][:-1] + 'S'
		else:
			res.append(f'{c}\t{char_class(c)}\tM')
	return '\n'.join(res)

# For now we only use left samples
for direction, samples in [('l', lsamples)]:
	with open(f'segmentation/{direction}-all.csv', 'w', encoding='utf-16') as f:
			print(*samples, sep='\n', end='', file=f)

	with open(f'segmentation/{direction}-train.csv', 'w', encoding='utf-16') as f:
			print(*samples[0:int(0.8*len(samples))], sep='\n', end='', file=f)
#	with open(f'segmentation/{direction}-train.crfpp.csv', 'w') as f:
#			print(*map(make_crfpp_sample, samples[0:int(0.8*len(samples))]), sep='\n\n', end='', file=f)

	with open(f'segmentation/{direction}-cv.csv', 'w', encoding='utf-16') as f:
			print(*samples[int(0.6*len(samples)):int(0.8*len(samples))], sep='\n', end='', file=f)

	with open(f'segmentation/{direction}-test.csv', 'w', encoding='utf-16') as f:
			print(*samples[int(0.8*len(samples)):], sep='\n', end='', file=f)
#	with open(f'segmentation/{direction}-test.crfpp.csv', 'w') as f:
#			print(*map(make_crfpp_sample, samples[int(0.8*len(samples)):]), sep='\n\n', end='', file=f)
