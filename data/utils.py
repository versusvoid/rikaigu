import os
import subprocess
import builtins
import itertools

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

_e_row = set('え け げ せ ぜ て で ね へ べ ぺ め 　 　 れ ゑ'.split())
_o_row = set('お こ ご そ ぞ と ど の ほ ぼ ぽ も よ ょ ろ'.split())
_long_vowel_mark_mapping = dict(itertools.chain(
	map(lambda k: (k, 'あ'), 'あ か が さ ざ た だ な は ば ぱ ま や ゃ ら わ'.split()),
	map(lambda k: (k, 'い'), 'い き ぎ し じ ち ぢ に ひ び ぴ み 　 　 り ゐ'.split()),
	map(lambda k: (k, 'う'), 'う く ぐ す ず つ づ ぬ ふ ぶ ぷ む ゆ ゅ る'.split()),
	map(lambda k: (k, 'い'), _e_row),
 	map(lambda k: (k, 'う'), _o_row),
	map(lambda k: (k, 'ー'), 'ぁ ぃ ぅ ぇ ぉ ゔ ゎ'.split()),
))
def kata_to_hira(w, agressive=True):
	res = []
	for c in w:
		code = ord(c)
		if code >= 0x30a1 and code <= 0x30f6:
			res.append(chr(ord(c) - ord('ァ') + ord('ぁ')))
		elif c == 'ー' and len(res) > 0 and res[-1] in _long_vowel_mark_mapping:
			res.append(_long_vowel_mark_mapping[res[-1]])
		else:
			res.append(c)

		if agressive:
			if res[-1] == 'を':
				res[-1] = 'お'
			if res[-1] == 'づ':
				res[-1] = 'ず'
			if res[-1] == 'は':
				res[-1] = 'わ'

			if len(res) > 1:
				if res[-1] == 'お' and res[-2] in _o_row:
					res[-1] = 'う'
				if res[-1] == 'え' and res[-2] in _e_row:
					res[-1] = 'い'

	return ''.join(res)

assert kata_to_hira('ぶっとおし') == 'ぶっとうし', kata_to_hira('ぶっとおし')

def download(url, filename):
	path = os.path.join('tmp', filename)
	if not os.path.exists(path):
		print(f"Downloading {filename}")
		tmp_path = path + '-part'
		subprocess.check_call(
			['curl', '-C', '-', url, '-o', tmp_path, '--create-dirs'],
			universal_newlines=True
		)
		os.rename(tmp_path, path)
		print(f"\nDownloaded {filename}")
	return path
