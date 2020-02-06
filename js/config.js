"use strict";

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
		browser.storage.local.set(config);
	}

	window.config = config;
	browser.storage.onChanged.addListener(onConfigChange);

	onConfigReady();
}
browser.storage.local.get(null, initConfig);
