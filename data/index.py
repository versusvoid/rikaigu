#!/usr/bin/env python3
import sys
import re
import os
from collections import defaultdict
from utils import *

# Mapping from kanji to set of it's readings
kanji_dict = {}
with open('data/kanji.dat', 'r') as f:
	for l in f:
		l = l.split('|')
		kanji = l[0]
		readings = (l[2] + ' ' + l[3]).split()
		all_readings = set()
		for reading in readings:
			res = reading.replace('-', '')
			if is_katakana(res[0]):
				# Convert all readings to hiragana
				new_res = []
				for c in res:
					new_res.append(chr(ord(c) - ord('ァ') + ord('ぁ')))
				res = ''.join(new_res)

			j = res.find('.')
			if j != -1:
				assert res.count('.') == 1
				res = res[:-1]
				before, after = res.split('.')
				# For kun-readings kanji can devour okurigana
				# up to last letter
				for i in range(len(after)):
					partial_reading = before + after[:i+1]
					all_readings.add(partial_reading)
				res = before

			all_readings.add(res)
		for reading in list(all_readings):
			if len(reading) > 1 and reading[-1] == 'つ':
				all_readings.add(reading[:-1] + 'っ')
			if reading[0] in set('かきくけこさしすせそたちつてとばびぶべぼ'):
				all_readings.add(chr(ord(reading[0]) + 1) + reading[1:])
			elif reading[0] in set('はひふへほ'):
				all_readings.add(chr(ord(reading[0]) + 1) + reading[1:])
				all_readings.add(chr(ord(reading[0]) + 2) + reading[1:])

		assert kanji not in kanji_dict
		kanji_dict[kanji] = list(all_readings)

def anchor_groups(w, reading):
	kanji_groups = []
	kanjis = {}
	j = 0
	i = 0
	# Mapping `position in word` -> `position in reading`
	anchors = []
	while i < len(w):
		c = w[i]
		if is_kanji(c):
			kanjis.setdefault(c, []).append(i)
			i_ = i + 1
			while i_ < len(w) and is_kanji(w[i_]):
				kanjis.setdefault(w[i_], []).append(i_)
				i_ += 1
			kanji_groups.append((i, i_))
			anchors.append((i, j))
			i = i_
		else:
			i_ = i + 1
			while i_ < len(w) and is_hiragana(w[i_]):
				i_ += 1
			kana_space = w[i:i_]

			j_ = reading.find(kana_space, j)
			if j_ == -1: return
			j__ = reading.find(kana_space, j_ + len(kana_space))
			if j__ == -1 or reading.count(kana_space, j) == w.count(kana_space, i):
				anchors.append((i, j_))
				j = j_ + len(kana_space)
				i = i_
			else:
				#assert False, f'{w} {reading} {c} {i} {j} {j_} {j__}'
				# TODO brutesearch through kanjis' readings for groups with hiragana (菖蒲か杜若)
				return

	return anchors, kanji_groups, kanjis

def anchor_kanjis(w, reading, kanji_groups, anchors):
	for start, end in kanji_groups:
		if end - start == 1: continue
		compound = w[start:end]
		compound_reading = reading[anchors[start]:anchors[end]]
		per_kanji_readings = list(map(kanji_dict.__getitem__, compound))
		remaining_reading = compound_reading
		# stack[i] - index in per_kanji_readings[i]
		stack = [-1]
		partitions = []
		# Bruteforce with backtracking through combinations of readings
		while len(stack) > 0:
			first_reading = stack.pop() + 1
			found = False
			if len(stack) == end - start - 1:
				# When only one kanji left - we simply check for remaining part of reading
				try:
					i = per_kanji_readings[-1].index(remaining_reading)
					stack.append(i)
					found = True
				except:
					pass
			else:
				# Otherwise loop through all readings for kanji looking for appropriate
				for i in range(first_reading, len(per_kanji_readings[len(stack)])):
					kanji_reading = per_kanji_readings[len(stack)][i]
					if remaining_reading.startswith(kanji_reading):
						remaining_reading = remaining_reading[len(kanji_reading):]
						stack.append(i)
						found = True
						break

			if found:
				# If appropriate reading was found
				if len(stack) == len(compound):
					# .. and it was last kanji in group
					partitions.append(stack[:])
					stack.pop()
					# Restore remaining reading and backtrack, until
					# we find any more possible readings to check
					i = stack[-1]
					remaining_reading = per_kanji_readings[len(stack) - 1][i] + remaining_reading
					while len(stack) > 0 and stack[-1] == len(per_kanji_readings[len(stack) - 1]) - 1:
						stack.pop()
						if len(stack) > 0:
							i = stack[-1]
							remaining_reading = per_kanji_readings[len(stack) - 1][i] + remaining_reading
					if len(stack) > 0:
						stack[-1] += 1
				else:
					stack.append(-1)
			elif len(stack) > 0:
				# If reading was not found - backtrack
				i = stack[-1]
				remaining_reading = per_kanji_readings[len(stack) - 1][i] + remaining_reading

		if len(partitions) != 1:
			'''
			print(w, reading, compound, compound_reading, sep='\n')
			print(*per_kanji_readings, sep='\n')
			for p in partitions:
				print(*map(lambda p: per_kanji_readings[p[0]][p[1]], enumerate(p)))
			print('-----------------------------------------------')
			'''
			if len(partitions) > 1:
				# TODO rate readings
				pass
			raise Exception('ambigous reading partitioning')

		for i, j in enumerate(partitions[0]):
			p = anchors[start + i] + len(per_kanji_readings[i][j])
			assert anchors.setdefault(start + i + 1, p) == p

def compute_variations(w, reading):

	# ========== Phase 1: anchor kana/kanji groups ===============
	try:
		anchors, kanji_groups, kanjis = anchor_groups(w, reading)
	except:
		return

	# ========== Phase 2: anchor kanjis inside groups ============
	anchors = dict(anchors)
	anchors[len(w)] = len(reading)
	try:
		anchor_kanjis(w, reading, kanji_groups, anchors)
	except:
		return

	# ======== Phase 3: replace every type of kanji one by one ==========
	for kanji, occurances in kanjis.items():
		assert all(map(anchors.__contains__, occurances))

		# Writing variation with all instances of this
		# kanji replaced by it's reading(s)
		i = 0
		res = []
		for j in occurances:
			res.append(w[i:j])
			res.append(reading[anchors[j]:anchors[j+1]])
			i = j + 1
		res.append(w[i:])
		res = ''.join(res)
		yield res

		for j in occurances:
			if j + 2 >= len(w) or not is_hiragana(w[j + 1]): continue
			# Writing variation, where kanji devours part of okurigana.
			# Currently - single letter only
			kanji_reading = reading[anchors[j]:anchors[j+1]]
			if (kanji_reading + w[j + 1]) in kanji_dict[w[j]]:
				yield w[:j + 1] + w[j + 2:]

word_re = re.compile('[一-龥ぁ-ゔ]+') # Hiragana and kanji only
kanji_re = re.compile('[一-龥]')
kanji_3_in_row_re = re.compile('[一-龥]{3,}')
candidate_re = re.compile('[一-龥][ぁ-ゔ]') # At least one hiragana after kanji
def is_variable_word(w):
	if word_re.fullmatch(w) is None:
		return False
	if candidate_re.search(w) is None:
		return
	m = kanji_re.findall(w)
	# No sense to expand single kanji - we'll simply get reading
	if len(m) < 2:
		return False
	# Word must contain at least two different kanji
	for i in range(1, len(m)):
		if m[i] != m[i - 1]:
			break
	else:
		return False
	# Currently we are not interested in words with more than 2
	# kanji without hiragana between them
	if kanji_3_in_row_re.search(w) is not None:
		return False
	return True


def index_keys(entry, variate=True, convert_to_hiragana=True, with_source=False):
	transform = kata_to_hira if convert_to_hiragana else (lambda x: x)
	res = defaultdict(set)
	for k in entry.kanjis:
		res[transform(k.text)].add(k.text)
	for r in entry.readings:
		res[transform(r.text)].add(r.text)
		if variate:
			for ki in r.kanjis:
				k = entry.kanjis[ki]
				if not is_variable_word(k.text): continue
				for key in compute_variations(k.text, r.text):
					res[key].add(k.text)

	if with_source:
		return res
	else:
		return set(res)
