
from utils import download, is_hiragana, is_katakana, is_kanji

def _load_freqs_old():
	freqlist1_path = download('https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/Japanese', 'freqs-0-10000')
	freqlist2_path = download('https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/Japanese10001-20000', 'freqs-10001-20000')
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

_freq_order = {}
def _load_freqs():
	download('http://namakajiri.net/data/wikipedia-20150422-lemmas.tsv', 'wikipedia-20150422-lemmas.tsv')
	with open('tmp/wikipedia-20150422-lemmas.tsv') as f:
		for l in f:
			freq, lemma = l.strip().split()[1:]
			assert lemma not in _freq_order
			freq = int(freq)
			if freq < 1000:
				break
			_freq_order[lemma] = len(_freq_order)
_load_freqs()

def get_frequency(entry):
	min_freq_order = len(_freq_order)
	for kanji in entry.kanjis:
		min_freq_order = min(min_freq_order, _freq_order.get(kanji.text, min_freq_order))
	if min_freq_order < len(_freq_order):
		return min_freq_order

	if entry.is_archaic():
		return None
	for r in entry.get_uk_readings():
		min_freq_order = min(min_freq_order, _freq_order.get(r.text, min_freq_order))
	if min_freq_order < len(_freq_order):
		return min_freq_order

	for r in entry.readings:
		if len(entry.kanjis) == 0 or is_katakana(r.text[0]):
			min_freq_order = min(min_freq_order, _freq_order.get(r.text, min_freq_order))
	if min_freq_order < len(_freq_order):
		return min_freq_order

	return None

def get_name_frequency(name):
	min_freq_order = len(_freq_order)
	for kanji in name.kanjis:
		min_freq_order = min(min_freq_order, _freq_order.get(kanji.text, min_freq_order))
	if min_freq_order < len(_freq_order):
		return min_freq_order
