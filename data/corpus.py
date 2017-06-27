import subprocess
from utils import *

sentences_file = "tmp/jpn_indices.csv"
if not os.path.exists(sentences_file):
	download('http://downloads.tatoeba.org/exports/jpn_indices.tar.bz2', 'jpn_indices.tar.bz2')
	subprocess.run(["tar", "-xf", "tmp/jpn_indices.tar.bz2", "-C", "tmp"], check=True)
	subprocess.run(["rm", "tmp/jpn_indices.tar.bz2"], check=True)

Word = namedtuple('Word', 'dkanji, dreading, form, sense_index')
def parse(w):
	dkanji = []
	reading = []
	form = []
	sense = []
	last_control = ''
	for c in w:
		if c in '{}()[]|~':
			last_control = c
		elif last_control == '':
			dkanji.append(c)
		elif last_control == '(':
			reading.append(c)
		elif last_control == '{':
			form.append(c)
		elif last_control == '[' or last_control == '|':
			sense.append(c)
	dkanji = ''.join(dkanji)
	reading = ''.join(reading) if len(reading) > 0 else None
	form = ''.join(form) if len(form) > 0 else dkanji
	for i in range(43):
		form = form.replace(chr(ord('0') + i), chr(ord('０') + i))
	form = form.replace('、', '')
	form = form.replace('～', '')
	sense = int(''.join(sense)) - 1 if len(sense) > 0 else None
	return Word(dkanji, reading, form, sense)

assert parse('は|1') == Word('は', None, 'は', 0)
assert parse('二十歳(はたち){２０歳}') == Word('二十歳', 'はたち', '２０歳', None)
assert parse('になる[02]{になりました}') == Word('になる', None, 'になりました', 1)
assert parse('妻(つま)|1') == Word('妻', 'つま', '妻', 0)

def corpus_reader():
	line_no = 0
	since = 0
	with open(sentences_file) as f:
		for string_line in f:
			line_no += 1
			if line_no < since: continue
			if line_no % 1000 == 0: print(sentences_file, line_no)
			words = string_line.split()[2:]
			i = 0
			while i < len(words):
				word = words[i]
				if word.startswith('※'):
					words.pop(i)
					continue

				words[i] = parse(word)
				assert len(words[i].form) > 0
				i += 1
			yield words
