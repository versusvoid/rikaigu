if (localStorage["v0.9.4"]) {
	// Update from old config
	// TODO remove after couple of months/versions
	localStorage.removeItem('copySeparator');
	localStorage.removeItem('maxClipCopyEntries');
	localStorage.removeItem('lineEnding');

	for (var oldNew of [
			["popupcolor", "popupColor"],
			["highlight", "matchHighlight"],
			["textboxhl"],
			["onlyreading", "onlyReadings"],
			["minihelp", "showMiniHelp"],
			["disablekeys", "disableKeys"],
			["kanjicomponents", "showKanjiComponents"]]) {

		if (oldNew.length > 1) {
			localStorage[oldNew[1]] = localStorage[oldNew[0]];
		}
		localStorage.removeItem(oldNew[0]);
	}

	if (!localStorage['showOnKey']) {
		localStorage['showOnKey'] = 'None';
	}

	var kanjiInfo = [];
	for (var k of ["H", "L", "E", "DK", "N", "V", "Y", "P", "IN", "I", "U"]) {
		if (localStorage[k] === 'true') {
			kanjiInfo.push(k);
		}
		localStorage.removeItem(k);
	}
	localStorage['kanjiInfo'] = kanjiInfo.join(' ');

	for (var k in localStorage) {
		if (k.startsWith('v0')) {
			localStorage.removeItem(k);
		}
	}
}

function initOption(name, defaultValue) {
	if (localStorage.getItem(name) === null) {
		localStorage[name] = defaultValue;
	}
}

initOption("popupColor", "blue");
initOption("matchHighlight", true);
initOption("onlyReadings", false);
initOption("showMiniHelp", "true");
initOption("disableKeys", "false");
initOption("showKanjiComponents", "true");
initOption("popupDelay", "150");
initOption("showOnKey", "None");
initOption("defaultDict", "words");
initOption('kanjiInfo', 'H L E DK N V Y P IN I U');
initOption('configVersion', 'v1.0.0');

function updateCppConfig() {
	if (!window.Module) return;
	Module.ccall('rikaigu_set_config', null, ['number', 'number', 'string', 'string'],
		[ localStorage['onlyReadings'] === 'true'
		, localStorage['showKanjiComponents'] === 'true'
		, localStorage['defaultDict']
		, localStorage['kanjiInfo']
		]);
}

function makeTabConfig() {
	return {
		css: localStorage['popupColor'],
		disableKeys: localStorage['disableKeys'] === 'true',
		matchHighlight: localStorage['matchHighlight'] === 'true',
		popupDelay: parseInt(localStorage['popupDelay']),
		showOnKey: localStorage['showOnKey']
	};
}

function updateConfig() {
	console.log('updateConfig()');

	var tabConfig = makeTabConfig();

	var windows = chrome.windows.getAll({
			"populate": true
		},
		function(windows) {
			for (var i = 0; i < windows.length; ++i) {
				var tabs = windows[i].tabs;
				for (var j = 0; j < tabs.length; ++j) {
					chrome.tabs.sendMessage(tabs[j].id, {
						type: "config",
						config: tabConfig
					});
				}
			}
		});

	updateCppConfig();
}
