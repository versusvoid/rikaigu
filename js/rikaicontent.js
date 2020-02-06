'use strict';

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
	browser.storage.local.get(null, function(config) {
		if (rikaigu !== null) {
			rikaigu.config = config;
		}
	});
}

function enableTab(config) {
	if (rikaigu === null) {
		rikaigu = {
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
			lastShownRange: {
				node: null,
				offset: 0,
			},
			lastRange: null,
			config: config
		};
		window.addEventListener('mousemove', onMouseMove, false);
		window.addEventListener('keydown', onKeyDown, true);
		window.addEventListener('keyup', onKeyUp, true);
		window.addEventListener('mousedown', onMouseDown, false);
		window.addEventListener('mouseup', onMouseUp, false);
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
	css.setAttribute('href', browser.extension.getURL('css/popup-' + rikaigu.config.popupColor + '.css'));
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

async function showPopup(text, renderParams) {
	var popup = document.getElementById('rikaigu-window');
	if (!popup) {
		popup = makePopup();
	} else {
		var href = browser.extension.getURL('css/popup-' + rikaigu.config.popupColor + '.css');
		var css = document.getElementById('rikaigu-css');
		if (css.getAttribute('href') !== href) {
			css.setAttribute('href', href);
		}
	}

	if (getContentType() == 'text/plain') {
		const span = document.createElement('span');
		span.textContent = text;

		while (popup.firstChild) {
			popup.removeChild(popup.firstChild);
		}
		popup.appendChild(span);
	} else {
		popup.innerHTML = text;
	}

	// popup.style.setProperty('top', `${window.scrollY}px`, 'important');
	// popup.style.setProperty('left', `${window.scrollX}px`, 'important');
	popup.style.setProperty('top', `-1000px`, 'important');
	popup.style.setProperty('left', `0px`, 'important');

	popup.style.removeProperty('display');

	await _updatePopupPosition(popup, renderParams);
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
	button.textContent = button.textContent.indexOf('▲') !== -1 ? '▼' : '▲';
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

	// TODO handle select in popup
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
		/*
		let context = getCurrentWordContext();
		console.log('context:', context);
		for (const el of wordNode.querySelectorAll('.w-kanji, .w-kana')) {
			if (context === el.innerText) {
				console.log('matching context');
				context = '';
				break;
			}
		}
		*/
		const context = '';

		rikaigu.config.reviewList[wordNode.getAttribute('jmdict-id')] = context;
		wordNode.getElementsByClassName('w-review-context')[0].textContent = context;
	} else {
		delete rikaigu.config.reviewList[wordNode.getAttribute('jmdict-id')];
	}

	for (const el of wordNode.getElementsByClassName('rikaigu-review-listed')) {
		el.classList.toggle('rikaigu-hidden');
	}
	wordNode.classList.toggle('reviewed');

	browser.storage.local.set({reviewList: rikaigu.config.reviewList});
}

function rightmostRangeRect(range) {
	/*
	 * Range can have multiple client rects
	 * if caret is at the start of the line.
	 * We want the lowest (argmax rect.y)
	 * In the sense of text flow it will be
	 * the rightmost
	 */
	let lowest = null;
	for (const rect of range.getClientRects()) {
		if (!lowest || rect.top > lowest.top) {
			lowest = rect;
		}
	}
	return lowest;
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

const _DIRECTIONS = {
	UP   : 0b0001,
	DOWN : 0b0010,
	LEFT : 0b0100,
	RIGHT: 0b1000,
}

function _getRenderParams(rect) {
	const dx = (rikaigu.lastPos.screenX - rikaigu.lastPos.clientX);
	const dy = (rikaigu.lastPos.screenY - rikaigu.lastPos.clientY);
	return {
		firstCharacterStart: rect.x + dx,
		lastCharacterEnd: rect.x + dx, // FIXME we don't have selection yet, so make array for all possible selections length
		characterUpperLine: rect.top + dy,
		characterBottomLine: rect.bottom + dy,
	};
}

const _PADDING_AND_BORDER = 4 + 1;
const _defaultWidth = 347;
const _defaultHeight = 413;
class PopupDimPosComputer {
	constructor(popup, renderParams) {
		this.popup = popup;

		// In top frame this represents integral position of webpage's viewport.
		// In a sense we transform coordinates to screen space when passing them
		// to background page, and here we transform them back to webpage space of
		// top frame
		const integralDx = (rikaigu.lastPos.screenX - rikaigu.lastPos.clientX);
		const integralDy = (rikaigu.lastPos.screenY - rikaigu.lastPos.clientY);
		this._firstCharacterStart = renderParams.firstCharacterStart - integralDx;
		this._lastCharacterEnd = renderParams.lastCharacterEnd - integralDx;
		this._characterBottomLine = renderParams.characterBottomLine - integralDy;
		this._characterUpperLine = renderParams.characterUpperLine - integralDy;
	}

	_getCached(key, computeFunction) {
		if (key in this) {
			return this[key];
		}
		computeFunction.apply(this);
		return this[key];
	}

	_computeRequiredDimensions() {
		this._requiredWidthValue = Math.min(this.popup.offsetWidth, _defaultWidth);
		this._requiredHeightValue = Math.min(this.popup.offsetHeight, _defaultHeight + _PADDING_AND_BORDER);
	}

	get _requiredHeight() {
		return this._getCached('_requiredHeightValue', this._computeRequiredDimensions);
	}

	get _requiredWidth() {
		return this._getCached('_requiredWidthValue', this._computeRequiredDimensions);
	}

	_computeHeightAvailable() {
		const availableUp = this._characterUpperLine;
		const availableDown = window.innerHeight - this._characterBottomLine;
		this._upDownOrBothValue = (
			(availableUp >= this._requiredHeight ? _DIRECTIONS.UP : 0)
			|
			(availableDown >= this._requiredHeight ? _DIRECTIONS.DOWN : 0)
		)
		this._availableHeightValue = Math.min(this._requiredHeight, Math.max(availableUp, availableDown));
	}

	get _upDownOrBoth() {
		return this._getCached('_upDownOrBothValue', this._computeHeightAvailable);
	}

	get _availableHeight() {
		return this._getCached('_availableHeightValue', this._computeHeightAvailable);
	}

	_computeWidthAvailable() {
		const availableLeft = this._lastCharacterEnd;
		const availableRight = window.innerWidth - this._firstCharacterStart;
		const availableMax = Math.max(availableLeft, availableRight);
		if (availableMax < this._requiredWidth) {
			return [Math.min(this._requiredWidth, window.innerWidth), 0];
		}
		this._leftRightOrBothValue = (
			(availableRight >= this._requiredWidth ? _DIRECTIONS.RIGHT : 0)
			|
			(availableLeft >= this._requiredWidth ? _DIRECTIONS.LEFT : 0)
		);
		this._availableWidthValue = Math.min(this._requiredWidth, availableMax);
	}

	get _leftRightOrBoth() {
		return this._getCached('_leftRightOrBothValue', this._computeWidthAvailable);
	}

	get _availableWidth() {
		return this._getCached('_availableWidthValue', this._computeWidthAvailable);
	}

	_makePopupScrollable() {
		console.error('implement me');
		for (var el of this.popup.getElementsByClassName('rikaigu-lurk-moar')) {
			el.parentNode.removeChild(el);
		}
		for (var el of this.popup.getElementsByClassName('rikaigu-second-and-further')) {
			el.classList.remove('rikaigu-hidden')
		}
	}

	async _popupReady() {
		if (this.popup.offsetWidth === 0) {
			await _conditionSatisfied(() => this.popup.offsetWidth !== 0);
		}

		if (this._availableHeight < this._requiredHeight) {
			this._makePopupScrollable();
		}
	}

	_computeFinalPosition() {
		let x,y;
		if (this._leftRightOrBoth === 0) {
			x = (window.innerWidth - this._availableWidth) / 2;
		}
		// TODO change defaults for writing-mode: vertical-rl;
		// these defaults are preferable only for horizontal
		else if ((this._leftRightOrBoth & _DIRECTIONS.RIGHT) !== 0) {
			x = this._firstCharacterStart;
		} else {
			x = this._lastCharacterEnd - this._availableWidth;
		}

		if (this._upDownOrBoth === 0 || (this._upDownOrBoth & _DIRECTIONS.DOWN) !== 0) {
			y = this._characterBottomLine;
		} else {
			y = this._characterUpperLine - this._availableHeight - _PADDING_AND_BORDER;
		}

		x += window.scrollX;
		y += window.scrollY;
		return [x, y];
	}

	_isPopupBelowText(y) {
		return y > this._characterUpperLine + window.scrollY;
	}

	_placeExpandButton(y) {
		const el = this.popup.getElementsByClassName('rikaigu-lurk-moar')[0] || null;
		if (el === null) return;
		el.parentNode.removeChild(el);
		if (this._isPopupBelowText(y)) {
			this.popup.insertBefore(el, this.popup.firstChild);
		} else {
			this.popup.appendChild(el);
		}
	}

	async updatePopupPosition() {
		await this._popupReady();

		const [x, y] = this._computeFinalPosition();
		this._placeExpandButton(y);

		this.popup.style.setProperty('left', `${x}px`, 'important');
		this.popup.style.setProperty('top', `${y}px`, 'important');
	}
}

async function _updatePopupPosition(popup, renderParams) {
	const computer = new PopupDimPosComputer(popup, renderParams);
	await computer.updatePopupPosition();
}

function _getPopupAndUpdateItsPosition() {
	_updatePopupPosition(document.getElementById('rikaigu-window'), rikaigu.lastRange.renderParams);
}

function requestHidePopup() {
	browser.runtime.sendMessage({
		'type': 'relay',
		'targetType': 'close'
	});
}

function hidePopup() {
	var popup = document.getElementById('rikaigu-window');
	if (popup) {
		popup.style.setProperty('display', 'none', 'important');
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
	if (rikaigu.config.showOnKey !== 'None' && (ev.altKey || ev.ctrlKey)) {
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
				browser.runtime.sendMessage(fakeEvent);
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
			browser.storage.local.set({defaultDict: (rikaigu.config.defaultDict - 1 + 3) % 3}, function() {
				rikaigu.shownMatch = null;
				extractTextAndSearch();
			});
			break;
		case 'ShiftRight':
		case 'Enter':
			browser.storage.local.set({defaultDict: (rikaigu.config.defaultDict + 1) % 3}, function() {
				rikaigu.shownMatch = null;
				extractTextAndSearch();
			});
			break;
		case 'Escape':
			reset();
			break;
		case 'KeyD':
			browser.storage.local.set({onlyReadings: !rikaigu.config.onlyReadings});
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

function processSearchResult(selectionRange, renderParams, result) {
	clearHighlight();
	if (!result.matchLength || !highlightMatch(result.matchLength, selectionRange)) {

		rikaigu.lastShownRange = {
			node: null,
			offset: 0,
			renderParams,
		};

		requestHidePopup();

	} else if (selectionRange.constructor === Array) {

		rikaigu.lastShownRange = {
			node: selectionRange[0].rangeNode,
			offset: selectionRange[0].offset,
			renderParams,
		};

	} else {

		rikaigu.lastShownRange = {
			node: selectionRange.rangeNode,
			offset: selectionRange.offset,
			renderParams,
		};

	}
}

function makeFake(real) {
	const fake = document.createElement('div');
	fake.innerText = real.value;

	const computedStyle = window.getComputedStyle(real, '');
	fake.style.cssText = computedStyle.cssText;

	fake.style.opacity = '0';
	/* for debugging
	fake.style.color = 'red';
    fake.style.webkitTextFillColor = 'red';
	fake.style.backgroundColor = 'transparent';
	*/

	fake.scrollTop = real.scrollTop;
	fake.scrollLeft = real.scrollLeft;
	fake.style.position = 'absolute';
	fake.style.zIndex = 7777;

	const realRect = real.getBoundingClientRect();
	fake.style.top = (window.scrollY + realRect.top - parseFloat(computedStyle.marginTop)) + 'px';
	fake.style.left = (window.scrollX + realRect.left - parseFloat(computedStyle.marginLeft)) + 'px';

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
		browser.runtime.sendMessage({
			'type': 'relay',
			'targetType': 'changeActiveFrame',
			'activeFrameId': window.frameId
		});
	}
}

function _shouldDoAnythingOnMouseMove(ev) {
	return !rikaigu.mouseOnPopup && (
		rikaigu.config.showOnKey === 'None' ||
		rikaigu.config.showOnKey.includes('Alt') && ev.altKey ||
		rikaigu.config.showOnKey.includes('Ctrl') && ev.ctrlKey
	);
}

function _tooFar(rect, clientX, clientY) {
	return (
		clientX - rect.right > 15
		|| rect.left - clientX > 15
		|| clientY - rect.bottom > 15
		|| rect.top - clientY > 15
	);
}

function nextTick() {
	return new Promise(function(resolve, reject) {
		setTimeout(function() { resolve(); }, 0);
	});
}

async function _getRangeCandidateFromInput(ev) {
	const checkElement = document.elementFromPoint(ev.clientX, ev.clientY);
	if (checkElement !== ev.target) {
		// Non-repeatable mouseover
		return null;
	}
	if (!ev.target.value) {
		return null;
	}

	const fakeInput = makeFake(ev.target);
	document.body.parentNode.appendChild(fakeInput);
	await nextTick();
	const range = _rangeFromPoint(ev.clientX, ev.clientY);

	if (range.startContainer.parentNode !== fakeInput) {
		console.error('Failed to fake input', ev.target, range.startContainer, range.startOffset, fakeInput);
		fakeInput.remove();
		return null;
	}

	const rect = rightmostRangeRect(range);
	const result = {
		node: ev.target,
		offset: range.startOffset,
		end: ev.target.value.length,
		renderParams: _getRenderParams(rect),
	};
	fakeInput.remove();

	if (_tooFar(rect, ev.clientX, ev.clientY)) {
		return null;
	}

	return result;
}

function _rangeFromPoint(x, y) {
	if (document.caretRangeFromPoint) {
		// chrome
		return document.caretRangeFromPoint(x, y);
	}

	// firefox
	const caretPosition = document.caretPositionFromPoint(x, y);

	const range = new Range();
	range.setStart(caretPosition.offsetNode, caretPosition.offset);
	range.setEnd(caretPosition.offsetNode, caretPosition.offset);
	return range;
}

function _getRangeCandidateFromPlainElement(ev) {
	const range = _rangeFromPoint(ev.clientX, ev.clientY);
	const rect = range && rightmostRangeRect(range);
	if (!rect || _tooFar(rect, ev.clientX, ev.clientY)) {
		return null;
	}

	return {
		node: range.startContainer,
		offset: range.startOffset,
		end: range.startContainer.data ? range.startContainer.data.length : 0,
		renderParams: _getRenderParams(rect),
	};
}

async function _getNewRangeCandidate(ev) {
	let result = null;
	if (isInput(ev.target)) {
		result = await _getRangeCandidateFromInput(ev);
	} else {
		result = _getRangeCandidateFromPlainElement(ev);
	}

	if (result && result.offset === result.end) {
		result = null;
	}

	return result;
}

function _checkRangeHaveNotChanged(rangeCandidate) {
	if (!rangeCandidate ^ !rikaigu.lastRange) {
		return false;
	}
	if (!rangeCandidate) {
		return true;
	}

	return (
		rangeCandidate.node === rikaigu.lastRange.node
		&& rangeCandidate.offset === rikaigu.lastRange.offset
		&& (rikaigu.isVisible || rikaigu.timer !== null)
	);
}

function _setSearchTimeout(ev) {
	const delay = !!ev.noDelay ? 1 : rikaigu.config.popupDelay;
	if (rikaigu.timer) {
		clearTimeout(rikaigu.timer);
	}
	rikaigu.timer = setTimeout(
		function(rangeCandidate) {
			rikaigu.timer = null;
			if (!rikaigu || rikaigu.mouseOnPopup) {
				return;
			}
			if (rangeCandidate !== rikaigu.lastRange) {
				return;
			}
			if (rangeCandidate.node === rikaigu.lastShownRange.node && rangeCandidate.offset === rikaigu.lastShownRange.offset && rikaigu.isVisible) {
				return;
			}
			extractTextAndSearch(rangeCandidate.node, rangeCandidate.offset, rangeCandidate.renderParams);
		},
		delay, rikaigu.lastRange,
	);
}

function _shouldResetPopup(ev) {
	if (!rikaigu.isVisible || rikaigu.config.showOnKey !== 'None') return false;

	// TODO check if required
	if (rikaigu.selected && rikaigu.lastRange) {
		const highlightedRange = window.getSelection().getRangeAt(0);
		// Check if cursor still in highlighted range.
		// At this point updated request have already been sent. If match will change, we'll update
		// (or close) popup. Otherwise no reason to close it.
		if (highlightedRange.comparePoint(rikaigu.lastRange.node, rikaigu.lastRange.offset) === 0) {
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

async function onMouseMove(ev) {
	if (window.debugMode) return;

	_updateMousePositionState(ev);

	if (!_shouldDoAnythingOnMouseMove(ev)) {
		return;
	}

	const rangeCandidate = await _getNewRangeCandidate(ev);
	if (_checkRangeHaveNotChanged(rangeCandidate)) {
		return;
	}

	rikaigu.lastRange = rangeCandidate;

	if (rangeCandidate) {
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
	const popup = document.createElement('div');
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
	}
	return popup;
}

function addToReviewPopup(popup, entry) {
	const p = document.createElement('p');
	p.append(entry[0]);
	p.appendChild(document.createElement('br'));
	p.append(entry[1]);
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
browser.runtime.onMessage.addListener(
	function(request, sender, response) {
		switch (request.type) {
			case 'enable':
				browser.storage.local.get(null, enableTab);
				break;
			case 'disable':
				disableTab();
				break;
			case 'show':
				if (window.self === window.top) {
					console.assert(request.match !== rikaigu.shownMatch);
					showPopup(request.html, request.renderParams);
					rikaigu.shownMatch = request.match;
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
browser.runtime.sendMessage({
	'type': 'enable?'
}, function(response) {
	window.frameId = response.frameId;
	if (response.enabled) {
		browser.storage.local.get(null, enableTab);
	}
});

browser.storage.onChanged.addListener(updateConfig);
