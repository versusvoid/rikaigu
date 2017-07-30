import subprocess
import gzip
import sys
import traceback
import io
from utils import *

sentences_file = "tmp/examples.utf.gz"
if not os.path.exists(sentences_file):
	download('ftp://ftp.monash.edu.au/pub/nihongo/examples.utf.gz', 'examples.utf.gz')

Sentence = namedtuple('Sentence', 'text, words')
Word = namedtuple('Word', 'dkanji, dreading, form, start_index')
def parse(w, sentence_plain_text, minimal_start_index):
	dkanji = []
	reading = []
	form = []
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
			pass
	dkanji = ''.join(dkanji)
	reading = ''.join(reading) if len(reading) > 0 else None
	form = ''.join(form) if len(form) > 0 else dkanji
	start_index = sentence_plain_text.find(form, minimal_start_index)
	if start_index == -1 and form.endswith('―'):
		form = form[:-1]
		start_index = sentence_plain_text.find(form, minimal_start_index)
	if start_index == -1:
		start_index = sentence_plain_text.find(dkanji, minimal_start_index)
		if start_index >= 0:
			dkanji, form = form, dkanji
	if start_index == -1 and reading is not None:
		start_index = sentence_plain_text.find(reading, minimal_start_index)
		if start_index >= 0:
			reading, form = form, reading
	if start_index == -1:
		raise Exception(sentence_plain_text, w)
	#form = form.replace('、', '')
	return Word(dkanji, reading, form, start_index)

def corpus_reader():
	line_no = 0
	since = 0
	shit = 0

	sample = '''A: 首相の辞任のニュースは私たちを驚かせた。	The news of the prime minister's resignation took us by surprise.#ID=266140_148419
B: 首相 の 辞任[02] の ニュース は 私たち を[02] 驚かせる{驚かせた}'''
	with gzip.open(sentences_file, 'rt') as f, open('shit.log', 'w') as shit_of:
	#with io.StringIO(sample) as f, open('shit.log', 'w') as shit_of:
		sentence_plain_text = None
		for string_line in f:
			for i in range(43):
				string_line = string_line.replace(chr(ord('０') + i), chr(ord('0') + i))
			if string_line[0] == 'A':
				sentence_plain_text = string_line[3:string_line.index('\t')]
				continue

			line_no += 1
			if line_no < since: continue
			if line_no % 1000 == 0: print(sentences_file, line_no)
			words = string_line.split()[1:]
			i = 0
			index_in_sentence = 0
			try:
				while i < len(words):
					word = words[i]
					if word.startswith('※'):
						words.pop(i)
						continue

					words[i] = parse(word, sentence_plain_text, index_in_sentence)
					#print(word, '->', words[i])
					if len(words[i].form) == 0:
						assert len(words[i].dkanji) == 0 and words[i].dreading is None
						words.pop(i)
						continue
					assert len(words[i].form) > 0, f'{sentence_plain_text} {word} {index_in_sentence}'
					index_in_sentence = words[i].start_index + len(words[i].form)
					i += 1
			except:
				print(f"Parse failed\n{sentence_plain_text}\n{string_line}:", traceback.format_exc(), file=shit_of)
				shit += 1
				continue

			yield Sentence(sentence_plain_text, words)
	print("Shitty sentences:", shit)
