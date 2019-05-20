"use strict";

function clearHighlight() {
	if ('oldSelectionStart' in rikaigu) {
		document.activeElement.selectionStart = rikaigu.oldSelectionStart;
		delete rikaigu.oldSelectionStart;
		document.activeElement.selectionEnd = rikaigu.oldSelectionEnd;
		delete rikaigu.oldSelectionEnd;
	}

	if (rikaigu.oldActiveElement) {
		if (rikaigu.oldActiveElement === document.body) {
			document.activeElement.blur();
		} else {
			rikaigu.oldActiveElement.focus();
		}
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

function highlightMatch(matchLength, selectionRange) {
	if (!rikaigu.config.matchHighlight || rikaigu.mousePressed) return true;

	if (selectionRange.constructor === Array) {
		return highlightRange(matchLength, selectionRange);
	} else {
		return highlightInput(matchLength, selectionRange.rangeNode, selectionRange.offset);
	}
}

function highlightInput(matchLength, input, offset) {
	if (!document.body.contains(input)) return false;
	if (!isHighlightableInput(input)) return true;

	if (offset + matchLength > input.value.length) {
		console.error('Invalid input', input, 'selectionRange:', offset, matchLength);
		return false;
	}
	if (document.activeElement !== input) {
		rikaigu.oldActiveElement = document.activeElement;
	}
	rikaigu.oldSelectionStart = input.selectionStart;
	rikaigu.oldSelectionEnd = input.selectionEnd;
	input.selectionStart = offset;
	input.selectionEnd = offset + matchLength;
	input.focus();
	return true;
}

function highlightRange(matchLength, selectionRange) {
	if (!document.body.contains(selectionRange[0].rangeNode)) return false;

	let requiredLength = matchLength;
	let i = 0;
	while (i < selectionRange.length - 1 && selectionRange[i].endIndex - selectionRange[i].offset < requiredLength) {
		requiredLength -= selectionRange[i].endIndex - selectionRange[i].offset;
		++i;
	}
	const endNode = selectionRange[i].rangeNode;
	const endOffset = Math.min(selectionRange[i].offset + requiredLength, selectionRange[i].endIndex);

	if (isHighlightableInput(document.activeElement)) {
		rikaigu.oldActiveElement = document.activeElement;
		rikaigu.oldActiveElementSelectionStart = rikaigu.oldActiveElement.selectionStart;
		rikaigu.oldActiveElementSelectionEnd = rikaigu.oldActiveElement.selectionEnd;
	}

	const selection = window.getSelection();
	if (selection.rangeCount > 0) {
		rikaigu.oldRange = selection.getRangeAt(0);
		selection.removeAllRanges();
	}

	var range = document.createRange();
	range.setStart(selectionRange[0].rangeNode, selectionRange[0].offset);
	range.setEnd(endNode, endOffset);
	selection.addRange(range);
	rikaigu.selected = true;
	return true;
}
