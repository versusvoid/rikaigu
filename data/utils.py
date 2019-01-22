import os
import time
import urllib.request
from collections import namedtuple
import gzip
import xml.etree.ElementTree as ET
import builtins

def all(function_or_iterable, *args):
	if len(args) == 0:
		return builtins.all(function_or_iterable)
	else:
		return builtins.all(map(function_or_iterable, args[0]))

def any(function_or_iterable, *args):
	if len(args) == 0:
		return builtins.any(function_or_iterable)
	else:
		return builtins.any(map(function_or_iterable, args[0]))

def is_kanji(c):
	code = ord(c)
	return (code >= 0x4e00 and code <= 0x9fa5) or code > 0xffff # last one isn't good enough in case of ja.wiktionary

def is_hiragana(c):
	code = ord(c)
	return code >= 0x3040 and code <= 0x309f

def is_katakana(c):
	code = ord(c)
	return code >= 0x30a1 and code <= 0x30fe

def is_kana(c):
	code = ord(c)
	return (code >= 0x3040 and code <= 0x309f) or (code >= 0x30a1 and code <= 0x30fe)

def _is_simple_japanese_character(code):
	return ((code >= 0x4e00 and code <= 0x9fa5)
				or (code >= 0x3041 and code <= 0x3096)
				or (code >= 0x30a1 and code <= 0x30fa)
				or code == 0x30fc)

def is_simple_japanese_character(c):
	return _is_simple_japanese_character(ord(c))

def _is_supplementary_japanese_character(code):
	# Only a small portion of this ranges has something to do with Japanese.
	# Care to determine exact boundaries?
	return (
		(code >= 0x3400 and code <= 0x4D85) # CJK extension A
		or
		(code >= 0x20000 and code <= 0x2A6D6) # CJK extension B
		or
		(code >= 0x2A700 and code <= 0x2B734) # CJK extension C
		or
		(code >= 0x2B740 and code <= 0x2B81D) # CJK extension D
		or
		(code >= 0x2B820 and code <= 0x2CEA1) # CJK extension E
		or
		(code >= 0x2CEB0 and code <= 0x2EBE0) # CJK extension F
		or
		(code >= 0x2F800 and code <= 0x2FA1F) # CJK Compatibility Supplement
	)

def is_supplementary_japanese_character(c):
	return _is_supplementary_japanese_character(ord(c))

def is_japanese_character(c):
	code = ord(c)
	return _is_simple_japanese_character(code) or _is_supplementary_japanese_character(code)

def is_english(c):
	code = ord(c)
	return (code >= 65 and code <= 90) or (code >= 97 and code <= 122)

def kata_to_hira(w, full_or_none=False):
	res = []
	for c in w:
		code = ord(c)
		if code >= 0x30a1 and code <= 0x30f3:
			res.append(chr(ord(c) - ord('ァ') + ord('ぁ')))
		elif full_or_none and not is_hiragana(c):
			return w
		else:
			res.append(c)

	return ''.join(res)

def maketmp():
	if not os.path.exists('tmp'):
		os.makedirs('tmp')
	if not os.path.isdir('tmp'):
		raise Exception("`tmp` has to be dir, but it isn't")

_report_time = time.time()
def _download_reporthook(chunk_number, max_chunk_size, download_size):
        global _report_time
        if time.time() - _report_time > 1:
            _report_time = time.time()
            print(f'\r{chunk_number} {max_chunk_size} {download_size}, {100*chunk_number*max_chunk_size/download_size:.2f}%', end='')

def download(url, filename):
	maketmp()
	path = os.path.join('tmp', filename)
	if not os.path.exists(path):
		print(f"Downloading {filename}")
		urllib.request.urlretrieve(url, path, _download_reporthook)
		print(f"\nDownloaded {filename}")
	return path

