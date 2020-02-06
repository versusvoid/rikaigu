
import { getDictionaryFiles, setFile } from '/js/idb.js';

async function init() {
	[window.namesDictionary, window.wordsDictionary] = await getDictionaryFiles();
	const inputs = document.getElementsByTagName('input');
	for (const input of inputs) {
		initInput(input);
	}
}

function initInput(inputElement) {
	const dictionary = window[`${inputElement.name}Dictionary`];
	if (dictionary) {
		//inputElement.files[0] = dictionary;
		console.log(inputElement.name, dictionary);
		// TODO display
	}
	inputElement.disabled = false;
	inputElement.addEventListener('change', uploadDictionary);
}

async function uploadDictionary(event) {
	const inputElement = event.target;
	if (inputElement.files.length === 0) {
		return;
	}

	inputElement.disabled = true;
	await setFile(inputElement.name, inputElement.files[0]);
	inputElement.disabled = false;
}

window.addEventListener('load', init);
