#!/usr/bin/env python3

import os
import re
import xml.etree.ElementTree as ET
from utils import *

files = {}
for filename in [
		"aux-s-inf.xml",
		"aux.xml",
		"exp-s-inf.xml",
		"bare-exp.xml"]:
	files[filename] = ET.Element('entries')

count = 0
def print_entry(entry, sense_group, filename):
	global count
	count += 1

	root = files[filename]
	elem = ET.SubElement(root, 'entry')
	for k in entry.kanjis:
		kelem = ET.SubElement(elem, 'k')
		if not k.common:
			kelem.set("uncommon", '')
		kelem.text = k.text
	for r in entry.readings:
		relem = ET.SubElement(elem, 'r')
		if len(r.kanjis) != len(entry.kanjis):
			relem.set("kanjis", ','.join(map(str, r.kanjis)))
		relem.text = r.text

	ET.SubElement(elem, 'pos').text = ','.join(sense_group.pos)
	for s in sense_group.senses:
		selem = ET.SubElement(elem, 's')
		if len(s.kanji_restriction) != 0:
			selem.set("kanjis", ','.join(map(str, s.kanji_restriction)))
		if len(s.reading_restriction) != 0:
			selem.set("readings", ','.join(map(str, s.reading_restriction)))
		for m in s.misc:
			ET.SubElement(selem, 'misc').text = m
		for d in s.dialect:
			ET.SubElement(selem, 'dialect').text = d
		for inf in s.s_inf:
			ET.SubElement(selem, 's_inf').text = inf
		for g in s.glosses:
			ET.SubElement(selem, 'gloss').text = g


s_inf_regex = re.compile(r'\b(after|follows|attaches)\b.*?\b(form|stem|noun)\b', re.IGNORECASE)
for entry in dictionary_reader():
	bare_exp = None
	for sense_group in entry.sense_groups:
		if sense_group.pos != ['exp']:
			bare_exp = False
		if bare_exp is None and sense_group.pos == ['exp']:
			bare_exp = True

		aux = None
		exp = False
		for pos in sense_group.pos:
			if pos.startswith('aux'):
				assert aux is None
				#assert len(sense_group.senses) == 1, entry
				aux = pos
			exp = exp or pos == 'exp'

		have_s_inf = False
		for sense in sense_group.senses:
			if len(sense.s_inf) > 0 and s_inf_regex.search(sense.s_inf[0]) is not None:
				have_s_inf = True
				break

		if aux is not None:
			if have_s_inf:
				print_entry(entry, sense_group, "aux-s-inf.xml")
			else:
				print_entry(entry, sense_group, "aux.xml")
		if exp and have_s_inf:
				print_entry(entry, sense_group, "exp-s-inf.xml")
				bare_exp = False
	if bare_exp:
			print_entry(entry, entry.sense_groups[0], "bare-exp.xml")

print(count)
for filename, root in files.items():
	with open(os.path.join('tmp', filename), 'w') as f:
		level = 0
		for l in ET.tostringlist(root, encoding="unicode"):
			if l.startswith('<'):
				if l[1] != '/':
					print(file=f)
					last_open = l[1:]
					level += 1
					print('\t'*level, end='', file=f)
				else:
					if l[2:-1] != last_open:
						print(file=f)
						print('\t'*level, end='', file=f)
					level -= 1
			print(l, sep='', end='', file=f)
