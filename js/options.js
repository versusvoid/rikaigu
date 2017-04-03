var kanjiInfoKeys = ["H", "L", "E", "DK", "N", "V", "Y", "P", "IN", "I", "U"];

function loadValues() {
	chrome.storage.local.get(null, function(config) {
		for (var input of document.querySelectorAll('[bind]')) {
			if (input.getAttribute('type') === 'checkbox') {
				input.checked = config[input.id];
			} else {
				 input.value = config[input.id];
			}
		}

		for (var k of kanjiInfoKeys) {
			document.getElementById(k).checked = false;
		}
		for (var k of config['kanjiInfo'].split(' ').filter(s => s.length > 0)) {
			document.getElementById(k).checked = true;
		}
	});
}

function saveValues() {
	var newConfig = {}
	for (var input of document.querySelectorAll('[bind]')) {
		if (input.getAttribute('type') === 'checkbox') {
			newConfig[input.id] = input.checked;
		} else {
			 newConfig[input.id] = input.value;
		}
	}

	var kanjiinfoarray = []
	for (var k of kanjiInfoKeys) {
		if(document.getElementById(k).checked) {
			kanjiinfoarray.push(k);
		}
	}
	newConfig['kanjiInfo'] = kanjiinfoarray.join(' ');

	chrome.storage.local.set(newConfig);
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
chrome.storage.onChanged.addListener(loadValues);
