import os
import urllib.request
from collections import namedtuple
import gzip
import xml.etree.ElementTree as ET

def is_kanji(c):
	code = ord(c)
	return (code >= 0x4e00 and code <= 0x9fa5) or code > 0xffff # last one isn't good enough in case of ja.wiktionary

def is_hiragana(c):
	code = ord(c)
	return code >= 0x3040 and code <= 0x309f

def is_katakana(c):
	code = ord(c)
	return code >= 0x30a1 and code <= 0x30fe

def is_japanese_character(c):
	code = ord(c)
	return ((code >= 0x4e00 and code <= 0x9fa5) or code > 0xffff
				or (code >= 0x3041 and code <= 0x3096)
				or (code >= 0x30a1 and code <= 0x30fa))

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

def download(url, filename):
	maketmp()
	path = os.path.join('tmp', filename)
	if not os.path.exists(path):
		print(f"Downloading {filename}")
		urllib.request.urlretrieve(url, path)
		print(f"Downloaded {filename}")
	return path

