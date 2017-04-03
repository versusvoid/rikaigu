"use strict";

function clearHighlight() {
	if ('oldSelectionStart' in rikaigu) {
		document.activeElement.selectionStart = rikaigu.oldSelectionStart;
		delete rikaigu.oldSelectionStart;
		document.activeElement.selectionEnd = rikaigu.oldSelectionEnd;
		delete rikaigu.oldSelectionEnd;
	}

	if (rikaigu.oldActiveElement) {
		rikaigu.oldActiveElement.focus();
		if ('oldActiveElementSelectionStart' in rikaigu) {
			rikaigu.oldActiveElement.selectionStart = rikaigu.oldActiveElementSelectionStart;
			delete rikaigu.oldActiveElementSelectionStart;
			rikaigu.oldActiveElement.selectionEnd = rikaigu.oldActiveElementSelectionEnd;
			delete rikaigu.oldActiveElementSelectionEnd;
			rikaigu.selected = false;
		}
		delete rikaigu.oldActiveElement;
	}

	if (rikaigu.selected) {
		var selection = window.getSelection();
		selection.removeAllRanges();
		if (rikaigu.oldRange) {
			selection.addRange(rikaigu.oldRange);
			delete rikaigu.oldRange;
		}
		rikaigu.selected = false;
	}
}

function isHighlightableInput(input) {
	return input.nodeName === 'TEXTAREA' || (input.nodeName === 'INPUT' && input.type === 'text');
}

function highlightMatch(matchLength, prefixLength, selectionRange, prefixSelectionRange) {
	if (!rikaigu.config.matchHighlight || rikaigu.mousePressed) return true;

	if (selectionRange.constructor === Array) {
		return highlightRange(matchLength, prefixLength, selectionRange, prefixSelectionRange);
	} else {
		return highlightInput(matchLength, prefixLength, selectionRange.rangeNode, selectionRange.offset);
	}
}

function highlightInput(matchLength, prefixLength, input, offset) {
	if (!document.body.contains(input)) return false;
	if (!isHighlightableInput(input)) return true;

	if (offset + matchLength > input.value.length || offset - prefixLength < 0) {
		console.error('Invalid input', input, 'selectionRange:', offset, matchLength, prefixLength);
		return false;
	}
	if (document.activeElement !== input) {
		rikaigu.oldActiveElement = document.activeElement;
	}
	rikaigu.oldSelectionStart = input.selectionStart;
	rikaigu.oldSelectionEnd = input.selectionEnd;
	input.selectionStart = offset - prefixLength;
	input.selectionEnd = offset + matchLength;
	input.focus();
	return true;
}

function highlightRange(matchLength, prefixLength, selectionRange, prefixSelectionRange) {
	if (!document.body.contains(selectionRange[0].rangeNode)) return false;

	var requiredLength = prefixLength;
	var i = 0;
	while (i < prefixSelectionRange.length && prefixSelectionRange[i].offset - prefixSelectionRange[i].endIndex < requiredLength) {
		requiredLength -= prefixSelectionRange[i].offset - prefixSelectionRange[i].endIndex;
		++i;
	}
	var startNode = prefixSelectionRange[i].rangeNode,
		startOffset = Math.max(prefixSelectionRange[i].offset - requiredLength, 0);

	requiredLength = matchLength;
	i = 0;
	while (i < selectionRange.length && selectionRange[i].endIndex - selectionRange[i].offset < requiredLength) {
		requiredLength -= selectionRange[i].endIndex - selectionRange[i].offset;
		++i;
	}
	var endNode = selectionRange[i].rangeNode,
		endOffset = Math.min(selectionRange[i].offset + requiredLength, selectionRange[i].endIndex);

	if (isHighlightableInput(document.activeElement)) {
		rikaigu.oldActiveElement = document.activeElement;
		rikaigu.oldActiveElementSelectionStart = rikaigu.oldActiveElement.selectionStart;
		rikaigu.oldActiveElementSelectionEnd = rikaigu.oldActiveElement.selectionEnd;
	}

	var selection = window.getSelection();
	if (selection.rangeCount > 0) {
		rikaigu.oldRange = selection.getRangeAt(0);
		selection.removeAllRanges();
	}

	var range = document.createRange();
	range.setStart(startNode, startOffset);
	range.setEnd(endNode, endOffset);
	selection.addRange(range);
	rikaigu.selected = true;
	return true;
}
