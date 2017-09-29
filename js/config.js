if (localStorage.length > 0) {
	// Update from old config
	// TODO remove after couple of months/versions

	var newConfig = {
		popupColor: localStorage["popupcolor"],
		enableKeys: localStorage["disablekeys"] !== 'true',
		popupDelay: parseInt(localStorage['popupDelay']) || 150,
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
var cppConfig = ['onlyReadings', 'showKanjiComponents', 'deinflectExpressions', 'defaultDict', 'kanjiInfo'];
function updateCppConfig() {
	if (!window.Module) return;
	Module.ccall('rikaigu_set_config', null, ['number', 'number', 'number', 'number', 'string'],
		cppConfig.map(key => config[key]));
}

function onConfigChange(configChange) {
	for (var key in configChange) {
		window.config[key] = configChange[key].newValue;
	}
	for (var key of cppConfig) {
		if (key in configChange) {
			updateCppConfig();
			return;
		}
	}
}

function initConfig(config) {
	const defaultConfig = {
		"deinflectExpressions": true,
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
