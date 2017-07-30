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

def split_words(sentence_part, start_index, words, words_start_index):
	sample = []
	i = 0

	#print(sentence_part, start_index, words, words_start_index)

	if words_start_index < len(words) and start_index > words[words_start_index].start_index:
		words_start_index += 1

	while i < len(sentence_part):
		if words_start_index >= len(words):
			sample.append(sentence_part[i:])
			i = len(sentence_part)
		elif start_index + i < words[words_start_index].start_index:
			end = words[words_start_index].start_index - start_index
			sample.append(sentence_part[i:end])
			i = end
		else:
			if start_index + i != words[words_start_index].start_index:
				print(sentence_part)
				print('start_index =', start_index, 'i =', i, 'words_start_index =', words_start_index)
				print(*enumerate(words), sep='\n')
				raise Exception('Wtf')
			end = i + len(words[words_start_index].form)
			sample.append(sentence_part[i:end])
			i = end
			words_start_index += 1

	return ' '.join(sample), words_start_index

samples = []
def record_samples(sentence_text, words):
	sample_start_index = 0
	words_start_index = 0
	current_sample = None
	for i, c in enumerate(sentence_text):
		if not is_japanese_character(c):
			if current_sample is not None:
				sample, words_start_index = split_words(''.join(current_sample), sample_start_index, words, words_start_index)
				#print(sample)
				samples.append(sample)
			current_sample = None
		else:
			if current_sample is None:
				current_sample = []
				sample_start_index = i
			current_sample.append(c)

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
	if word1.start_index + len(word1.form) != word2.start_index:
		return False

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


for sentence_text, words in corpus.corpus_reader():
	i = 0
	while i + 1 < len(words):
		# TODO test
		if should_join(words[i], words[i + 1]):
			#sentence[i]._replace(form=sentence[i].form + sentence[i + 1].form)
			words[i] = join(words[i], words[i+1])
			words.pop(i + 1)
		else:
			i += 1

	record_samples(sentence_text, words)

	#sentence = [resolve(w) for w in sentence]
	#for i in range(5):
	#	for i, w in enumerate(sentence):
	#		sentence[i] = substitute_word(w)
	#	record_samples([w.corpus_word.form for w in sentence])

del known_expressions
del words_by_pos

random.shuffle(samples)
print("Number of samples:", len(samples))
#lsamples = lsamples[:1000000]

with open('segmentation/train.csv', 'w', encoding='utf-16') as f:
	print(*samples[0:int(0.8*len(samples))], sep='\n', end='', file=f)

#with open(f'segmentation/{direction}-cv.csv', 'w', encoding='utf-16') as f:
	#print(*samples[int(0.6*len(samples)):int(0.8*len(samples))], sep='\n', end='', file=f)

with open('segmentation/test.csv', 'w', encoding='utf-16') as f:
	print(*samples[int(0.8*len(samples)):], sep='\n', end='', file=f)
