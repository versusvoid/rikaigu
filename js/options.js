var kanjiInfoKeys = ["H", "L", "E", "DK", "N", "V", "Y", "P", "IN", "I", "U"];

function loadValues() {
	for (var input of document.querySelectorAll('[bind]')) {
		if (input.getAttribute('type') === 'checkbox') {
			input.checked = localStorage[input.id] === 'true';
		} else if (localStorage[input.id]) {
			input.value = localStorage[input.id];
		}
	}

	document.optform.showOnKey.value = localStorage['showOnKey'] || "None";

	for (var k of kanjiInfoKeys) {
		document.getElementById(k).checked = false;
	}
	for (var k of localStorage['kanjiInfo'].split(' ').filter(s => s.length > 0)) {
		document.getElementById(k).checked = true;
	}
}

function saveValues() {
	for (var input of document.querySelectorAll('[bind]')) {
		if (input.getAttribute('type') === 'checkbox') {
			localStorage[input.id] = input.checked;
		} else if (localStorage[input.id]) {
			 localStorage[input.id] = input.value;
		}
	}

	localStorage['showOnKey'] = document.optform.showOnKey.value;

	var kanjiinfoarray = []
	for (var k of kanjiInfoKeys) {
		if(document.getElementById(k).checked) {
			kanjiinfoarray.push(k);
		}
	}
	localStorage['kanjiinfo'] = kanjiinfoarray.join(' ');

	chrome.extension.getBackgroundPage().updateConfig();
}

window.onload = loadValues;
var inputs = document.querySelectorAll('.config');
for (var i = 0; i < inputs.length; ++i) {
	inputs[i].addEventListener('change', saveValues);
	var type = inputs[i].getAttribute('type');
	if (type === 'number' || type === 'text') {
		inputs[i].addEventListener('input', saveValues);
	}
}
