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

function enableTab(config, popup) {
	if (rikaigu === null) {
		rikaigu = {
			altView: 0,
			keysDown: {},
			lastPos: {
				clientX: 0,
				clientY: 0,
				screenX: 0,
				screenY: 0
			},
			lastTarget: null,
			mousePressed: false,
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

		if (popup) {
			if (!document.hidden && window.self === window.top) {
				rikaigu.altView = 1;
				showPopup(popup);
				rikaigu.altView = 0;
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
	document.documentElement.appendChild(popup);

	document.addEventListener('click', onClick, false);
	return popup;
}

function showPopup(text, x, y) {
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

	popup.style.setProperty('top', '-1000px', 'important');
	popup.style.setProperty('left', '0px', 'important');

	popup.style.display = '';
	updatePopupPosition(x, y, popup);
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

function onClick(ev) {
	if (!rikaigu.isVisible) return;
	if (!ev.target.classList.contains('rikaigu-add-to-review-list')) {
		return requestHidePopup();
	}
	var wordNode = ev.target.parentNode;
	rikaigu.config.reviewList[wordNode.getAttribute('id')] = getCurrentWordContext();
	chrome.storage.local.set({reviewList: rikaigu.config.reviewList}, function() {
		wordNode.removeChild(ev.target);
	});
}

function updatePopupPosition(x, y, popup) {
	if (isNaN(x) || isNaN(y)) x = y = 0;
	if (!popup) {
		popup = document.getElementById('rikaigu-window');
	}
	rikaigu.shownX = x;
	rikaigu.shownY = y;

	var popupWidth = popup.offsetWidth;
	var popupHeight = popup.offsetHeight;

	// guess!
	if (popupWidth <= 0) popupWidth = 200;
	if (popupHeight <= 0) {
		popupHeight = 0;
		var j = 0;
		var text = popup.innerHTML;
		while ((j = text.indexOf('<br/>', j)) != -1) {
			j += 5;
			popupHeight += 22;
		}
		popupHeight += 25;
	}

	if (rikaigu.altView === 1) {
		x = window.scrollX;
		y = window.scrollY;
	} else if (rikaigu.altView === 2) {
		x = (window.innerWidth - (popupWidth + 20)) + window.scrollX;
		y = (window.innerHeight - (popupHeight + 20)) + window.scrollY;
	} else {

		// Go left if necessary
		if (x + popupWidth > window.innerWidth - 20) {
			x = (window.innerWidth - popupWidth) - 20;
			if (x < 0) x = 0;
		}

		// Below the mouse
		// TODO compute from font-size
		const verticalOffset = 25;

		// Under the popup title
		//if ((elem.title) && (elem.title != '')) verticalOffset += 20;

		// Go up if necessary
		if (y + verticalOffset + popupHeight > window.innerHeight) {
			var t = y - popupHeight - 30;
			if (t >= 0) {
				y = t;
			} else {
				// If can't go up, still go down to prevent blocking cursor
				y += verticalOffset;
			}
		} else {
			y += verticalOffset;
		}

		x += window.scrollX;
		y += window.scrollY;
	}

	popup.style.setProperty('left', x + 'px', 'important');
	popup.style.setProperty('top', y + 'px', 'important');
}

function requestHidePopup() {
	chrome.runtime.sendMessage({
		"type": "close"
	});
}

function hidePopup() {
	var popup = document.getElementById('rikaigu-window');
	if (popup) {
		popup.style.setProperty('display', 'none', 'important');
		popup.innerHTML = '';
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
				fakeEvent.type = "keyboardEventForActiveFrame";
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
			rikaigu.altView = (rikaigu.altView + 1) % 3;
			updatePopupPosition(rikaigu.shownX, rikaigu.shownY);
			break;
		case 'KeyD':
			chrome.storage.local.set({onlyReadings: !rikaigu.config.onlyReadings}, function() {
				rikaigu.shownMatch = null;
				extractTextAndSearch();
			});
			break;
		case 'KeyY':
			rikaigu.altView = 0;
			updatePopupPosition(rikaigu.shownX, rikaigu.shownY + 20);
			break;
		case 'KeyE':
			chrome.storage.local.set({deinflectExpressions: !rikaigu.config.deinflectExpressions}, function() {
				rikaigu.shownMatch = null;
				extractTextAndSearch();
			});
			break
		case 'KeyF':
			for (var el of document.getElementsByClassName('rikaigu-second-and-further')) {
				el.classList.toggle('rikaigu-hidden');
			}
			break;
		case 'KeyR':
			toggleHiddenAllReviewListEntriesInfo(document.getElementById('rikaigu-window'));
			break;
		case 'KeyS':
			alert('Здесь мог бы быть ваш код для отображения слов из review-list из текущего предложения.');
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

function onMouseMove(ev) {
	rikaigu.lastPos = {
		clientX: ev.clientX,
		clientY: ev.clientY,
		screenX: ev.screenX,
		screenY: ev.screenY,
	};
	rikaigu.lastTarget = ev.target;

	if (rikaigu.activeFrame !== window.frameId) {
		chrome.runtime.sendMessage({
			"type": "changeActiveFrame",
			"frameId": window.frameId
		});
	}

	if (rikaigu.config.showOnKey !== 'None' &&
		((rikaigu.config.showOnKey.includes("Alt") && !ev.altKey) ||
		(rikaigu.config.showOnKey.includes("Ctrl") && !ev.ctrlKey))) {
		return;
	}

	var rangeEnd = 0;
	rikaigu.previousTarget = ev.target;
	var rangeNode, rangeOffset;
	if (isInput(ev.target)) {
		var fakeInput = makeFake(ev.target);
		document.body.appendChild(fakeInput);
		rangeNode = ev.target;
		var range = document.caretRangeFromPoint(ev.clientX, ev.clientY);
		if (range.startContainer.parentNode !== fakeInput) {
			console.error('Failed to fake input', ev.target, range.startContainer, range.startOffset);
		}
		rangeOffset = range.startOffset;
		rangeEnd = ev.target.value.length;
		document.body.removeChild(fakeInput);
	} else {
		var range = document.caretRangeFromPoint(ev.clientX, ev.clientY);
		var rect = range && range.getBoundingClientRect();
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
	if (rangeNode === rikaigu.lastRangeNode && rangeOffset === rikaigu.lastRangeOffset
			&& (rikaigu.isVisible || rikaigu.timer !== null)) {
		return;
	}

	rikaigu.lastRangeNode = rangeNode;
	rikaigu.lastRangeOffset = rangeOffset;

	if (rikaigu.lastRangeNode && rikaigu.lastRangeOffset < rangeEnd) {
		var delay = !!ev.noDelay ? 1 : rikaigu.config.popupDelay;
		if (rikaigu.timer) {
			clearTimeout(rikaigu.timer);
		}
		rikaigu.timer = setTimeout(
			function(rangeNode, rangeOffset) {
				rikaigu.timer = null;
				if (!rikaigu || rangeNode != rikaigu.lastRangeNode
						|| rangeOffset != rikaigu.lastRangeOffset) {
					return;
				}
				extractTextAndSearch(rangeNode, rangeOffset);
			}, delay, rikaigu.lastRangeNode, rikaigu.lastRangeOffset);
		return;
	}

	if (!rikaigu.isVisible) return;

	if (rikaigu.selected && rikaigu.lastRangeNode) {
		var highlightedRange = window.getSelection().getRangeAt(0);
		// Check if cursor still in highlighted range.
		// At this point updated request have already been sent. If match will change, we'll update
		// (or close) popup. Otherwise no reason to close it.
		if (highlightedRange.comparePoint(rikaigu.lastRangeNode, rikaigu.lastRangeOffset) === 0) {
			return;
		}
	}

	// Don't close just because we moved from a valid popup slightly over to a place with nothing
	var dx = rikaigu.shownX - ev.screenX;
	var dy = rikaigu.shownY - ev.screenY;
	var distance = Math.sqrt(dx * dx + dy * dy);
	if (distance > 4 && rikaigu.config.showOnKey === 'None') {
		reset();
	}
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
	function(request, sender, sendResponse) {
		switch (request.type) {
			case 'enable':
				chrome.storage.local.get(null, config => enableTab(config, request.popup));
				break;
			case 'disable':
				disableTab();
				break;
			case 'show':
				if (window.self === window.top) {
					if (request.match === rikaigu.shownMatch) {
						updatePopupPosition(
							request.screenX - (rikaigu.lastPos.screenX - rikaigu.lastPos.clientX),
							request.screenY - (rikaigu.lastPos.screenY - rikaigu.lastPos.clientY)
						);
					} else {
						showPopup(request.html,
							request.screenX - (rikaigu.lastPos.screenX - rikaigu.lastPos.clientX),
							request.screenY - (rikaigu.lastPos.screenY - rikaigu.lastPos.clientY)
						);
						rikaigu.shownMatch = request.match;
					}
				}
				rikaigu.isVisible = true;
				chrome.runtime.sendMessage(
					{
						"type": "review",
						"text": getCurrentWordSentence(),
					},
					processReviewResult
				);
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
					rikaigu.activeFrame = request.frameId;
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
}, function(enabled, frameId) {
	window.frameId = frameId;
	if (enabled) {
		chrome.storage.local.get(null, enableTab);
	}
});

chrome.storage.onChanged.addListener(updateConfig);
