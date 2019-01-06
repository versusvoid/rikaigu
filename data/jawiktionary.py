#!/usr/bin/env python3
from utils import kata_to_hira, is_kanji, is_japanese_character, download
import dictionary

from collections import namedtuple
import xml.etree.ElementTree as ET
import bz2
import os
import subprocess
import traceback
import enum
import itertools
import sys

import mwparserfromhell as MW
Wikicode = MW.wikicode.Wikicode

Heading = MW.nodes.heading.Heading
Wikilink = MW.nodes.wikilink.Wikilink
Tag = MW.nodes.tag.Tag
Template = MW.nodes.template.Template
Text = MW.nodes.text.Text
Comment = MW.nodes.comment.Comment
ExternalLink = MW.nodes.external_link.ExternalLink

pos_headings = {
	'{{noun}}': {'n'},
	'名詞': {'n'},
	'固有名詞': {'n-pr'},

	'{{adverb}}': {'adv'},
	'副詞': {'adv'},

	'{{interjection}}': {'int'},
	'感動詞': {'int'},

	'{{adj}}': {'adj-i'},
	'{{adjective}}': {'adj-i'},
	'形容詞': {'adj-i'},

	'{{adjectivenoun}}': {'adj-na'},
	'{{Adjectival noun}}': {'adj-na'},
	'形容動詞': {'adj-na'},

	'{{parti}}': {'prt'},
	'{{particle}}': {'prt'},
	'助詞': {'prt'},
	'終助詞': {'prt'},

	'{{auxverb}}': {'aux-v'},
	'助動詞': {'aux-v'},

	'{{pronoun}}': {'pn'},
	'タ名詞': {'pn'},
	'代名詞': {'pn'},
	'人称代名詞': {'pn'},

	'{{verb}}': {'v'},
	'動詞': {'v'},

	'{{suffix}}': {'suf'},
	'{{prefix}}': {'pref'},
	'接頭語': {'pref'},
	'{{abbr}}': {'abbr'},

	'{{preposition}}': set(),
	'前置詞': set(),
	'意味': set(),

	# TODO only if there is no other
	# Or if there is only one match in jmdict
	'成句': set(),
	'{{idiom}}': set(),
}
other_headings = {
	'{{trans}}', '{{prov}}',
	# TODO maybe use?
	'読み', '{{pron}}', '発音',

	'訳語', '熟語', '類義語',
	'文字コード', '同音の漢字',
	'アクセント', '{{etym}}',
	'関連語句', '{{name}}',
	'造語成分', '{{rel}}'
}
def is_pos_heading(title, page_title):
	if '・' in title:
		return all([is_pos_heading(part, page_title) for part in title.split('・')])

	if title in pos_headings:
		return True
	if title in other_headings:
		return False

	i = title.find('：')
	if i == -1:
		i = title.find(':')
	if i > 0:
		title = title[0:i]
		if title in pos_headings:
			return True

	print(f'Unknown heading ==={title}=== on page {page_title}.')
	sys.exit(1)
	answer = 'wtf'
	while answer.strip().lower() not in ('y', 'n', ''):
		answer = input('POS? [Y/n]: ')
	if answer.strip().lower() == 'n':
		other_headings.add(title)
	else:
		pos_headings[title] = set([input('Which: ')])
		return True

def pos_by_heading(title):
	if '・' in title:
		return set().update(*[pos_by_heading(part) for part in title.split('・')])

	i = title.find('：')
	if i == -1:
		i = title.find(':')
	if i > 0:
		title = title[0:i]
	return pos_headings[title].copy()

_kana_to_latin = {
	'バ': 'b',
	'ガ': 'g',
	'カ': 'k',
	'マ': 'm',
	'ナ': 'n',
	'ラ': 'r',
	'サ': 's',
	'タ': 't',
	'ア': 'u',
}
def pos_by_inf_ja(element):
	if element.name == 'inf-ja-adj':
		if element.params[0] == 'タルト':
			return ['adj-t']
		elif element.params[0] == '形容詞':
			return ['adj-i']
		elif element.params[0] == 'ダ':
			return ['adj-na']
		else:
			raise Exception(f"Unknown adjective inflection: {element}")
	elif element.params[2] in ('上一', '下一'):
		return ['v1']
	elif element.params[2] == '五':
		return ['v5' + _kana_to_latin[element.params[1]]]
	elif element.params[2] == '変':
		if element.params[1] == 'サ':
			return ['vs']
		elif element.params[1] == 'カ':
			return ['vk']
		else:
			raise Exception(f"Unknown irregular inflection: {element}")
	else:
		raise Exception(f"Unknown inflection: {element}")

def parse_jawiktionary_word(title, content):
	headers = ['== 日本語 ==', '==日本語==', '== {{jpn}} ==', '=={{jpn}}==', '== {{ja}} ==', '=={{ja}}==', ]
	if all([h not in content for h in headers]):
		return None

	carry_info = {'candidates': {}}
	for c in dictionary.find_entry(title, None):
		carry_info['candidates'][id(c)] = c

	if len(carry_info['candidates']) == 0:
		return None

	try:
		p = MW.parse(content)
	except:
		print(f"Error parsing page {title}: {traceback.format_exc()}", file=sys.stderr)
		return None

	japanese_words = p.get_sections(levels=[2], matches="(日本語|{{jpn}}|{{ja}})")
	assert len(japanese_words) <= 1, f"More than two japanese level-2 headings on page {title}\n\n{content}"
	if len(japanese_words) == 0:
		return None

	s = japanese_words[0]
	pos_sections = []
	for subsection in s.get_sections(levels=[3]):
		heading_title = subsection.nodes[0].title
		for t in heading_title.filter_templates():
			t.params.clear()
		heading_title = heading_title.strip()
		if is_pos_heading(heading_title, title):
			pos_sections.append((subsection, heading_title))

	if len(pos_sections) == 0:
		print(f'No pos subsections in japanese section of page {title}', file=sys.stderr)
		return None

	entries = []
	for subsection, heading_title in pos_sections:
		try:
			extract_entry_from_subsection(title, subsection, heading_title, carry_info, entries)
		except Exception:
			print(f"Wasn't able to extract entry from {subsection.nodes[0]} on page {title}:\n",
				traceback.format_exc(), file=sys.stderr)
			print('-------------------------------', f"All candidates:", *carry_info['candidates'].values(), sep='\n')
			answer = 'wtf'
			while answer.strip().lower()[:1] not in ['y', 'n', '']:
				answer = input('Continue? [Y/n]: ')
			if answer.strip().lower()[:1] == 'n':
				raise
			print('-------------------------------------------------------------------------')

	return entries

def filter_candidates_by_pos(candidates, poses):
	to_remove = set()
	for key, c in candidates.items():
		found = False
		for sg in c.sense_groups:
			for pos in poses:
				if pos in sg.pos:
					found = True
					break
				if pos == 'v5r' and ('v5aru' in sg.pos or 'v5r-i' in sg.pos):
					found = True
					break
				if pos == 'v5u' and 'v5u-s' in sg.pos:
					found = True
					break
				if pos == 'v5k' and 'v5k-s' in sg.pos:
					found = True
					break
				if pos == 'vs' and ('vs-s' in sg.pos or 'vs-i' in sg.pos):
					found = True
					break

		if not found:
			to_remove.add(key)

	for key in to_remove:
		candidates.pop(key)

	if len(candidates) == 0:
		raise Exception("No candidates left (after pos filter)")

def filter_candidates(writing_or_reading, candidates):
	to_remove = set()
	for key, c in candidates.items():
		found = False
		for k in c.kanjis:
			if kata_to_hira(k.text) == kata_to_hira(writing_or_reading):
				found = True
				break

		if found:
			continue

		for r in c.readings:
			if kata_to_hira(r.text) == kata_to_hira(writing_or_reading):
				found = True
				break

		if not found:
			to_remove.add(key)

	for key in to_remove:
		candidates.pop(key)

	if len(candidates) == 0:
		raise Exception("No candidates left (after writing/reading filter)")

def filter_candidates_cumulatively(writings, readings, candidates):
	to_remove = set()
	for key, c in candidates.items():
		if len(c.kanjis) + len(writings) > 0 and len(writings.intersection(map(lambda k: k.text, c.kanjis))) == 0:
			to_remove.add(key)
			continue

		if len(c.readings) + len(writings) > 0 and len(readings.intersection(map(lambda k: k.text, c.readings))) == 0:
			to_remove.add(key)

	for key in to_remove:
		candidates.pop(key)

	if len(candidates) == 0:
		raise Exception(f"No candidates left (after writing and reading cumulative filter): {writings} {readings}")

def filter_candidates_by_heading(subsection_title, subsection_info):
	if '：' not in subsection_title and ':' not in subsection_title:
		return

	start = subsection_title.find('：')
	if start == -1:
		start = subsection_title.find(':')
	start += 1

	while start < len(subsection_title) and not is_japanese_character(subsection_title[start]):
		start += 1

	end = len(subsection_title) - 1
	while end > start and not is_japanese_character(subsection_title[end]):
		end -= 1

	if end <= start:
		return

	specialization = subsection_title[start:end + 1].strip().split('/')
	if len(specialization) == 1:
		specialization = specialization[0].split('・')

	for element in specialization:
		assert all(map(is_japanese_character, element)), subsection_title
		filter_candidates(element, subsection_info['candidates'])
		if any([is_kanji(c) for c in element]):
			subsection_info['writings'].add(element)
		else:
			subsection_info['readings'].add(element)

class SubsectionPosition(enum.Enum):
	START = 0
	CATEGORY_LINKS = 1
	WRITING_AND_READING = 2
	SENSE = 3
	END = 4

def extract_entry_from_subsection(page_title, subsection, subsection_title, carry_info, entries):

	subsection_info = {
		'candidates': carry_info['candidates'].copy(),
		'writings': set(),
		'readings': set(),
		'pos': pos_by_heading(subsection_title),
	}

	if any([is_kanji(c) for c in page_title]):
		subsection_info['writings'].add(page_title)
	else:
		subsection_info['readings'].add(page_title)

	filter_candidates_by_heading(subsection_title, subsection_info)
	state = SubsectionPosition.START

	for i, element in enumerate(subsection.nodes[1:]):
		t = type(element)
		if t == Heading:
			break
		elif t == Comment:
			continue
		elif t == Text and all([c == '\n' for c in element.value]):
			continue

		new_state = transition(state, element, t)
		if new_state is not None:
			state = new_state

		if (state, t) in _wikinode_actions:
			_wikinode_actions[(state, t)](page_title, element, subsection_info, i + 1,
					subsection, carry_info, entries)
		else:
			error_message = f"Unexpected state-type pair ({state}, {t}) on page {page_title}. Element: \n{element}"
			print(error_message, file=sys.stderr)
			answer = 'wtf'
			while answer.strip().lower()[:1] not in ['y', 'n', '']:
				answer = input('Continue? [Y/n]: ')
			if answer.strip().lower()[:1] == 'n':
				raise BaseException(error_message)

	parse_wr(subsection_info)
	end_sense(subsection_info)

	if len(subsection_info['candidates']) > 1:
		print(page_title, 'WR = ', subsection_info.get('wr'))
		filter_candidates_cumulatively(subsection_info['writings'], subsection_info['readings'],
				subsection_info['candidates'])

	if len(subsection_info['candidates']) > 1:
		filter_candidates_by_pos(subsection_info['candidates'], subsection_info['pos'])
	if len(subsection_info['candidates']) == 0:
		raise Exception(f"Can't find entry for subsection {subsection_title} on page {page_title}")
	elif len(subsection_info['candidates']) > 1:
		raise Exception("Ambigious entry for in subsection {subsection_title} on page {page_title}:\n" +
				"\n".join(map(str, subsection_info['candidates'].values())))
	else:
		entries.extend(subsection_info['candidates'])

def transition(state, element, t):
	if state.value <= SubsectionPosition.START.value:
		if t == Template and element.name.lower() == 'wikipedia':
			return SubsectionPosition.CATEGORY_LINKS
		if t == Wikilink and (element.title.lower().startswith('category') or element.title.startswith("カテゴリ")):
			return SubsectionPosition.CATEGORY_LINKS

	if state.value <= SubsectionPosition.CATEGORY_LINKS.value:
		if t == Template and (element.name.lower() in ('infl', 'jachar', 'jachars')):
			return SubsectionPosition.WRITING_AND_READING
		if t == Tag and element.tag == 'b':
			return SubsectionPosition.WRITING_AND_READING
		if t == Text:
			return SubsectionPosition.WRITING_AND_READING

	if state.value <= SubsectionPosition.WRITING_AND_READING.value:
		if t == Tag and element.tag == 'li':
			return SubsectionPosition.SENSE

	if state.value <= SubsectionPosition.SENSE.value:
		if t == Template and element.name.startswith('inf-ja'):
			return SubsectionPosition.END
		if t == Tag and element.tag == 'hr':
			return SubsectionPosition.END

	return None

def template_in_links(page_title, element, subsection_info, i, subsection, carry_info, entries):
	if element.name.strip().lower() == 'wikipedia':
		pass
	else:
		raise Exception(f"Unexpected template {element} in links on page {page_title}")

def link_in_links(page_title, element, subsection_info, i, subsection, carry_info, entries):
	title = element.title.lower()
	if title.startswith('category') or title.startswith("カテゴリ"):
		if element.text is not None and (':{{ja}}' in title or ':{{jpn}}' in title or ':日本語' in title):
			text = element.text.strip()
			if all([is_japanese_character(c) for c in text]):
				if any([is_kanji(c) for c in text]):
					subsection_info['writings'].add(text)
				else:
					subsection_info['readings'].add(text)
	else:
		raise Exception(f"Unexpected link {element} in links on page {page_title}")

def determine_writing_reading_order(writing_or_reading, subsection_info):
	if any([is_kanji(c) for c in writing_or_reading]):
		subsection_info['writings'].add(writing_or_reading)
		subsection_info['readings after writings'] = True
	else:
		subsection_info['readings'].add(writing_or_reading)
		subsection_info['readings after writings'] = False

def parse_wr(subsection_info):
	if 'wr' not in subsection_info:
		return

	if len(subsection_info['candidates']) < 2:
		# I'm too lazy and there is no need
		return

	"""
	1) '''[[保]] [[護]]'''（[[ほご]]）
	1.1) '''ポーランド[[語]]'''（-ご）
	1.2) '''ペルシア語'''（-ゴ　表記・発音のゆれ　'''ペルシャ語'''）
	1.3) {{jachar|六|月}}（ろくがつ / [[みなづき]]）
	1.4) '''[[小]] [[豆]]'''（一般的な読み:[[あずき]]、専門的な読み:しょうず）
	1.5) {{jachar|一|富|士|二|鷹|三|茄|子}} （一富士・二鷹・三茄子、一・[[富士]]・二・鷹・三・[[茄子]]　いちふじ にたか さんなすび）
	1.6) '''{{ふりがな|下手|へた}}の{{おくりがな2|長|なが||ながい}}{{ふりがな|談義|だんぎ|yomilink=n}}'''（一部には「下手な長談義」とも）
	1.7) '''[[はり]]'''{{jachar|師}}（-し、[[鍼]]師、[[針]]師）
	1.8) '''ほろほろ[[鳥]]'''（－チョウ、異表記:[[珠鶏]]）
	1.9) '''クムク [[語]]'''（-ご　表記のゆれ:クミィク語）
	1.10) '''グラゴル'''{{jachar|文|字}}(－[[文字]]、－もじ）
	1.11) '''[[日]][[本]][[人]]'''（[[にほんじん]] (nihonjin), [[にっぽんじん]] (nipponjin)）
	1.12) '''[[虎]] [[穴]] [[虎]] [[子]]'''（[[こ]] [[けつ]] [[こ]] [[し]]、または[[じ]]）
	1.13) '''[[朝鮮]] [[語]]'''（ちょうせん ご）
	1.14) '''[[御]] [[名]]'''（[[ぎょめい]] [[みな]] [[おんな]] [[おな]]）
	1.15) '''[[満]][[州]][[語]]'''（[[満州]]（[[満洲]]）・語　まんしゅうご）
	1.16) あなた（彼方、貴方、貴男、貴女）

	2) {{infl|jpn|noun}}【[[色]]】
	2.1) '''とる'''【[[取]]る（一般的用字）, [[録]]る, [[撮]]る, [[摂]]る, [[採]]る, [[盗]]る, [[捕]]る, [[穫]]る, [[獲]]る, [[執]]る, [[脱]]る, [[操]]る】
	2.2) '''{{PAGENAME}}'''【[[晴]]る・[[霽]]る】
	2.3) '''{{PAGENAME}}'''【[[雛]] [[霰]]】
	2.4) '''{{PAGENAME}}'''【漢字表記: [[老檛]]】
	2.5) '''{{PAGENAME}}'''【[[泡]] [[沫]]】（表外）
	2.6) '''{{PAGENAME}}'''【[[寿]][[司]] / [[鮨]] / [[鮓]]】
	2.7) '''[[奈]][[辺]]'''【なへん　異表記:[[那辺]]】
	2.8) '''{{PAGENAME}}'''【[[売]]（り）[[上]]（げ）】
	2.9) [[雲]][[泥]]【うんでい】
	2.10) '''[[馘]][[首]]'''【かくしゅ　意訳して「[[くび]]」】
	2.11) {{infl|jpn|動詞 活用形}}【'''[[沸]]く'''、'''[[湧]]く'''、'''[[涌]]く'''】の連用形。
	2.12) '''{{PAGENAME}}'''【[[豌豆]] [[豆]]:[[豌豆豆]]】
	2.13) '''{{PAGENAME}}'''【[[JIS]][[マーク]]】

	3) '''[[覆]] [[水]]（ふくすい）[[盆]]（ぼん）に{{おくりがな2|返|かえ|ら|かえる}}[[ぬ|ず]]'''
	3.1) '''{{PAGENAME}}'''【[[逢]] [[魔]] [[時]]】、'''おおまがとき'''【[[大]] [[禍]] 時】

	4) '''ブラジル人'''（-じん）【[[伯剌西爾]]人】

	5) '''【[[本]][[鮪]]】''' （ほんまぐろ）
	"""
	text = ''.join(subsection_info['wr']).strip()
	if text == '':
		return

	parts = ['']
	opening2closing_brackets = {'[': ']', '【': '】', '(': ')', '（': '）'}
	closing2opening_brackets = {']': '[', '】': '【', ')': '(', '）': '（'}
	brackets_stack = []
	for c in text:
		if c in opening2closing_brackets:
			brackets_stack.append(c)
			if len(brackets_stack) == 1:
				parts.append(c)
				parts.append('')
			else:
				parts[-1] += c
		elif c in closing2opening_brackets:
			assert len(brackets_stack) > 0, f'Invalid WR bracket sequence: {text}'
			assert closing2opening_brackets[c] == brackets_stack[-1], f'Invalid WR bracket sequence: {text}'
			brackets_stack.pop()
			if len(brackets_stack) == 0:
				parts.append(c)
				parts.append('')
		else:
			parts[-1] += c

	if parts[-1] == '':
		parts.pop()

	assert len(parts[0]) > 0, f'Bracket right from start in WR: {text}'

	'''
		S -> EL S
		S -> EL
		EL -> J
		EL -> J （EVERYTHING）【WRITING】
		EL -> J （EVERYTHING）
		EL -> J 【WRITING】（EVERYTHING）
		EL -> J 【WRITING】
		EVERYTHING -> ???
		WRITING -> ?
		J -> kanji-or-kana J
		J -> kanji-or-kana
	'''

	elements = []
	i = 0
	while i < len(parts):
		if parts[i] in opening2closing_brackets:
			if parts[i] in '(（':
				elements[-1][1] = parts[i+1]
			else:
				elements[-1][2] = parts[i+1]
			i += 3
		else:
			elements.append([parts[i].strip(), None, None])
			i += 1

	try:
		extracted_elements = list(map(lambda el: parse_wr_element(*el), elements))

		assert len(extracted_elements) == 1
		if len(extracted_elements[0].writings) > 0:
			text = list(extracted_elements[0].writings)[0]
			filter_candidates(text, subsection_info['candidates'])
			subsection_info['writings'].add(text)
		if len(extracted_elements[0].readings) > 0:
			text = list(extracted_elements[0].readings)[0]
			filter_candidates(text, subsection_info['candidates'])
			subsection_info['readings'].add(text)
	except:
		print(f"Need to parse wr:\n{subsection_info['wr']} {repr(text)} {parts} {elements}",
				*subsection_info['candidates'].values(), sep='\n')
		raise


	# TODO analyze me

WR = namedtuple('WR', 'writings, readings')
def parse_wr_element(base, readings_or_whatever, writings_or_whatever):
	assert len(base) > 0
	writings = set()
	readings = set()
	if any([is_kanji(c) for c in base]):
		writings.add(base)
	else:
		readings.add(base)

	if readings_or_whatever is not None:
		# FIXME so the あなた page has all four writings in one entry but JMdict has two entries. How you're going to handle this??
		raise NotImplementedError()

	if writings_or_whatever is not None:
		if all([is_japanese_character(c) for c in writings_or_whatever]):
			if any([is_kanji(c) for c in writings_or_whatever]):
				writings.add(writings_or_whatever)
			else:
				readings.add(writings_or_whatever)
		else:
			raise NotImplementedError()

	return WR(writings, readings)

def template_in_wr(page_title, element, subsection_info, i, subsection, carry_info, entries):
	name = element.name.lower()
	if name.lower() in ('infl', 'head', 'pagename'):
		subsection_info.setdefault('wr', []).append(page_title)
	elif name.startswith('jachar'):
		subsection_info.setdefault('wr', []).append(''.join(map(lambda p: p.value.strip_code(), element.params)))
	elif name == 'ふりがな':
		wr = subsection_info.setdefault('wr', [])
		wr.append(element.params[0])
		wr.append('（')
		wr.append(element.params[1])
		wr.append('）')
	elif name == 'おくりがな':
		wr = subsection_info.setdefault('wr', [])
		wr.append(element.params[0])
		wr.append('（')
		wr.append(element.params[2][:-len(element.params[1])])
		wr.append('）')
		wr.append(element.params[1])
	elif name == 'おくりがな2':
		wr = subsection_info.setdefault('wr', [])
		wr.append(element.params[0])
		wr.append('（')
		wr.append(element.params[1])
		wr.append('）')
		wr.append(element.params[2])
	elif name == 'おくりがな3':
		wr = subsection_info.setdefault('wr', [])
		wr.append(element.params[0])
		wr.append('（')
		wr.append(element.params[1])
		wr.append('）')
		wr.append(element.params[2])
		wr.append(element.params[3])
		wr.append('（')
		wr.append(element.params[4])
		wr.append('）')
		wr.append(element.params[5])
	else:
		raise Exception(f"Unexpected template {element} in wr on page {page_title}")

def text_in_wr(page_title, element, subsection_info, i, subsection, carry_info, entries):
	subsection_info.setdefault('wr', []).append(element.value)

def tag_in_wr(page_title, element, subsection_info, i, subsection, carry_info, entries):
	if element.tag == 'b':
		for subelem in element.contents.nodes:
			_wikinode_actions[(SubsectionPosition.WRITING_AND_READING, type(subelem))](page_title, subelem,
					subsection_info, i, subsection, carry_info, entries)
	else:
		raise Exception(f"Unexpected tag {element} in wr on page {page_title}")

def link_to_text(link):
	if link.text is None:
		return link.title.strip_code()
	else:
		return link.text.strip_code()

def link_in_wr(page_title, element, subsection_info, i, subsection, carry_info, entries):
	text = link_to_text(element)
	subsection_info.setdefault('wr', []).append(text)

def end_sense(subsection_info):
	if len(subsection_info.get('current sense', '')) == 0:
		return
	if not subsection_info.get('is example', False):
		subsection_info.setdefault('senses', []).append(''.join(subsection_info['current sense']))
	subsection_info['sense depth'] = 1
	subsection_info['current sense'] = []
	subsection_info['is example'] = False

def tag_in_sense(page_title, element, subsection_info, i, subsection, carry_info, entries):
	if element.tag == 'li':
		if 'current sense' not in subsection_info:
			subsection_info['sense depth'] = 1
			subsection_info['current sense'] = []
		elif len(subsection_info['current sense']) == 0:
			subsection_info['sense depth'] += 1
		else:
			end_sense(subsection_info)
	elif element.tag == 'dd':
		assert len(subsection_info.get('current sense', '')) == 0, f'Stray `dd`: {element} on page {page_title}'
		subsection_info['is example'] = True
	else:
		if element.contents is None:
			raise Exception(f'Empty tag "{element.tag}" {element}')
		subsection_info['current sense'].append(element.contents.strip_code())

def link_in_sense(page_title, element, subsection_info, i, subsection, carry_info, entries):
	subsection_info['current sense'].append(link_to_text(element))

def external_link_in_sense(page_title, element, subsection_info, i, subsection, carry_info, entries):
	if element.title is None:
		pass
	else:
		raise Exception(f"Don't know what to do with external link {element} at page {page_title}")

def template_in_sense(page_title, element, subsection_info, i, subsection, carry_info, entries):
	if element.name.lower() in ('w', 'ふりがな', 'ruby'):
		subsection_info['current sense'].append(element.params[0].value.strip_code())
	elif element.name == 'おくりがな2':
		subsection_info['current sense'].append(element.params[0].value.strip_code())
		subsection_info['current sense'].append(element.params[2].value.strip_code())
	elif element.name.lower() == 'usage':
		subsection_info['current sense'].append('用法')
	else:
		raise Exception(f"Unexpected template {element} in sense on page {page_title}")

def text_in_sense(page_title, element, subsection_info, i, subsection, carry_info, entries):
	subsection_info['current sense'].append(element.value)

def template_at_end(page_title, element, subsection_info, i, subsection, carry_info, entries):
	if element.name.startswith('inf-ja'):
		subsection_info['pos'].update(pos_by_inf_ja(element))
	else:
		raise Exception(f"Unexpected template {element} at end on page {page_title}")

def tag_at_end(page_title, element, subsection_info, i, subsection, carry_info, entries):
	if element.tag == 'hr':
		pass
	else:
		raise Exception(f"Unexpected tag {element.tag} '{element}' at end on page {page_title}")

_wikinode_actions = {
	(SubsectionPosition.CATEGORY_LINKS, Template): template_in_links,
	(SubsectionPosition.CATEGORY_LINKS, Wikilink): link_in_links,
	(SubsectionPosition.WRITING_AND_READING, Tag): tag_in_wr,
	(SubsectionPosition.WRITING_AND_READING, Text): text_in_wr,
	(SubsectionPosition.WRITING_AND_READING, Template): template_in_wr,
	(SubsectionPosition.WRITING_AND_READING, Wikilink): link_in_wr,
	(SubsectionPosition.SENSE, Tag): tag_in_sense,
	(SubsectionPosition.SENSE, Wikilink): link_in_sense,
	(SubsectionPosition.SENSE, ExternalLink): external_link_in_sense,
	(SubsectionPosition.SENSE, Template): template_in_sense,
	(SubsectionPosition.SENSE, Text): text_in_sense,
	(SubsectionPosition.END, Template): template_at_end,
	(SubsectionPosition.END, Tag): tag_at_end,
}

def japanese_dictionary_reader():
	dictionary_path = download("https://dumps.wikimedia.org/jawiktionary/latest/jawiktionary-latest-pages-articles-multistream.xml.bz2", "jawiktionary.xml.bz2")
	with bz2.open(dictionary_path, 'rt') as f:
		repack = f.readline().strip() != '<mediawiki>'

	if repack:
		print("Repacking jawiktionary")
		subprocess.check_call(["bash", "-c", f"cat <(echo '<mediawiki>') <(bunzip2 -c {dictionary_path} | tail -n +2) "
				"| bzip2 > tmp/jawiktionary-repack.xml.bz2"])
		os.rename("tmp/jawiktionary-repack.xml.bz2", dictionary_path)

	dictionary.load_dictionary()

	try:
		source = bz2.open(dictionary_path, 'rt')
		for _, elem in ET.iterparse(source):
			if elem.tag == 'page':
				if elem.find("ns").text != '0':
					elem.clear()
					continue

				entries = parse_jawiktionary_word(elem.find('title').text, elem.find("revision").find("text").text)
				if entries is not None:
					yield from entries
				elem.clear()

			elif elem.tag == 'mediawiki':
				elem.clear()
	except BaseException:
		print(f"\nHeadings:\n{pos_headings}\n{other_headings}\n")
		raise

	print(f"Headings:\n{pos_headings}\n{other_headings}")

if __name__ == '__main__':
	for _ in japanese_dictionary_reader():
		pass
