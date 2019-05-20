"use strict";

if (localStorage.length > 0) {
	// Update from old config
	// TODO remove after couple of months/versions

	var newConfig = {
		popupColor: localStorage["popupcolor"],
		enableKeys: localStorage["disablekeys"] !== 'true',
		popupDelay: parseInt(localStorage['popupDelay']) || 100,
		defaultDict: ['words', 'names', 'kanji'].indexOf(localStorage["defaultDict"])
	};
	for (var oldNew of [
			["highlight", "matchHighlight"],
			["onlyreading", "onlyReadings"],
			["minihelp", "showMiniHelp"],
			["kanjicomponents", "showKanjiComponents"]]) {

		newConfig[oldNew[1]] = (localStorage[oldNew[0]] === "true");
	}

	newConfig.showOnKey = localStorage['showOnKey'];
	if (!newConfig.showOnKey) {
		newConfig.showOnKey = "None";
	}

	var kanjiInfo = [];
	for (var k of ["H", "L", "E", "DK", "N", "V", "Y", "P", "IN", "I", "U"]) {
		if (localStorage[k] === 'true') {
			kanjiInfo.push(k);
		}
	}
	newConfig.kanjiInfo = kanjiInfo.join(' ');

	for (var k in localStorage) {
		localStorage.removeItem(k);
	}

	chrome.storage.local.set(newConfig);
}

var config = null;
function onConfigChange(configChange) {
	for (var key in configChange) {
		window.config[key] = configChange[key].newValue;
	}
	if ('reviewList' in configChange) {
		const oldReviewList = configChange['reviewList'].oldValue;
		const newReviewList = configChange['reviewList'].newValue;
		for (var key of Object.keys(oldReviewList)) {
			if (!(key in newReviewList)) {
				Module.instance.exports.review_list_remove_entry(Number(key));
			}
		}

		for (var key of Object.keys(newReviewList)) {
			console.assert(typeof key === "number");
			if (!(key in oldReviewList)) {
				Module.instance.exports.review_list_add_entry(Number(key));
			}
		}
	}
}

function initConfig(config) {
	const defaultConfig = {
		"popupColor": "blue",
		"matchHighlight": true,
		"onlyReadings": false,
		"showMiniHelp": true,
		"enableKeys": true,
		"showKanjiComponents": true,
		"popupDelay": 150,
		"showOnKey": "None",
		"defaultDict": 0,
		'kanjiInfo': 'H L E DK N V Y P IN I U',
		'configVersion': 'v1.0.0',
		'autostart': false,
		'reviewList': {},
	};

	var needUpdate = false;
	for (var k in defaultConfig) {
		if (!(k in config)) {
			config[k] = defaultConfig[k];
			needUpdate = true;
		}
	}
	if (needUpdate) {
		chrome.storage.local.set(config);
	}

	window.config = config;
	chrome.storage.onChanged.addListener(onConfigChange);

	onConfigReady();
}
chrome.storage.local.get(null, initConfig);
