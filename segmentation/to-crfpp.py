#!/usr/bin/env python3

import sys
import os
mydir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(mydir + '/../data')
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

def make_crfpp_sample(sample):
	res = []
	tag = 'M'
	for c in sample:
		if c == ' ':
			#if len(res) > 0: res[-1] = res[-1][:-1] + 'S'
			tag = 'S'
		else:
			res.append(f'{c}\t{char_class(c)}\t{tag}')
			tag = 'M'
	for i in range(len(res)):
		res[i] += 'M' if i + 1 >= len(res) else res[i + 1][-1]
		res[i] += 'M' if i + 2 >= len(res) else res[i + 2][-1]

	return '\n'.join(res)

for filename in sys.argv[1:]:
	with open(filename, encoding='utf-16') as f, open(f'{filename}.crfpp', 'w') as of:
		first = True
		for l in f:
			if not first:
				print('\n\n', end='', file=of)
			print(make_crfpp_sample(l.strip('\n')), end='', file=of)
			first = False


