if (localStorage.length > 0) {
	// Update from old config
	// TODO remove after couple of months/versions

	var newConfig = {
		popupColor: localStorage["popupcolor"],
		enableKeys: localStorage["disablekeys"] !== 'true',
		popupDelay: parseInt(localStorage['popupDelay']) || 150,
		defaultDict: localStorage["defaultDict"]
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

function initOption(name, defaultValue) {
	chrome.storage.local.get(name, function(config) {
		if (!(name in config)) {
			config = {};
			config[name] = defaultValue;
			chrome.storage.local.set(config);
		}
	});
}

initOption("popupColor", "blue");
initOption("matchHighlight", true);
initOption("onlyReadings", false);
initOption("showMiniHelp", true);
initOption("enableKeys", true);
initOption("showKanjiComponents", true);
initOption("popupDelay", 150);
initOption("showOnKey", "None");
initOption("defaultDict", "words");
initOption('kanjiInfo', 'H L E DK N V Y P IN I U');
initOption('configVersion', 'v1.0.0');

var config = null;
var cppConfig = ['onlyReadings', 'showKanjiComponents', 'defaultDict', 'kanjiInfo'];
function updateCppConfig() {
	if (!window.Module) return;
	console.log('rikaigu_set_config');
	Module.ccall('rikaigu_set_config', null, ['number', 'number', 'string', 'string'],
		cppConfig.map(key => config[key]));
}

function onConfigChange(configChange) {
	chrome.storage.local.get(null, function(config) {
		window.config = config;
		for (var key of cppConfig) {
			if (key in configChange) {
				updateCppConfig();
				return;
			}
		}
	});
}

onConfigChange({});
chrome.storage.onChanged.addListener(onConfigChange);
