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
var rikaiguError = false;
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

function onError(err) {
	console.error('onError(', err, ')');
	chrome.browserAction.setBadgeBackgroundColor({
		"color": [0, 0, 0, 255]
	});
	chrome.browserAction.setBadgeText({
		"text": "Err"
	});
	rikaiguError = true;
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

function readCString(ptr) {
	let length = 0;
	const buf = new Uint8Array(Module.instance.exports.memory.buffer, ptr);
	while (buf[length] !== 0) {
		length += 1;
	}
	return decoder.decode(buf.slice(0, length));
}

function takeATrip(errorPtr) {
	const err = readCString(errorPtr);
	onError(err);
	throw new Error(err);
}

function print(ptr) {
	console.log(readCString(ptr));
}

const traceLog = [];
chrome.storage.local.get(['traceLog'], function(data) {
	console.log('last trace log:', JSON.parse(data.traceLog || null));
});

function trace(ptr, stack) {
	traceLog.push(`${readCString(ptr)} stack at ${stack}`);
	chrome.storage.local.set({ traceLog: JSON.stringify(traceLog)}, function() {});
}

function resetTraceLog() {
	traceLog.splice(0);
	chrome.storage.local.set({ traceLog: JSON.stringify(traceLog)}, function() {});
}

async function rikaiguEnable(tab) {
	if (!!window.Module) {
		console.error("Double enable");
		return;
	}
	try {
		window.Module = await WebAssembly.instantiateStreaming(
			fetch('/wasm/rikai.wasm'),
			{ env: {
				take_a_trip: takeATrip,
				request_read_dictionary: requestReadDictionary,
				print: print,
				trace: trace,
			}}
		);
	} catch(err) {
		onError(err);
	}

	Module.inputDataOffset = Module.instance.exports.rikaigu_set_config(
		Module.instance.exports.__heap_base,
		Module.instance.exports.memory.buffer.byteLength,
	);

	onLoaded(tab);
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
		var len = 75; // median line length
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

function readLines(offsetsPtr, numOffsets) {
	const offsetsView = new Uint32Array(Module.instance.exports.memory.buffer, offsetsPtr, numOffsets);
	const promises = [];
	for (let i = 0; i < offsetsView.length; ++i) {
		// see word_results.c : state_make_offsets_array_and_request_read()
		const isName = !!(offsetsView[i] & (1 << 31));
		const offset = offsetsView[i] & 0x7FFFFFFF;
		promises.push(getLine(isName ? namesFile : dictFile, offset));
	}
	return Promise.all(promises);
}

var nextRequestId = 0;
var requestsData = new Map();

const decoder = new TextDecoder('utf-8');
async function requestReadDictionary(offsetsPtr, numOffsets, bufferHandle, requestId) {
	const lines = await readLines(offsetsPtr, numOffsets);

	for (const line of lines) {
		const lineView = new Uint8Array(line);
		const bufPtr = Module.instance.exports.buffer_allocate(bufferHandle, lineView.length + 2);
		const bufView = new Uint8Array(Module.instance.exports.memory.buffer, bufPtr, lineView.length + 2);
		bufView[0] = lineView.length & 0xff;
		bufView[1] = (lineView.length >> 8) & 0xff;
		bufView.set(lineView, 2);
	}

	const request = requestsData.get(requestId);
	console.assert(request);
	requestsData.delete(requestId);

	let res = Module.instance.exports.rikaigu_search_finish(bufferHandle);
	resetTraceLog();
	if (res === -1) {
		console.error('wut');
		return;
	}
	const htmlPtr = res % Math.pow(2, 32);
	const htmlLength = (res - htmlPtr) / Math.pow(2, 32);

	const htmlView = new Uint8Array(Module.instance.exports.memory.buffer, htmlPtr, htmlLength);
	const html = decoder.decode(htmlView);

	chrome.tabs.sendMessage(request.tabId, {
		"type": "show",
		"html": html,
		"match": request.text.substring(0, request.matchLength),
		"renderParams": request.renderParams,
	});
}

function writeInputText(text) {
	const view = new Uint16Array(Module.instance.exports.memory.buffer, Module.inputDataOffset, 32);
	for (let i = 0; i < text.length; i += 1) {
		view[i] = text.charCodeAt(i);
	}
}

const searchHistory = [];
chrome.storage.local.get(['searchHistory'], function(data) {
	console.log('old search history:', JSON.parse(data.searchHistory || null));
});

function startSearch(request, tabId) {
	searchHistory.push(request.text);
	chrome.storage.local.set({ searchHistory: JSON.stringify(searchHistory)}, function() {});

	if (requestsData.size > 0) {
		console.error('Still processing previous request:', requestsData.values().next().value);
		return;
	}

	writeInputText(request.text);
	const matchLength = Module.instance.exports.rikaigu_search_start(request.text.length, nextRequestId);
	resetTraceLog();
	if (matchLength) {
		request.tabId = tabId;
		request.matchLength = matchLength;
		requestsData.set(nextRequestId, request);
		nextRequestId += 1;
	}
	return matchLength;
}

function onMessage(request, sender, response) {
	switch (request.type) {
		case 'enable?':
			response({enabled: rikaiguEnabled, frameId: sender.frameId});
			break;

		case 'xsearch':
			if (rikaiguError) return;
			const matchLength = startSearch(request, sender.tab.id);
			response({matchLength, type: request.type});

			break;

		case 'relay':
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
