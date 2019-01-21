
from utils import *

freqlist1_path = download('https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/Japanese', 'freqs-0-10000')
freqlist2_path = download('https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/Japanese10001-20000', 'freqs-10001-20000')
# TODO use https://github.com/LuminosoInsight/wordfreq
freqs = {}
max_freq = 1
for filename in [freqlist1_path, freqlist2_path]:
	with open(filename, 'r') as f:
		for l in f:
			if not l.startswith('<li>'): continue
			start = l.find('>')
			while l[start + 1] == '<':
				start = l.find('>', start + 1)
			assert is_katakana(l[start + 1]) or is_hiragana(l[start + 1]) or is_kanji(l[start + 1]), l
			end = start + 2
			while is_katakana(l[end]) or is_hiragana(l[end]) or is_kanji(l[end]):
				end += 1
			w = l[start + 1:end]
			freqs[w] = max_freq
			max_freq += 1

def get_frequency(w):
	return freqs.get(w, max_freq)
