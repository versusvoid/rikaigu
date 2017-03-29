/*
	Rikaigu
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

var miniHelp = '<span style="font-weight:bold">Rikaigu enabled!</span><br><br>' +
		'<table cellspacing=5>' +
		'<tr><td>A</td><td>Alternate popup location</td></tr>' +
		'<tr><td>Y</td><td>Move popup location down</td></tr>' +
		'<tr><td>D</td><td>Hide/show definitions</td></tr>' +
		'<tr><td>Shift/Enter&nbsp;&nbsp;</td><td>Switch dictionaries</td></tr>' +
		'<tr><td>B</td><td>Previous character</td></tr>' +
		'<tr><td>M</td><td>Next character</td></tr>' +
		'<tr><td>N</td><td>Next word</td></tr>' +
		'<tr><td colspan="2">&nbsp;</td></tr>' +
		'<tr><td colspan="2">Hold Shift to search only kanji</td></tr>' +
		'</table>';


var rikaiguEnabled = false;
function onLoaded(tabId) {
	rikaiguEnabled = true;
	chrome.tabs.sendMessage(tabId, {
		"type": "enable",
		"config": makeTabConfig(),
		"popup": (localStorage['showMiniHelp'] === 'true' ? miniHelp : 'Rikaigu enabled!')
	});

	chrome.browserAction.setBadgeBackgroundColor({
		"color": [255, 0, 0, 255]
	});
	chrome.browserAction.setBadgeText({
		"text": "On"
	});
	chrome.browserAction.setPopup({
		"popup": "/html/popup.html"
	});
}

function onLoadError(err) {
	console.error('onLoadError(', err, ')');
	chrome.browserAction.setBadgeBackgroundColor({
		"color": [0, 0, 0, 255]
	});
	chrome.browserAction.setBadgeText({
		"text": "Err"
	});
}

function clearState() {
	rikaiguEnabled = false;
	chrome.browserAction.setBadgeBackgroundColor({
		"color": [0, 0, 0, 0]
	});
	chrome.browserAction.setBadgeText({
		"text": ""
	});
	chrome.browserAction.setPopup({
		"popup": ""
	});
}

function loadFile(filename) {
	return new Promise(function(resolve, reject) {
		/*
		 * Modified version of emscripten_async_wget_data() which
		 * does not free allocated buffer after callback return.
		 * We don't have to copy file's content anymore (and we have
		 * large files like names.idx > 20MB). This leads to reduced
		 * TOTAL_MEMORY.
		 */
		var xhr = new XMLHttpRequest();
		xhr.open('GET', chrome.extension.getURL(filename), true);
		xhr.responseType = 'arraybuffer';
		xhr.onload = function xhr_onload() {
			if (xhr.status == 200) {
				var byteArray = new Uint8Array(xhr.response);
				var buffer = Module._malloc(byteArray.length);
				HEAPU8.set(byteArray, buffer);
				if (Module.ccall('rikaigu_set_file', 'number',
						['string', 'number', 'number'],
						[filename, buffer, byteArray.length])) {
					resolve();
				} else {
					reject('asm.js is a shit');
				}
			} else {
				reject(xhr.status);
			}
		};
		xhr.onerror = reject;
		xhr.send(null);
	});
}

function rikaiguEnable(tab) {
	if (!!window.Module) {
		console.error("Double enable");
		return;
	}
	window.Module = {
		print: function(text) { console.log('stdout:', text); },
		memoryInitializerPrefixURL: '/cpp/',
		filePackagePrefixURL: '/cpp/',
		onRuntimeInitialized: function() {
			updateCppConfig();
			Promise.all([
					/* names.dat and dict.dat are stored
					 * compressed in virtual file system
					 * of asm.js.
					 */
					loadFile('data/model.bin'),
					loadFile('data/radicals.dat'),
					loadFile('data/dict.idx'),
					loadFile('data/names.idx'),
					loadFile('data/kanji.idx'),
					loadFile('data/deinflect.dat'),
					loadFile('data/expressions.dat')
				]).then(onLoaded.bind(null, tab.id), onLoadError);
		}
	};
	var js = document.createElement("script");
	js.type = "text/javascript";
	js.src = "/cpp/rikai.asm.js";
	document.head.appendChild(js);
}

function rikaiguDisable() {
	// Send a disable message to all browsers
	var windows = chrome.windows.getAll({
			"populate": true
		},
		function(windows) {
			for (var i = 0; i < windows.length; ++i) {
				var tabs = windows[i].tabs;
				for (var j = 0; j < tabs.length; ++j) {
					chrome.tabs.sendMessage(tabs[j].id, {
						"type": "disable"
					});
				}
			}
		});
	location.reload();
}

function search(request) {
	var matchLengthPtr = Module._malloc(4);
	var prefixLengthPtr = Module._malloc(4);
	var html = Module.ccall('rikaigu_search', 'string', ['string', 'string', 'number'],
			[request.text, request.prefix, request.dictOption, matchLengthPtr, prefixLengthPtr]);
	var matchLen = Module.getValue(matchLengthPtr, 'i32');
	var prefixLength = Module.getValue(prefixLengthPtr, 'i32');
	Module._free(matchLengthPtr);
	Module._free(prefixLengthPtr);
	return {html, matchLen, prefixLength};
}

var translateCache = {__count__: 0};
function translate(title) {
	if (title in translateCache) {
		var res = translateCache[title];
		res.lastAccess = new Date().getTime();
		return res.html;
	} else {
		var html = Module.ccall('rikaigu_translate', 'string', ['string'], [title]);
		if (title.length < 1000) {
			translateCache[title] = {
				html,
				lastAccess: new Date().getTime()
			};
			translateCache.__count__ += 1;
			while (translateCache.__count__ > 10) {
				var min = translateCache[title].lastAccess, argmin = title;
				for (var k in translateCache) {
					if (translateCache[k].lastAccess && min > translateCache[k].lastAccess) {
						min = translateCache[k].lastAccess;
						argmin = k;
					}
				}
				delete translateCache[argmin];
				translateCache.__count__ -= 1;
			}
		}
		return html;
	}
}

function onTabActivated(activeInfo) {
	if (rikaiguEnabled) {
		chrome.tabs.sendMessage(activeInfo.tabId, {
			"type": "enable",
			"config": makeTabConfig()
		});
	}
}

function onMessage(request, sender, response) {
	switch (request.type) {
		case 'enable?':
			console.log('enable?');
			onTabActivated({tabId: sender.tab.id});
			break;
		case 'xsearch':
			console.log('xsearch');
			var result = search(request);
			result.type = request.type;
			response(result);
			//Module.ccall('rikaigu_dump_profile_info', null, []);
			break;
		case 'translate':
			console.log('translate');
			var html = translate(request.title);
			response({type: request.type, html});
			break;
		case 'switchOnlyReading':
			console.log('switchOnlyReading');
			if (localStorage['onlyReadings'] === 'true')
				localStorage['onlyReadings'] = 'false';
			else
				localStorage['onlyReadings'] = 'true';
			updateCppConfig();
			break;
		default:
			console.error('Unknown request type:', request);
	}
}

clearState();
chrome.browserAction.onClicked.addListener(rikaiguEnable);
chrome.tabs.onActivated.addListener(onTabActivated);
chrome.runtime.onMessage.addListener(onMessage);
