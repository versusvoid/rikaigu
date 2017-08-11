#!/usr/bin/env python3
import random

text = """
顔のない人
方向音痴
泣かないで
どうかしたの
届け出ないし
行かなくてもよい
ならないうちに
来たがっている
涼しくてよかった
飲みたくてたまらない
優れなくてそう
誘わなくちゃ
見ていただき
防がねばなりません
しなければならない
奪ったらしい
ＡＶ
林檎
時鳥
蟇蛙
アッパーカット
飛ばす＞飛ばせる
おまんこ
なっちゃうでしょ
逃げちゃう
頭にきていて
頭に来た
投込んだ
身うごき
茗荷谷
成りたち
嘘をついた
血のかよった
手つかず
てつかず ??
身につけた
つき抜ける
気がきく
わかっている
うぬら
いずれ菖蒲かかきつばた
ヴぉろぐだ
ヴォログダ
してくれた
してくれる
"""

tags = [
    'font',
    'tt',
    'i',
    'b',
    'big',
    'small',
    'strike',
    's',
    'u',

    'em',
    'strong',
    'dfn',
    'code',
    'samp',
    'kbd',
    'var',
    'cite',
    'abbr',
    'acronym',

    'a',
    'q',
    'sub',
    'sup',
    'span',
    'wbr',

    'ruby',
    'rb',
	'div class="inline"',
	'div class="inline-block"'
	]

sep = [
	'&#10;',
	'<p>sep</p>',
	'<div style="display: block !important">sep</div>',
	'<hr>',
	'<pre>sep</pre>',
	'<br />'
	]



stack = []
written = False
i = 0
while i < len(text):
	action = random.randrange(0, 4)
	while ((len(stack) == 0 or not written) and action == 2) or (stack[-1:] != ['ruby'] and action == 3):
		action = random.randrange(0, 4)

	if action == 0:
		if text[i] == '\n':
			while len(stack) > 0:
				tag = stack.pop()
				print('</', tag.split()[0], '>', sep='', end='')
			print(random.choice(sep))
		else:
			print(text[i], end='')
		i += 1
		written = True
	elif action == 1:
		tag = random.choice(tags)
		while stack[-1:] == ['ruby'] and tag == 'rb':
			tag = random.choice(tags)
		stack.append(tag)
		print('<', tag, '>', sep='', end='')
		written = False
	elif action == 2:
		tag = stack.pop()
		print('</', tag.split()[0], '>', sep='', end='')
	else:
		assert stack[-1] == 'ruby'
		tag = random.choice(['rp', 'rt'])
		print('<', tag, '>', chr(random.choice(range(42, 120))), '</', tag, '>', sep='', end='')

