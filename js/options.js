var kanjiInfoKeys = ["H", "L", "E", "DK", "N", "V", "Y", "P", "IN", "I", "U"];

function fillVals() {
	document.optform.popupcolor.value = localStorage['popupcolor'];

	if (localStorage['highlight'] == 'true')
		document.optform.highlighttext.checked = true;
	else
		document.optform.highlighttext.checked = false;

	if (localStorage['textboxhl'] == 'true')
		document.optform.textboxhl.checked = true;
	else
		document.optform.textboxhl.checked = false;

	if (localStorage['onlyreading'] == 'true')
		document.optform.onlyreading.checked = true;
	else
		document.optform.onlyreading.checked = false;

	if (localStorage['minihelp'] == 'true')
		document.optform.minihelp.checked = true;
	else
		document.optform.minihelp.checked = false;

	document.optform.popupDelay.value = localStorage["popupDelay"];
	document.optform.defaultDict.value = localStorage["defaultDict"];
	if (document.optform.defaultDict.value === "") {
		document.optform.defaultDict.value = document.optform.defaultDict[0].value;
		localStorage['defaultDict'] = document.optform.defaultDict.value;
	}

	if (localStorage['disablekeys'] == 'true')
		document.optform.disablekeys.checked = true;
	else
		document.optform.disablekeys.checked = false;

	if (localStorage['kanjicomponents'] == 'true')
		document.optform.kanjicomponents.checked = true;
	else
		document.optform.kanjicomponents.checked = false;

	for (var k of kanjiInfoKeys) {
		document.getElementById(k).checked = false;
	}
	for (var k of localStorage['kanjiinfo'].split(' ').filter(s => s.length > 0)) {
		document.getElementById(k).checked = true;
	}

	store = localStorage['lineEnding'];
	for (var i = 0; i < document.optform.lineEnding.length; ++i) {
		if (document.optform.lineEnding[i].value == store) {
			document.optform.lineEnding[i].selected = true;
			break;
		}
	}

	store = localStorage['copySeparator'];
	for (var i = 0; i < document.optform.copySeparator.length; ++i) {
		if (document.optform.copySeparator[i].value == store) {
			document.optform.copySeparator[i].selected = true;
			break;
		}
	}

	document.optform.maxClipCopyEntries.value = parseInt(localStorage['maxClipCopyEntries']);

	store = localStorage['showOnKey'];
	for (var i = 0; i < document.optform.showOnKey.length; ++i) {
		if (document.optform.showOnKey[i].value === store) {
			document.optform.showOnKey[i].checked = true;
			break;
		}
	}

}

function getVals() {
	localStorage['popupcolor'] = document.optform.popupcolor.value;
	localStorage['highlight'] = document.optform.highlighttext.checked;
	localStorage['textboxhl'] = document.optform.textboxhl.checked;
	localStorage['onlyreading'] = document.optform.onlyreading.checked;
	localStorage['minihelp'] = document.optform.minihelp.checked;
	localStorage['disablekeys'] = document.optform.disablekeys.checked;
	localStorage['kanjicomponents'] = document.optform.kanjicomponents.checked;

	var kanjiinfoarray = []
	for (var k of kanjiInfoKeys) {
		if(document.getElementById(k).checked) {
			kanjiinfoarray.push(k);
		}
	}
	localStorage['kanjiinfo'] = kanjiinfoarray.join(' ');

	localStorage['lineEnding'] = document.optform.lineEnding.value;
	localStorage['copySeparator'] = document.optform.copySeparator.value;
	localStorage['maxClipCopyEntries'] = document.optform.maxClipCopyEntries.value;

	var popupDelay;
	try {
		popupDelay = parseInt(document.optform.popupDelay.value);
		if (!isFinite(popupDelay)) {
			throw Error('infinite');
		}
		localStorage['popupDelay'] = document.optform.popupDelay.value;
	} catch (err) {
		popupDelay = 150;
		localStorage['popupDelay'] = "150";
	}
	localStorage['showOnKey'] = document.optform.showOnKey.value;
	localStorage['defaultDict'] = document.optform.defaultDict.value;

	// TODO config can be used directly from localStorage. No need to copy it every time
	// probably
	chrome.extension.getBackgroundPage().rcxMain.config.css = localStorage["popupcolor"];
	chrome.extension.getBackgroundPage().rcxMain.config.highlight = localStorage["highlight"];
	chrome.extension.getBackgroundPage().rcxMain.config.textboxhl = localStorage["textboxhl"];
	chrome.extension.getBackgroundPage().rcxMain.config.onlyreading = localStorage["onlyreading"];
	chrome.extension.getBackgroundPage().rcxMain.config.minihelp = localStorage["minihelp"];
	chrome.extension.getBackgroundPage().rcxMain.config.popupDelay = popupDelay;
	chrome.extension.getBackgroundPage().rcxMain.config.defaultDict = localStorage["defaultDict"];
	chrome.extension.getBackgroundPage().rcxMain.config.disablekeys = localStorage["disablekeys"];
	chrome.extension.getBackgroundPage().rcxMain.config.showOnKey = localStorage["showOnKey"];
	chrome.extension.getBackgroundPage().rcxMain.config.kanjicomponents = localStorage["kanjicomponents"];
	chrome.extension.getBackgroundPage().rcxMain.config.kanjiinfo = localStorage['kanjiinfo'];
	chrome.extension.getBackgroundPage().rcxMain.config.lineEnding = localStorage["lineEnding"];
	chrome.extension.getBackgroundPage().rcxMain.config.copySeparator = localStorage["copySeparator"];
	chrome.extension.getBackgroundPage().rcxMain.config.maxClipCopyEntries = localStorage["maxClipCopyEntries"];

	chrome.extension.getBackgroundPage().rcxMain.updateConfig();
}
window.onload = fillVals;

var inputs = document.querySelectorAll('.config');
for (var i = 0; i < inputs.length; ++i) {
	inputs[i].addEventListener('change', getVals);
	var type = inputs[i].getAttribute('type');
	if (type === 'number' || type === 'text') {
		inputs[i].addEventListener('input', getVals);
	}
}
