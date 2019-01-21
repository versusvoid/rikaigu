#!/usr/bin/env python3

import os
import random
import sys
mydir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(mydir + '/../data')
from expressions import parse, sentences_file
from index import index_keys
from utils import *


def char_class(c):
	if is_kanji(c):
		return 'K'
	elif is_hiragana(c):
		return 'h'
	elif is_katakana(c):
		return 'k'
	else:
		return 'm'

rsamples = []
lsamples = []
def record_samples(sentence):
	split_sentence = []
	for form in sentence:
		split_sentence.append('\t'.join((form[0], char_class(form[0]), 'S')))
		split_sentence.extend(map(lambda c: '\t'.join((c, char_class(c), 'M')), form[1:]))
	for i in range(2, len(split_sentence)):
		lsamples.append('\n'.join(split_sentence[max(i - 14, 0):i][::-1]))

line_no = 0
with open(sentences_file, 'r') as f:
	for ls in f:
		line_no += 1
		if line_no % 1000 == 0:
			print(sentences_file, line_no)
		l = ls.split()[2:]

		record_samples(list(map(lambda w: parse(w).form, l)))

def get_writings(entry):
	if type(entry) == Entry:
		return index_keys(entry)
	else:
		res = []
		for k in entry.kanjis:
			res.append(k.text)
		for r in entry.readings:
			res.append(r.text)
		return res

for filename in ('JMdict_e.gz', 'JMnedict.xml.gz'):
	for entry, _ in dictionary_reader(filename):
		for writing in get_writings(entry):
			record_samples([writing])


random.shuffle(rsamples)
random.shuffle(lsamples)

for direction, samples in [('r', rsamples), ('l', lsamples)]:
	with open(f'segmentation/{direction}-train.csv', 'w') as f:
			print(*samples[0:int(0.7*len(samples))], sep='\n\n', end='', file=f)
	with open(f'segmentation/{direction}-cv-train.csv', 'w') as f:
			print(*samples[0:int(0.1*len(samples))], sep='\n\n', end='', file=f)
	with open(f'segmentation/{direction}-cv.csv', 'w') as f:
			print(*samples[int(0.7*len(samples)):int(0.8*len(samples))], sep='\n\n', end='', file=f)
	with open(f'segmentation/{direction}-test.csv', 'w') as f:
			print(*samples[int(0.8*len(samples)):], sep='\n\n', end='', file=f)
