"use strict";

/*
	rikaigu
	Extended by Versus Void

	--

	Copyright (C) 2010-2017 Erek Speed
	https://github.com/melink14/rikaikun

	---

	Originally based on Rikaichan 1.07
	by Jonathan Zarate
	http://www.polarcloud.com/

	---

	Originally based on RikaiXUL 0.4 by Todd Rudick
	http://www.rikai.com/
	http://rikaixul.mozdev.org/

	---

	This program is free software; you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation; either version 2 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program; if not, write to the Free Software
	Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

	---

	Please do not change or remove any of the copyrights or links to web pages
	when modifying any of the files. - Jon
*/
var rikaigu = null;
var frameId = null;

function updateConfig() {
	chrome.storage.local.get(null, function(config) {
		if (rikaigu !== null) {
			rikaigu.config = config;
		}
	});
}

function enableTab(config, text) {
	if (rikaigu === null) {
		rikaigu = {
			altView: null,
			keysDown: {},
			lastPos: {
				clientX: 0,
				clientY: 0,
				screenX: 0,
				screenY: 0
			},
			lastTarget: null,
			mousePressed: false,
			mouseOnPopup: false,
			isVisible: false,
			shownMatch: null,
			screenX: 0,
			screenY: 0,
			activeFrame: 0,
			lastRangeNode: "some object that won't be equal neither any node nor null",
			lastRangeOffset: -1,
			config: config
		};
		window.addEventListener('mousemove', onMouseMove, false);
		window.addEventListener('keydown', onKeyDown, true);
		window.addEventListener('keyup', onKeyUp, true);
		window.addEventListener('mousedown', onMouseDown, false);
		window.addEventListener('mouseup', onMouseUp, false);

		if (text) {
			if (!document.hidden && window.self === window.top) {
				rikaigu.altView = 'up';
				showPopup(text);
				rikaigu.altView = null;
			}
			rikaigu.isVisible = true;
		}
	}
}

function disableTab() {
	if (rikaigu !== null) {
		window.removeEventListener('mousemove', onMouseMove, false);
		window.removeEventListener('keydown', onKeyDown, true);
		window.removeEventListener('keyup', onKeyUp, true);
		window.removeEventListener('mosuedown', onMouseDown, false);
		window.removeEventListener('mouseup', onMouseUp, false);

		reset();
		var e = document.getElementById('rikaigu-css');
		if (e) e.parentNode.removeChild(e);
		e = document.getElementById('rikaigu-window');
		if (e) e.parentNode.removeChild(e);

		rikaigu = null;
	}
}

function getContentType() {
	var metas = document.getElementsByTagName('meta');
	for (var meta of metas) {
		if (meta.httpEquiv == 'Content-Type') {
			return meta.content.split(';')[0];
		}
	}
	return null;
}

function makePopup() {
	var css = document.createElementNS('http://www.w3.org/1999/xhtml', 'link');
	css.setAttribute('rel', 'stylesheet');
	css.setAttribute('type', 'text/css');
	css.setAttribute('href', chrome.extension.getURL('css/popup-' + rikaigu.config.popupColor + '.css'));
	css.setAttribute('id', 'rikaigu-css');
	document.getElementsByTagName('head')[0].appendChild(css);

	const popup = document.createElementNS('http://www.w3.org/1999/xhtml', 'div');
	popup.setAttribute('id', 'rikaigu-window');
	popup.classList.add('rikaigu-window');
	popup.addEventListener('mouseenter', _onMouseEnter, false);
	popup.addEventListener('mouseleave', _onMouseLeave, false);
	document.documentElement.appendChild(popup);

	document.addEventListener('click', onClick, false);
	return popup;
}

async function showPopup(text) {
	var popup = document.getElementById('rikaigu-window');
	if (!popup) {
		popup = makePopup();
	} else {
		var href = chrome.extension.getURL('css/popup-' + rikaigu.config.popupColor + '.css');
		var css = document.getElementById('rikaigu-css');
		if (css.getAttribute('href') !== href) {
			css.setAttribute('href', href);
		}
	}

	if (getContentType() == 'text/plain') {
		var df = document.createDocumentFragment();
		df.appendChild(document.createElementNS('http://www.w3.org/1999/xhtml', 'span'));
		df.firstChild.innerHTML = text;

		while (popup.firstChild) {
			popup.removeChild(popup.firstChild);
		}
		popup.appendChild(df.firstChild);
	} else {
		popup.innerHTML = text;
	}

	// popup.style.setProperty('top', `${window.scrollY}px`, 'important');
	// popup.style.setProperty('left', `${window.scrollX}px`, 'important');
	popup.style.setProperty('top', `-1000px`, 'important');
	popup.style.setProperty('left', `0px`, 'important');

	popup.style.removeProperty('display');

	await _updatePopupRect(popup);
}

function toggleHiddenReviewListEntryInfo(node) {
	for (var child of node.children) {
		if (child.classList.contains('rikaigu-review-listed')) {
			child.classList.toggle('rikaigu-hidden');
		}
	}
}

function toggleHiddenAllReviewListEntriesInfo(popup) {
	for (var child of popup.getElementsByTagName('td')) {
		if (rikaigu.config.reviewList[child.getAttribute('id')]) toggleHiddenReviewListEntryInfo(child);
	}
}

function _toggleMoreEntries() {
	for (var el of document.getElementsByClassName('rikaigu-second-and-further')) {
		el.classList.toggle('rikaigu-hidden');
	}
}

function _toggleMoreEntriesButton(button) {
	button.innerHTML = button.innerText.indexOf('▲') !== -1 ? '▼' : '▲';
}

function onClick(ev) {
	if (!rikaigu.isVisible) return;
	if (ev.target.classList.contains('rikaigu-lurk-moar')) {
		console.log(window.getSelection().toString());
		ev.preventDefault();
		_toggleMoreEntries();
		_toggleMoreEntriesButton(ev.target);
		_getPopupAndUpdateItsPosition();
		return;
	}

	const popup = document.getElementById('rikaigu-window');
	let wordNode = ev.target;
	if (!popup.contains(wordNode)) {
		return !window.debugMode ? requestHidePopup() : null;
	}
	while (wordNode !== popup && !wordNode.classList.contains('reviewable')) {
		wordNode = wordNode.parentNode;
	}
	if (wordNode === popup) {
		return;
	}

	console.log('wordNode =', wordNode);
	if (!wordNode.classList.contains('reviewed')) {
		let context = getCurrentWordContext();
		console.log('context:', context);
		for (const el of wordNode.querySelectorAll('.w-kanji, .w-kana')) {
			if (context === el.innerText) {
				console.log('matching context');
				context = '';
				break;
			}
		}

		rikaigu.config.reviewList[wordNode.getAttribute('jmdict-id')] = context;
		wordNode.getElementsByClassName('w-review-context')[0].innerHTML = context;
	} else {
		delete rikaigu.config.reviewList[wordNode.getAttribute('jmdict-id')];
	}

	for (const el of wordNode.getElementsByClassName('rikaigu-review-listed')) {
		el.classList.toggle('rikaigu-hidden');
	}
	wordNode.classList.toggle('reviewed');

	chrome.storage.local.set({reviewList: rikaigu.config.reviewList});
}

const _PADDING_AND_BORDER = 4 + 1;
function _computeFinalPosition(availableWidth, leftRightOrBoth, availableHeight, upDownOrBoth) {
	if (rikaigu.altView === 'up' && (upDownOrBoth & _DIRECTIONS.UP) !== 0) {
		return [window.scrollX, window.scrollY];
	} else if (rikaigu.altView !== null) {
		return [
			(window.innerWidth - availableWidth) + window.scrollX,
			(window.innerHeight - availableHeight) + window.scrollY
		];
	} else {

		let x,y;
		if (leftRightOrBoth === 0) {
			x = (window.innerWidth -  availableWidth) / 2;
		}
		// TODO change defaults for writing-mode: vertical-rl;
		// these defaults are preferable only for horizontal
		else if ((leftRightOrBoth & _DIRECTIONS.RIGHT) !== 0) {
			x = _firstCharacterStart();
		} else {
			x = _lastCharacterEnd() - availableWidth;
		}

		if ((upDownOrBoth & _DIRECTIONS.DOWN) !== 0) {
			y = _characterBottomLine();
		} else {
			y = _characterUpperLine() - availableHeight - _PADDING_AND_BORDER;
		}

		x += window.scrollX;
		y += window.scrollY;
		return [x, y];
	}
}

const _DIRECTIONS = {
	UP   : 0b0001,
	DOWN : 0b0010,
	LEFT : 0b0100,
	RIGHT: 0b1000,
}

function _computeWidthAvailable(requiredWidth) {
	const availableLeft = _lastCharacterEnd();
	const availableRight = window.innerWidth - _firstCharacterStart();
	const availableMax = Math.max(availableLeft, availableRight);
	if (availableMax < requiredWidth) {
		return [Math.min(requiredWidth, window.innerWidth), 0];
	}
	const dir = (availableRight >= requiredWidth ? _DIRECTIONS.RIGHT : 0)
			  | (availableLeft >= requiredWidth ? _DIRECTIONS.LEFT : 0);
	return [Math.min(requiredWidth, availableMax), dir];
}

function _computeHeightAvailable(requiredHeight) {
	const availableUp = _characterUpperLine();
	const availableDown = window.innerHeight - _characterBottomLine();
	const dir = (availableUp >= requiredHeight ? _DIRECTIONS.UP : 0)
			  | (availableDown >= requiredHeight ? _DIRECTIONS.DOWN : 0);
	return [Math.min(requiredHeight, Math.max(availableUp, availableDown)), dir];
}

function _firstCharacterStart() {
	// FIXME would not work in multiframe setting
	// need comunications between frames
	const r = new Range();
	console.assert(rikaigu.lastRangeNode);
	r.setStart(rikaigu.lastRangeNode, rikaigu.lastRangeOffset);
	return r.getBoundingClientRect().x;
}

function _lastCharacterEnd() {
	const s = window.getSelection();
	console.assert(s.rangeCount > 0);
	var end = 0;
	for (var i = 0; i < s.rangeCount; ++i) {
		end = Math.max(s.getRangeAt(i).getBoundingClientRect().right, end);
	}
	return end;
}

function _characterUpperLine() {
	const r = new Range();
	console.assert(rikaigu.lastRangeNode);
	r.setStart(rikaigu.lastRangeNode, rikaigu.lastRangeOffset);
	return r.getBoundingClientRect().top;
}

function _characterBottomLine() {
	const r = new Range();
	console.assert(rikaigu.lastRangeNode);
	r.setStart(rikaigu.lastRangeNode, rikaigu.lastRangeOffset);
	return r.getBoundingClientRect().bottom;
}

function _conditionSatisfied(condition) {
	return new Promise(function (resolve) {
		var count = 0;
		var interval = setInterval(function() {
			count += 1;
			if (condition()) {
				resolve(count);
				clearInterval(interval);
			}
		}, 10);
	});
}

const _defaultWidth = 347;
const _defaultHeight = 413;
async function _computeRequiredDimensions(popup) {
	if (popup.offsetWidth === 0) {
		await _conditionSatisfied(() => popup.offsetWidth !== 0);
	}
	return [
		Math.min(popup.offsetWidth, _defaultWidth),
		Math.min(popup.offsetHeight, _defaultHeight + _PADDING_AND_BORDER)
	];
}

function _makePopupScrollable(popup) {
	console.error('implement me');
	for (var el of popup.getElementsByClassName('rikaigu-lurk-moar')) {
		el.parentNode.removeChild(el);
	}
	for (var el of popup.getElementsByClassName('rikaigu-second-and-further')) {
		el.classList.remove('rikaigu-hidden')
	}
}

function _isPopupBelowText(y) {
	return y > _characterUpperLine() + window.scrollY;
}

function _placeExpandButton(popup, y) {
	const el = popup.getElementsByClassName('rikaigu-lurk-moar')[0] || null;
	if (el === null) return;
	el.parentNode.removeChild(el);
	if (_isPopupBelowText(y)) {
		popup.insertBefore(el, popup.firstChild);
	} else {
		popup.appendChild(el);
	}
}

async function _updatePopupRect(popup) {
	const [requiredWidth, requiredHeight] = await _computeRequiredDimensions(popup);
	// TODO optimize recomputations of start/end/upper line/bottom line
	// FIXME multiframe setting
	const [availableWidth, leftRightOrBoth] = _computeWidthAvailable(requiredWidth);
	const [availableHeight, upDownOrBoth] = _computeHeightAvailable(requiredHeight);
	if (availableHeight < requiredHeight) {
		_makePopupScrollable(popup);
	}

	const [x, y] = _computeFinalPosition(availableWidth, leftRightOrBoth, availableHeight, upDownOrBoth);
	_placeExpandButton(popup, y);

	popup.style.setProperty('left', `${x}px`, 'important');
	popup.style.setProperty('top', `${y}px`, 'important');
}

function _getPopupAndUpdateItsPosition() {
	_updatePopupRect(document.getElementById('rikaigu-window'));
}

function requestHidePopup() {
	chrome.runtime.sendMessage({
		"type": "relay",
		"targetType": "close"
	});
}

function hidePopup() {
	var popup = document.getElementById('rikaigu-window');
	if (popup) {
		popup.style.setProperty('display', 'none', 'important');
		popup.innerHTML = '';
		rikaigu.mouseOnPopup = false;
	}
	rikaigu.shownMatch = null;
}

function reset() {
	if (rikaigu.isVisible) {
		clearHighlight();
		requestHidePopup();
	}
}

function onKeyDown(ev) {
	if (rikaigu.config.showOnKey !== "None" && (ev.altKey || ev.ctrlKey)) {
		if (rikaigu.lastTarget !== null) {
			var fakeEvent = {
				clientX: rikaigu.lastPos.clientX,
				clientY: rikaigu.lastPos.clientY,
				screenX: rikaigu.lastPos.screenX,
				screenY: rikaigu.lastPos.screenY,
				target: rikaigu.lastTarget,
				altKey: ev.altKey,
				ctrlKey: ev.ctrlKey,
				shiftKey: ev.shiftKey,
				noDelay: true
			};
			// Send message to background for distribution to iframe where mouse currently is.
			if (rikaigu.activeFrame !== window.frameId) {
				fakeEvent.type = 'relay';
				fakeEvent.targetType = 'keyboardEventForActiveFrame';
				fakeEvent.frameId = rikaigu.activeFrame;
				chrome.runtime.sendMessage(fakeEvent);
			} else {
				onMouseMove(fakeEvent);
			}
		}
		return;
	}
	if (ev.shiftKey && ev.key !== 'Shift') return;
	if (!!rikaigu.keysDown[ev.code]) return;
	if (!rikaigu.isVisible) return;
	if (!rikaigu.config.enableKeys && ev.key !== 'Shift') return;

	switch (ev.code) {
		case 'ShiftLeft':
			chrome.storage.local.set({defaultDict: (rikaigu.config.defaultDict - 1 + 3) % 3}, function() {
				rikaigu.shownMatch = null;
				extractTextAndSearch();
			});
			break;
		case 'ShiftRight':
		case 'Enter':
			chrome.storage.local.set({defaultDict: (rikaigu.config.defaultDict + 1) % 3}, function() {
				rikaigu.shownMatch = null;
				extractTextAndSearch();
			});
			break;
		case 'Escape':
			reset();
			break;
		case 'KeyA':
			switch (rikaigu.altView) {
				case null:
					rikaigu.altView = 'up';
					break;
				case 'up':
					rikaigu.altView = 'down';
					break;
				case 'down':
					rikaigu.altView = null;
					break;
			}
			_getPopupAndUpdateItsPosition();
			break;
		case 'KeyD':
			chrome.storage.local.set({onlyReadings: !rikaigu.config.onlyReadings});
			for (var el of document.getElementsByClassName('rikaigu-pos-and-def')) {
				el.classList.toggle('rikaigu-hidden');
			}
			break;
		case 'KeyF':
			for (var el of document.getElementsByClassName('rikaigu-second-and-further')) {
				el.classList.toggle('rikaigu-hidden');
			}
			break;
		case 'KeyR':
			toggleHiddenAllReviewListEntriesInfo(document.getElementById('rikaigu-window'));
			break;
		case 'KeyS':
			window.debugMode = !window.debugMode;
			break;
		default:
			return;
	}

	rikaigu.keysDown[ev.code] = true;
}

function onMouseDown(ev) {
	if (ev.button !== 0)
		return;
	if (rikaigu.isVisible)
		clearHighlight();
	rikaigu.mousePressed = true;
}

function onMouseUp(ev) {
	if (ev.button != 0)
		return;
	rikaigu.mousePressed = false;
}

function onKeyUp(ev) {
	if (!!rikaigu.keysDown[ev.code]) delete rikaigu.keysDown[ev.code];
}

function processSearchResult(selectionRange, prefixSelectionRange, result) {
	clearHighlight();
	rikaigu.lastShownRangeNode = null;
	rikaigu.lastShownRangeOffset = 0;
	if (!result.matchLength || !highlightMatch(result.matchLength, result.prefixLength,
			selectionRange, prefixSelectionRange)) {
		return requestHidePopup();
	}
	if (selectionRange.constructor === Array) {
		rikaigu.lastShownRangeNode = selectionRange[0].rangeNode;
		rikaigu.lastShownRangeOffset = selectionRange[0].offset;
	} else {
		rikaigu.lastShownRangeNode = selectionRange.rangeNode;
		rikaigu.lastShownRangeOffset = selectionRange.offset;
	}

	/*
	chrome.runtime.sendMessage(
		{
			"type": "review",
			"text": getCurrentWordSentence(),
		}
	);
	*/
}

function makeFake(real) {
	var fake = document.createElement('div');
	var realRect = real.getBoundingClientRect();
	fake.innerText = real.value;
	fake.style.cssText = window.getComputedStyle(real, "").cssText;
	fake.scrollTop = real.scrollTop;
	fake.scrollLeft = real.scrollLeft;
	fake.style.position = "absolute";
	fake.style.zIndex = 7777;
	fake.style.top = (window.scrollY + realRect.top) + 'px';
	fake.style.left = (window.scrollX + realRect.left) + 'px';

	for (var i = 0; i < fake.style.length; ++i) {
		fake.style.setProperty(fake.style[i], fake.style.getPropertyValue(fake.style[i]), 'important');
	}

	return fake;
}

function isInput(node) {
	return node && (node.nodeName === 'TEXTAREA' || node.nodeName === 'INPUT' || node.nodeName === 'SELECT');
}

function _updateMousePositionState(ev) {
	rikaigu.lastPos = {
		clientX: ev.clientX,
		clientY: ev.clientY,
		screenX: ev.screenX,
		screenY: ev.screenY,
	};
	rikaigu.lastTarget = ev.target;

	if (rikaigu.activeFrame !== window.frameId) {
		chrome.runtime.sendMessage({
			"type": "relay",
			"targetType": "changeActiveFrame",
			"activeFrameId": window.frameId
		});
	}
}

function _shouldDoAnythingOnMouseMove(ev) {
	return !rikaigu.mouseOnPopup && (
		rikaigu.config.showOnKey === 'None' ||
		rikaigu.config.showOnKey.includes("Alt") && ev.altKey ||
		rikaigu.config.showOnKey.includes("Ctrl") && ev.ctrlKey
	);
}

function _getNewRange(ev) {
	var rangeEnd = 0;
	var rangeNode, rangeOffset;
	if (isInput(ev.target)) {
		const fakeInput = makeFake(ev.target);
		document.body.appendChild(fakeInput);
		rangeNode = ev.target;
		const range = document.caretRangeFromPoint(ev.clientX, ev.clientY);
		if (range.startContainer.parentNode !== fakeInput) {
			console.error('Failed to fake input', ev.target, range.startContainer, range.startOffset);
		}
		rangeOffset = range.startOffset;
		rangeEnd = ev.target.value.length;
		document.body.removeChild(fakeInput);
	} else {
		const range = document.caretRangeFromPoint(ev.clientX, ev.clientY);
		const rect = range && range.getBoundingClientRect();
		if (!range
				|| ev.clientX - rect.right > 25
				|| rect.left - ev.clientX > 25
				|| ev.clientY - rect.bottom > 25
				|| rect.top - ev.clientY > 25) {
			rangeNode = null;
			rangeOffset = 0;
		} else {
			rangeNode = range.startContainer;
			rangeOffset = range.startOffset;
			rangeEnd = range.startContainer.data? range.startContainer.data.length : 0;
		}
	}
	return [rangeEnd, rangeNode, rangeOffset];
}

function _checkRangeHaveNotChanged(rangeNode, rangeOffset) {
	return rangeNode === rikaigu.lastRangeNode && rangeOffset === rikaigu.lastRangeOffset
		&& (rikaigu.isVisible || rikaigu.timer !== null);
}

function _saveNewRange(rangeNode, rangeOffset) {
	rikaigu.lastRangeNode = rangeNode;
	rikaigu.lastRangeOffset = rangeOffset;
}

function _shouldSetSearchTimeout(rangeEnd) {
	return rikaigu.lastRangeNode && rikaigu.lastRangeOffset < rangeEnd;
}

function _setSearchTimeout(ev) {
	const delay = !!ev.noDelay ? 1 : rikaigu.config.popupDelay;
	if (rikaigu.timer) {
		clearTimeout(rikaigu.timer);
	}
	rikaigu.timer = setTimeout(
		function(rangeNode, rangeOffset) {
			rikaigu.timer = null;
			if (!rikaigu || rangeNode != rikaigu.lastRangeNode
					|| rangeOffset != rikaigu.lastRangeOffset
					|| rikaigu.mouseOnPopup) {
				return;
			}
			extractTextAndSearch(rangeNode, rangeOffset);
		},
		delay, rikaigu.lastRangeNode, rikaigu.lastRangeOffset
	);
}

function _shouldResetPopup(ev) {
	if (!rikaigu.isVisible || rikaigu.config.showOnKey !== 'None') return false;

	// TODO check if required
	if (rikaigu.selected && rikaigu.lastRangeNode) {
		const highlightedRange = window.getSelection().getRangeAt(0);
		// Check if cursor still in highlighted range.
		// At this point updated request have already been sent. If match will change, we'll update
		// (or close) popup. Otherwise no reason to close it.
		if (highlightedRange.comparePoint(rikaigu.lastRangeNode, rikaigu.lastRangeOffset) === 0) {
			return false;
		}
	}

	// FIXME would be true only in top frame
	return !rikaigu.mouseOnPopup;
}

function _setResetTimeout(ev) {
	if (rikaigu.resetTimer) return;
	rikaigu.resetTimer = setTimeout(
		function () {
			rikaigu.resetTimer = null;
			if (_shouldResetPopup(ev)) {
				reset();
			}
		},
		Math.max(3, rikaigu.config.popupDelay / 2)
	);
}

function onMouseMove(ev) {
	if (window.debugMode) return;

	_updateMousePositionState(ev);

	if (!_shouldDoAnythingOnMouseMove(ev)) return;

	const [rangeEnd, rangeNode, rangeOffset] = _getNewRange(ev);
	if (_checkRangeHaveNotChanged(rangeNode, rangeOffset)) return;

	_saveNewRange(rangeNode, rangeOffset);

	if (_shouldSetSearchTimeout(rangeEnd)) {
		_setSearchTimeout(ev);
		return;
	}

	if (_shouldResetPopup(ev)) {
		_setResetTimeout(ev);
	}
}

function _onMouseEnter(ev) {
	rikaigu.mouseOnPopup = true;
}

function _onMouseLeave(ev) {
	rikaigu.mouseOnPopup = false;
}

function makeReviewPopup() {
	const popup = document.createElementNS('http://www.w3.org/1999/xhtml', 'div');
	popup.setAttribute('id', 'rikaigu-review-window');
	popup.classList.add('rikaigu-window');
	popup.classList.add('rikaigu-hidden');
	document.documentElement.appendChild(popup);

	return popup;
}

function getEmptyReviewPopup() {
	var popup = document.getElementById('rikaigu-review-window');
	if (!popup) {
		popup = makeReviewPopup();
	} else {
		popup.innerHTML = '';
	}
	return popup;
}

function addToReviewPopup(popup, entry) {
	popup.innerHTML += `<p>${entry[0]}<br />${entry[1]}</p>`;
}

function processReviewResult(result) {
	console.log('processReviewResult', result);
	const reviewPopup = getEmptyReviewPopup();
	if (result) {
		result.forEach(addToReviewPopup.bind(window, reviewPopup));
		reviewPopup.classList.remove('rikaigu-hidden');
	} else {
		reviewPopup.classList.add('rikaigu-hidden');
	}
}

//Event Listeners
chrome.runtime.onMessage.addListener(
	function(request, sender, response) {
		switch (request.type) {
			case 'enable':
				chrome.storage.local.get(null, config => enableTab(config, request.text));
				break;
			case 'disable':
				disableTab();
				break;
			case 'show':
				if (window.self === window.top) {
					if (request.match === rikaigu.shownMatch) {
						// _getPopupAndUpdateItsPosition();
						// updatePopupPosition(
							// request.screenX - (rikaigu.lastPos.screenX - rikaigu.lastPos.clientX),
							// request.screenY - (rikaigu.lastPos.screenY - rikaigu.lastPos.clientY)
						// );
						console.error('why this branch even exists');
					} else {
						showPopup(request.html);
						rikaigu.shownMatch = request.match;
					}
				}
				rikaigu.isVisible = true;
				break;
			case 'show-reviewed':
				if (window.self === window.top) {
					processReviewResult(request.result);
				}
				break;
			case 'close':
				if (window.self === window.top) {
					hidePopup();
				}
				clearHighlight();
				rikaigu.isVisible = false;
				break;

			case 'changeActiveFrame':
				if (rikaigu) {
					rikaigu.activeFrame = request.activeFrameId;
				}
				break;
			case 'keyboardEventForActiveFrame':
				if (document.activeElement && document.activeElement.tagName === 'IFRAME') {
					document.activeElement.blur();
				}
				request.clientX = rikaigu.lastPos.clientX;
				request.clientY = rikaigu.lastPos.clientY;
				request.screenX = rikaigu.lastPos.screenX;
				request.screenY = rikaigu.lastPos.screenY;
				request.target = rikaigu.lastTarget;
				onMouseMove(request);
				break;

			default:
				console.error('Unknown request type:', request);
		}
	}
);

/*
 * When a frame loads, it asks background for config (if rikaigu is currently enabled)
 * and own frameId (always).
 */
chrome.runtime.sendMessage({
	"type": "enable?"
}, function(response) {
	window.frameId = response.frameId;
	if (response.enabled) {
		chrome.storage.local.get(null, enableTab);
	}
});

chrome.storage.onChanged.addListener(updateConfig);
