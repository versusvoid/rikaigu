"use strict";

// Good place to use Set? Check https://jsperf.com/set-has-vs-indexof/3 first!
var inlineNodeNames = {
	// text node
	'#text': true,
	// comment node
	'#comment': true,

	// font style
	'FONT': true,
	'TT': true,
	'I': true,
	'B': true,
	'BIG': true,
	'SMALL': true,
	//deprecated
	'STRIKE': true,
	'S': true,
	'U': true,

	// phrase
	'EM': true,
	'STRONG': true,
	'DFN': true,
	'CODE': true,
	'SAMP': true,
	'KBD': true,
	'VAR': true,
	'CITE': true,
	'ABBR': true,
	'ACRONYM': true,

	// special, not included IMG, OBJECT, BR, SCRIPT, MAP, BDO
	'A': true,
	'Q': true,
	'SUB': true,
	'SUP': true,
	'SPAN': true,
	'WBR': true,

	// ruby
	'RUBY': true,
	'RBC': true,
	'RTC': true,
	'RB': true,
	'RT': true,
	'RP': true
};

function isInline(node) {
	return !!inlineNodeNames[node.nodeName] ||
		// Only check styles for elements.
		// Comments do not have getComputedStyle method
		(node.nodeType == Node.ELEMENT_NODE &&
			window.getComputedStyle(node, null).display.startsWith('inline')
		);
}

function nodeFilter(node) {
	if (node.nodeType === Node.ELEMENT_NODE) {
		if (node.nodeName === 'RP' || node.nodeName === 'RT') return NodeFilter.FILTER_REJECT;
		return NodeFilter.FILTER_SKIP;
	}
	return NodeFilter.FILTER_ACCEPT;
}

/*
 * Checks whether character with given code is simple Japanese character (kana or kanji < 0xffff).
 * Corresponds to is_japanese_character() in data/utils.py
 */
function isJapaneseCharacter(code) {
	return (
		(code >= 0x4e00 && code <= 0x9fa5) // kanji
		|| (code >= 0x3041 && code <= 0x3096) // hiragana
		|| (code >= 0x30a1 && code <= 0x30fa) // katakana
		|| (code >= 0xff66 && code <= 0xff9f) // half-width katakana
		|| code == 0x30fc // long vowel mark
	);
}
const endOfContinuousJapaneseTextRegex = /(\s|[^\u4e00-\u9fa5\u3041-\u3096\u30a1-\u30fa\u30fc])/;
const japaneseCharacterBoundaryCondition = {
	endRegex: endOfContinuousJapaneseTextRegex,
	predicate: isJapaneseCharacter,
};

const endOfJapaneseSentenceCharacters = '\t\n\r 　。？！．｡'.split('').map(c => c.charCodeAt(0));
function isJapaneseCharacterOrInSentencePunctuation(code) {
	return isJapaneseCharacter(code) || endOfJapaneseSentenceCharacters.indexOf(code) === -1;
}
const endOfJapaneseSentence = /(\s|[。？！．｡])/;
const japaneseSentenceBoundaryCondition = {
	endRegex: endOfJapaneseSentence,
	predicate: isJapaneseCharacterOrInSentencePunctuation,
}

function getText(rangeNode, maxLength, forward, outText, outSelectionRange, offset, boundaryCondition) {
	var string = rangeNode.data || rangeNode.value || "";
	if (forward) {
		offset = offset || 0;
		var endIndex = Math.min(string.length, offset + maxLength);
		string = string.substring(offset, endIndex);
		var endPos = string.search(boundaryCondition.endRegex);
		var isEdge = false;
		if (endPos !== -1) {
			isEdge = true;
			endIndex = offset + endPos;
			string = string.substring(0, endPos);
		}

		outText.push(string);
		outSelectionRange.push({
			rangeNode,
			offset,
			endIndex,
			isEdge
		});
	} else {
		offset = isNaN(offset) ? string.length : offset;
		var startIndex = Math.max(0, offset - maxLength);
		string = string.substring(startIndex, offset);
		var foundStart = false;
		for (var i = string.length - 1; i >= 0; --i) {
			if (!boundaryCondition.predicate(string.charCodeAt(i))) {
				startIndex += i + 1;
				string = string.substring(i + 1);
				foundStart = true;
				break;
			}
		}
		outText.push(string);
		outSelectionRange.push({
			rangeNode,
			offset,
			endIndex: startIndex,
			isEdge: foundStart
		});
	}
	return outText[outText.length - 1].length;
}

// Gets text from a node.
// Returns a string.
// node: a node
// selEnd: the selection end object will be changed as a side effect
// maxLength: the maximum length of returned string
// xpathExpr: an XPath expression, which evaluates to text nodes, will be evaluated
// relative to "node" argument
function getInlineText(node, maxLength, forward, outText, outSelectionRange, boundaryCondition) {
	if (node.nodeType === Node.COMMENT_NODE || node.nodeName === 'RP' || node.nodeName === 'RT') {
		return 0;
	}

	if (node.nodeType === Node.TEXT_NODE) {
		return getText(node, maxLength, forward, outText, outSelectionRange, 0, boundaryCondition);
	}

	var treeWalker = document.createTreeWalker(node, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, nodeFilter);
	var currentLength = 0;
	node = forward ? treeWalker.firstChild() : treeWalker.lastChild();
	while (currentLength < maxLength && node !== null && !outSelectionRange[outSelectionRange.length - 1].isEdge) {
		currentLength += getText(node, maxLength - currentLength, forward, outText, outSelectionRange, 0,
			boundaryCondition);
		node = forward ? treeWalker.nextNode() : treeWalker.previousNode();
	}

	return currentLength;
}

// Given a node which must not be null,
// returns either the next (previous) sibling or next (previous) sibling of the father or
// next (previous) sibling of the fathers father and so on or null
function getNext(node, forward) {
	var nextNode = forward ? node.nextSibling : node.previousSibling;
	if (nextNode !== null) {
		return isInline(nextNode) ? nextNode : null;
	}

	nextNode = node.parentNode;
	if (nextNode !== null) {
		return isInline(nextNode) ? getNext(nextNode, forward) : null;
	}

	return null;
}

// XPath expression which evaluates to a boolean. If it evaluates to true
// then rikaigu will not start looking for text in this text node.
// Ignore text in RT elements
// https://jsperf.com/xpath-vs-traversal-parent-test
const startElementExpr ='boolean(parent::rp or ancestor::rt)';
const maxWordLength = 13;
function getTextFromRange(rangeNode, offset, forward, forwardMaxLength, boundaryCondition) {
	var text = [], fullSelectionRange = [];
	var maxLength = forward ? forwardMaxLength : 1024;
	if (isInput(rangeNode)) {
		getText(rangeNode, maxLength, forward, text, fullSelectionRange, offset, boundaryCondition);
		return [text[0], fullSelectionRange[0]];
	}

	if (rangeNode.nodeType !== Node.TEXT_NODE)
		return ['', null];

	if (document.evaluate(startElementExpr, rangeNode, null, XPathResult.BOOLEAN_TYPE, null).booleanValue)
		return ['', null];

	var currentLength = getText(rangeNode, maxLength, forward, text, fullSelectionRange, offset, boundaryCondition);
	var nextNode = getNext(rangeNode, forward);
	while (currentLength < maxLength && nextNode !== null && !fullSelectionRange[fullSelectionRange.length - 1].isEdge) {
		currentLength += getInlineText(nextNode, maxLength - currentLength, forward, text, fullSelectionRange,
			boundaryCondition);
		nextNode = getNext(nextNode, forward);
	}

	if (!forward) {
		text.reverse();
	}

	return [text.join(''), fullSelectionRange];
}

var _cache = [];
function _getCacheEntry(boundaryCondition) {
	for (var c of _cache) {
		if (c.boundaryCondition == boundaryCondition) {
			return c;
		}
	}
	_cache.push({
		boundaryCondition: boundaryCondition,
		range: new Range(),
		value: null
	});
	return _cache[_cache.length - 1];
}

function getCurrentWordContext(boundaryCondition = japaneseCharacterBoundaryCondition) {
	const rangeNode = rikaigu.lastShownRangeNode,
		rangeOffset = rikaigu.lastShownRangeOffset;
	if (!rangeNode) {
		console.error("FIXME invalid frame");
		return;
	}
	const cacheEntry = _getCacheEntry(boundaryCondition);
	if (cacheEntry.range.isPointInRange(rangeNode, rangeOffset)) {
		return cacheEntry.value;
	}

	const [text, tailRanges] = getTextFromRange(rangeNode, rangeOffset, true, 100, boundaryCondition);
	var [prefix, headRanges] = getTextFromRange(rangeNode, rangeOffset, false, maxWordLength, boundaryCondition);
	const trimmedPrefix = prefix.trim();
	if (prefix.endsWith(trimmedPrefix)) {
		prefix = trimmedPrefix;
	} else {
		prefix = "";
	}

	if (tailRanges.constructor === Array) {
		cacheEntry.range.setStart(
			headRanges[headRanges.length - 1].rangeNode,
			headRanges[headRanges.length - 1].endIndex
		);
		cacheEntry.range.setEnd(
			tailRanges[tailRanges.length - 1].rangeNode,
			tailRanges[tailRanges.length - 1].endIndex
		);
	} else {
		cacheEntry.range.setStart(headRanges.rangeNode, headRanges.endIndex);
		cacheEntry.range.setEnd(tailRanges.rangeNode, tailRanges.endIndex);
	}

	cacheEntry.value = prefix + text.trim();
	return cacheEntry.value;
}

function getCurrentWordSentence() {
	return getCurrentWordContext(japaneseSentenceBoundaryCondition);
}

var spacePrefixRegexp = /^\s/;
function extractTextAndSearch(rangeNode, rangeOffset) {
	if (!rangeNode) {
		rangeNode = rikaigu.lastShownRangeNode;
		rangeOffset = rikaigu.lastShownRangeOffset;
	}
	if (!rangeNode || !document.body.contains(rangeNode)) {
		return reset();
	}
	var data = rangeNode.data || rangeNode.value;

	var match = data.substring(rangeOffset).match(spacePrefixRegexp);
	if (match !== null) {
		/*
		 * For now match[0].length will always be 1,
		 * but what if one day some wonderspace with
		 * code point > 0xffff will be added to unicode?
		 */
		rangeOffset += match[0].length;
	}

	if (rangeOffset >= data.length) {
		return reset();
	}

	var u = data.codePointAt(rangeOffset);
	if (isNaN(u) ||
		(u != 0x25CB && u < 0x20000 &&
			(u < 0x3001 || u > 0x30FF) &&
			(u < 0x3400 || u > 0x9FFF) &&
			(u < 0xF900 || u > 0xFAFF) &&
			(u < 0xFF10 || u > 0xFF9D))) {
		return reset();
	}

	// Selection end data
	var [text, fullSelectionRange] = getTextFromRange(rangeNode, rangeOffset, true, maxWordLength,
		japaneseCharacterBoundaryCondition);
	text = text.trim();
	if (!text) return reset();

	/* Not used currently.
	var [prefix, prefixSelectionRange] = getTextFromRange(rangeNode, rangeOffset, false);
	var trimmedPrefix = prefix.trim();
	if (prefix.endsWith(trimmedPrefix)) {
		prefix = trimmedPrefix;
	} else {
		prefix = "";
	}
	*/
	var prefix = '';
	var prefixSelectionRange = [{rangeNode, offset: rangeOffset, endIndex: rangeOffset, isEdge: true}];

	chrome.runtime.sendMessage({
			"type": "xsearch",
			"text": text,
			"prefix": prefix,
			"screenX": rikaigu.lastPos.screenX,
			"screenY": rikaigu.lastPos.screenY
		},
		processSearchResult.bind(window, fullSelectionRange, prefixSelectionRange));
}
