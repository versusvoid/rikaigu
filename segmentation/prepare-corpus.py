#!/usr/bin/env python3

import random
import sys
from collections import namedtuple
import os
import lzma
import itertools

mydir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(mydir + '/../data')
from expressions import deinflect, deinflection_rules, inflecting_pos
from index import index_keys
import corpus
import dictionary
from utils import *

# Right (suffix) samples
rsamples = []
# Left (prefix) samples (each sample in reverse direction)
lsamples = []
glove_file = lzma.open('segmentation/glove.csv.xz', 'wt')
def record_sentence(sentence):
	#print(*''.join(sentence), sep=' ', file=glove_file)
	pass
def record_samples(sentence):
	record_sentence(sentence)
	sentence = ' ' + ' '.join(sentence)
	#lsamples.append(sentence[::-1])
	#lsamples.append(sentence)
	for i in range(2, len(sentence)):
		if sentence[i] == ' ': continue
		#lsamples.append(sentence[max(i - 14, 0):i + 1][::-1])
		lsamples.append(sentence[max(i - 14, 0):i + 1])

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

def get_dictionary_pos(word):
	res = set()
	for e in dictionary.find_entry(word.dkanji, word.dreading):
		for sg in e.sense_groups:
			res.update(sg.pos)

	return res

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

known_expressions = load_expressions()
dictionary.load_dictionary()
words_by_pos = {}
for entries in dictionary._dictionary.values():
	for entry in entries:
		for sg in entry.sense_groups:
			pos_key = '-'.join(sg.pos)
			words_by_pos.setdefault(pos_key, []).append(entry)

PartialEntry = namedtuple('PartialEntry', 'entry, sense_groups_indices')
DictionaryBackedWord = namedtuple('DBK', 'corpus_word, partial_entries, base_suffix_len, inflected_suffix_len')
non_substituable_pos = {'aux', 'conj', 'cop-da', 'exp', 'int', 'n-pref', 'n-suf', 'n-t', 'num', 'pref', 'prt', 'suf', 'unc'}
def resolve(word):
	entries = dictionary.find_entry(word.dkanji, word.dreading)
	partial_entries = []
	for entry in entries:
		sense_groups_indices = []
		for i, sense_group in enumerate(entry.sense_groups):
			if len(non_substituable_pos.intersection(sense_group.pos)) == 0:
				sense_groups_indices.append(i)
		if len(sense_groups_indices) > 0:
			assert all([i < len(entry.sense_groups) for i in sense_groups_indices])
			partial_entries.append(PartialEntry(entry, sense_groups_indices))
	if len(partial_entries) == 0:
		partial_entries = None
	return DictionaryBackedWord(word, partial_entries, None, None)

def join(word1, word2):
	return word1._replace(form=word1.form + word2.form)

def common_prefix_len(a, b):
	for i in range(min(len(a), len(b))):
		if not b.startswith(a[:i + 1]):
			return i

	return min(len(a), len(b))

# TODO test
def inflected_suffixes_len(entry, form):
	longest_prefix = -1
	base_suffix_len = None
	inflected_suffix_len = len(form)
	for k in itertools.chain(entry.kanjis, entry.readings):
		prefix_len = common_prefix_len(k.text, form)
		if prefix_len > longest_prefix:
			longest_prefix = prefix_len
			base_suffix_len = len(k.text) - prefix_len
			inflected_suffix_len = len(form) - prefix_len

	return base_suffix_len, inflected_suffix_len

def conjugate(new_entry, sense_group_index, old_entry, old_corpus_word, base_suffix_len, inflected_suffix_len):
	if base_suffix_len is None:
		base_suffix_len, inflected_suffix_len = inflected_suffixes_len(old_entry, old_corpus_word.form)
	# TODO filter out unused in this sense group
	candidates = new_entry.kanjis + new_entry.readings
	dkanji = random.choice(candidates).text
	new_corpus_word = corpus.Word(dkanji, None, dkanji[:-base_suffix_len] + old_corpus_word.form[-inflected_suffix_len:], None)
	return DictionaryBackedWord(new_corpus_word, [PartialEntry(new_entry, [sense_group_index])], base_suffix_len, inflected_suffix_len)

def substitute_word(word):
	if word.partial_entries is None:
		return word
	entry, sense_groups_indices = random.choice(word.partial_entries)
	i = random.choice(sense_groups_indices)
	assert i < len(entry.sense_groups), f'{entry}\n{sense_groups_indices}'
	pos_key = '-'.join(entry.sense_groups[i].pos)
	new_entry = random.choice(words_by_pos[pos_key])
	for i, sg in enumerate(new_entry.sense_groups):
		if '-'.join(sg.pos) == pos_key:
			break
	return conjugate(new_entry, i, entry, word.corpus_word, word.base_suffix_len, word.inflected_suffix_len)


for sentence in corpus.corpus_reader():
		i = 0
		while i + 1 < len(sentence):
			# TODO test
			if should_join(sentence[i], sentence[i + 1]):
				#sentence[i]._replace(form=sentence[i].form + sentence[i + 1].form)
				sentence[i] = join(sentence[i], sentence[i+1])
				sentence.pop(i + 1)
			else:
				i += 1

		record_samples([w.form for w in sentence])

		sentence = [resolve(w) for w in sentence]
		for i in range(5):
			for i, w in enumerate(sentence):
				sentence[i] = substitute_word(w)
			record_samples([w.corpus_word.form for w in sentence])

del known_expressions
del words_by_pos

random.shuffle(rsamples)
random.shuffle(lsamples)
lsamples = lsamples[:1000000]

# For now we only use left samples
for direction, samples in [('l', lsamples)]:
	with open(f'segmentation/{direction}-train.csv', 'w', encoding='utf-16') as f:
		print(*samples[0:int(0.8*len(samples))], sep='\n', end='', file=f)

	#with open(f'segmentation/{direction}-cv.csv', 'w', encoding='utf-16') as f:
		#print(*samples[int(0.6*len(samples)):int(0.8*len(samples))], sep='\n', end='', file=f)

	with open(f'segmentation/{direction}-test.csv', 'w', encoding='utf-16') as f:
		print(*samples[int(0.8*len(samples)):], sep='\n', end='', file=f)
glove_file.close()
