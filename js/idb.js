
export async function getDictionaryFiles() {
	const db = await getFilesDb();
	const transaction = db.transaction(['files']);
	const filesStore = transaction.objectStore('files');
	return Promise.all([getFile('names', filesStore), getFile('words', filesStore)]);
}

function getFilesDb() {
	if (window.filesDb) {
		return window.filesDb;
	}

	return new Promise(function(resolve, reject) {
		const request = indexedDB.open('files');
		request.onerror = reject;
		request.onsuccess = (event) => {
			window.filesDb = event.target.result;
			resolve(event.target.result);
		};
		request.onupgradeneeded = (event) => {
			event.target.result.createObjectStore('files');
		};
	});
}

function getFile(fileName, filesStore) {
	return new Promise(function(resolve, reject) {
		const request = filesStore.get(fileName);
		request.onerror = (event) => resolve(null);
		request.onsuccess = (event) => resolve(event.target.result);
	});
}

function setStoreValue(store, key, value) {
	return new Promise(function(resolve, reject) {
		const request = store.put(value, key);
		request.onerror = (event) => reject(event);
		request.onsuccess = (event) => resolve(event.target.result);
	});
}

export async function setFile(fileName, file) {
	const db = await getFilesDb();
	const transaction = db.transaction(['files'], 'readwrite');
	const filesStore = transaction.objectStore('files');

	await setStoreValue(filesStore, fileName, file);
}
