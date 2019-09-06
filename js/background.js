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
const decoder = new TextDecoder('utf-8');

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
		window.Module = await WebAssembly.instantiateStreaming(
			fetch('/wasm/rikai.wasm'),
			{ env: {
				take_a_trip: takeATrip,
				print: print,
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

function writeInputText(text) {
	const view = new Uint16Array(Module.instance.exports.memory.buffer, Module.inputDataOffset, 32);
	for (let i = 0; i < text.length; i += 1) {
		view[i] = text.charCodeAt(i);
	}
}

function sendHtmlToTab(tabId, request, matchLength) {
	let res = Module.instance.exports.get_html();
	const htmlPtr = res % Math.pow(2, 32);
	const htmlLength = (res - htmlPtr) / Math.pow(2, 32);

	const htmlView = new Uint8Array(Module.instance.exports.memory.buffer, htmlPtr, htmlLength);
	const html = decoder.decode(htmlView);

	browser.tabs.sendMessage(tabId, {
		"type": "show",
		"html": html,
		"match": request.text.substring(0, matchLength),
		"renderParams": request.renderParams,
	});
}

function search(request, tabId) {
	writeInputText(request.text);
	const matchLength = Module.instance.exports.rikaigu_search(request.text.length);
	if (matchLength > 0) {
		sendHtmlToTab(tabId, request, matchLength);
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
			const matchLength = search(request, sender.tab.id);
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
