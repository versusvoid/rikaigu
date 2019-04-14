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
		'</table>';


var rikaiguEnabled = false;
function onLoaded(initiatorTab) {
	rikaiguEnabled = true;

	if (initiatorTab) {
		chrome.tabs.sendMessage(initiatorTab.id, {
			"type": "enable",
			"text": (config.showMiniHelp ? miniHelp : 'Rikaigu enabled!')
		});
	}

	chrome.windows.getAll({
			"populate": true
		},
		function(windows) {
			for (var browserWindow of windows) {
				for (var tab of browserWindow.tabs) {
					if (initiatorTab && tab.id === initiatorTab.id) continue;
					chrome.tabs.sendMessage(tab.id, {
						"type": "enable"
					});
				}
			}
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
		locateFile: function(path, prefix) { return '/cpp/' + path; },
		onRuntimeInitialized: function() {
			updateCppConfig();
			Promise.all([
					/* names.dat, dict.dat, and kanji.dat are stored
					 * compressed in emscripten's virtual file system.
					 */
					loadFile('data/radicals.dat'),
					loadFile('data/dict.idx'),
					loadFile('data/names.idx'),
					loadFile('data/kanji.idx'),
					loadFile('data/deinflect.dat'),
				]).then(onLoaded.bind(null, tab), onLoadError);
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
	chrome.storage.local.set({'reload': true});
	location.reload();
}

var inTextBuffer = [0, 0];
function stringToUTF16buffer(str) {
	let [buf, length] = inTextBuffer;
	if (length < str.length*2 + 2) {
		Module._free(buf);
		length = Math.max(64, str.length*2 + 2);
		buf = Module._malloc(str.length*2 + 2);
		inTextBuffer = [buf, length];
	}
	Module.stringToUTF16(str, buf, length);
	return buf;
}

async function getRoot() {
	return new Promise(function(resolve, reject) {
		chrome.runtime.getPackageDirectoryEntry(resolve);
	});
}

async function getFileEntry(root, path) {
	return new Promise(function(resolve, reject) {
		root.getFile(path, {}, resolve, reject);
	});
}

async function getFile(path) {
	const root = await getRoot();
	const entry = await getFileEntry(root, path);
	return new Promise(function(resolve, reject) {
		entry.file(resolve, reject);
	});
}

var namesFile = null;
var dictFile = null;

getFile('data/names.dat').then(function(f){namesFile = f;});
getFile('data/dict.dat').then(function(f){dictFile = f;});

async function getLines(file, offsets) {
	return Promise.all(offsets.map(offset => getLine(file, offset)));
};

async function getLine(file, offset) {
	return new Promise(function(resolve, reject) {
		var len = 75;
		var blob = file.slice(offset, offset + len);

		var reader = new FileReader();

		reader.addEventListener("loadend", function() {
			const view = new Uint8Array(reader.result);
			const end = view.indexOf('\n'.charCodeAt(0));
			if (end !== -1) {
				resolve(reader.result.slice(0, end));
			} else if (len > 7000) {
				reject(`There is no end: ${file.name}, ${offset}, ${len}, ${reader.result}`);
			} else {
				len = len * 2;
				blob = file.slice(offset, offset + len);
				reader.readAsArrayBuffer(blob);
			}
		});
		reader.readAsArrayBuffer(blob);
	});
}

async function printOffsets() {
	let readTimes = [];
	for (const k of ['names_offsets', 'dict_offsets']) {
		let v = Module.ccall(k, 'number', []);
		console.log('printOffsets', k, v);
		if (!v) continue;

		let offsets = [];
		let offset = Module.getValue(v, 'i32');
		while(offset !== 0) {
			offsets.push(offset);
			v += 4;
			offset = Module.getValue(v, 'i32');
		}
		console.log('printOffsets', k, offsets);

		const start = Date.now();
		const lines = await getLines(k.startsWith('names') ? namesFile : dictFile, offsets);
		readTimes.push(Date.now() - start);
		console.log(k, 'lines:', lines);
	}

	Module.ccall('rikaigu_dump_profile_info', null, []);
	Module.ccall('rikaigu_clear_profile_info', null, []);
	console.log('total read time:', readTimes.reduce((a,b) => a + b, 0), 'ms');
}

var matchLengthPtr = null;

function search(request) {
	if (!matchLengthPtr) {
		matchLengthPtr = Module._malloc(4);
	}
	const inText = stringToUTF16buffer(request.text);
	var html = Module.ccall('rikaigu_search', 'string', ['number', 'number'], [inText, matchLengthPtr]);
	var matchLength = Module.getValue(matchLengthPtr, 'i32');
	return [html, {matchLength, prefixLength: 0}];
}

function getReviewEntriesForSentence(text) {
	return Module.ccall('rikaigu_review_entries_for_sentence', 'string', ['string'], [text]);
}

function onMessage(request, sender, response) {
	switch (request.type) {
		case 'enable?':
			response({enabled: rikaiguEnabled, frameId: sender.frameId});
			break;

		case 'xsearch':
			var [html, result]  = search(request);
			result.type = request.type;
			response(result);
			if (html) {
				chrome.tabs.sendMessage(sender.tab.id, {
					"type": "show",
					"html": html,
					"match": request.prefix.substring(request.prefix.length - result.prefixLength)
						+ request.text.substring(0, result.matchLength),
					"screenX": request.screenX,
					"screenY": request.screenY
				});
			}

			break;

		case 'review':
			var result = getReviewEntriesForSentence(request.text);
			if (result) {
				chrome.tabs.sendMessage(sender.tab.id, {
					"type": "show-reviewed",
					"result": result.split('\n').map(s => s.split('\t'))
				})
			}
			break;

		case 'relay':
			console.assert(request.targetType);
			request.type = request.targetType;
			if ('frameId' in request) {
				chrome.tabs.sendMessage(sender.tab.id, request, {frameId: request.frameId});
			} else {
				chrome.tabs.sendMessage(sender.tab.id, request);
			}
			break;

		default:
			console.error('Unknown request type:', request);
	}
}

function onConfigReady() {
	if (config.reload) {
		chrome.storage.local.remove('reload');
		return;
	}
	if (config.autostart && !rikaiguEnabled) {
		rikaiguEnable();
	}
}

clearState();
chrome.browserAction.onClicked.addListener(rikaiguEnable);
chrome.runtime.onMessage.addListener(onMessage);
