import { getDictionaryFiles } from '/js/idb.js';
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

var rikaiguEnabled = false;
var rikaiguError = false;

function onLoaded() {
	rikaiguEnabled = true;

	browser.windows.getAll({
			"populate": true
		},
		function(windows) {
			for (var browserWindow of windows) {
				for (var tab of browserWindow.tabs) {
					browser.tabs.sendMessage(tab.id, {
						"type": "enable"
					});
				}
			}
		});


	browser.browserAction.setBadgeBackgroundColor({
		"color": [255, 0, 0, 255]
	});
	browser.browserAction.setBadgeText({
		"text": "On"
	});
	browser.browserAction.setPopup({
		"popup": "/html/popup.html"
	});
}

function openDictionaryUploadPage() {
	browser.tabs.create({
		active: true,
		url: '/html/upload.html',
	});
}

function onError(err) {
	console.error('onError(', err, ')');

	browser.browserAction.setBadgeBackgroundColor({
		"color": [0, 0, 0, 255]
	});
	browser.browserAction.setBadgeText({
		"text": "Err"
	});
	rikaiguError = true;
}

function clearState() {
	rikaiguEnabled = false;
	browser.browserAction.setBadgeBackgroundColor({
		"color": [0, 0, 0, 0]
	});
	browser.browserAction.setBadgeText({
		"text": ""
	});
	browser.browserAction.setPopup({
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

async function rikaiguEnable(tab) {
	if (!!window.Module) {
		console.error("Double enable");
		return;
	}
	try {
		[window.namesDictionary, window.wordsDictionary] = await getDictionaryFiles();
		if (!window.namesDictionary || !window.wordsDictionary) {
			return openDictionaryUploadPage();
		}

		window.Module = await WebAssembly.instantiateStreaming(
			fetch('/wasm/rikai.wasm'),
			{ env: {
				take_a_trip: takeATrip,
				request_read_dictionary: requestReadDictionary,
				print: print,
			}}
		);
	} catch(err) {
		return onError(err);
	}

	Module.inputDataOffset = Module.instance.exports.rikaigu_set_config();

	onLoaded(tab);
}

function rikaiguDisable() {
	// Send a disable message to all browsers
	browser.windows.getAll({
			"populate": true
		},
		function(windows) {
			for (var i = 0; i < windows.length; ++i) {
				var tabs = windows[i].tabs;
				for (var j = 0; j < tabs.length; ++j) {
					browser.tabs.sendMessage(tabs[j].id, {
						"type": "disable"
					});
				}
			}
		});
	browser.storage.local.set({'reload': true});
	location.reload();
}

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
		promises.push(getLine(isName ? namesDictionary : wordsDictionary, offset));
	}

	return Promise.all(promises);
}

var nextRequestId = 0;
var lastRequest = null;

const decoder = new TextDecoder('utf-8');
async function requestReadDictionary(offsetsPtr, numOffsets, bufferHandle, requestId) {
	const lines = await readLines(offsetsPtr, numOffsets);

	if (lastRequest.id !== requestId) {
		return;
	}

	for (const line of lines) {
		const lineView = new Uint8Array(line);
		const bufPtr = Module.instance.exports.buffer_allocate(bufferHandle, lineView.length + 2);
		const bufView = new Uint8Array(Module.instance.exports.memory.buffer, bufPtr, lineView.length + 2);
		bufView[0] = lineView.length & 0xff;
		bufView[1] = (lineView.length >> 8) & 0xff;
		bufView.set(lineView, 2);
	}

	let res = Module.instance.exports.rikaigu_search_finish(bufferHandle);
	if (res === -1) {
		console.error('wut');
		return;
	}
	const htmlPtr = res % Math.pow(2, 32);
	const htmlLength = (res - htmlPtr) / Math.pow(2, 32);

	const htmlView = new Uint8Array(Module.instance.exports.memory.buffer, htmlPtr, htmlLength);
	const html = decoder.decode(htmlView);

	browser.tabs.sendMessage(lastRequest.tabId, {
		"type": "show",
		"html": html,
		"match": lastRequest.text.substring(0, lastRequest.matchLength),
		"renderParams": lastRequest.renderParams,
	});
}

function writeInputText(text) {
	const view = new Uint16Array(Module.instance.exports.memory.buffer, Module.inputDataOffset, 32);
	for (let i = 0; i < text.length; i += 1) {
		view[i] = text.charCodeAt(i);
	}
}

function startSearch(request, tabId) {
	lastRequest = {
		tabId: tabId,
		id: nextRequestId,
		...request,
	};
	nextRequestId += 1;

	writeInputText(request.text);
	let matchLength = 0;
	try {
		matchLength = Module.instance.exports.rikaigu_search_start(request.text.length, lastRequest.id);
	} catch (err) {
		onError(err);
		return 0;
	}

	if (matchLength > 0) {
		lastRequest.matchLength = matchLength;
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
				browser.tabs.sendMessage(sender.tab.id, request, {frameId: request.frameId});
			} else {
				browser.tabs.sendMessage(sender.tab.id, request);
			}
			break;

		default:
			console.error('Unknown request type:', request);
	}
}

function onConfigReady() {
	if (config.reload) {
		browser.storage.local.remove('reload');
		return;
	}
	if (config.autostart && !rikaiguEnabled) {
		rikaiguEnable();
	}
}

clearState();
browser.browserAction.onClicked.addListener(rikaiguEnable);
browser.runtime.onMessage.addListener(onMessage);
