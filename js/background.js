var translateCache = {__count__: 0};
rcxMain.clearState();
chrome.browserAction.onClicked.addListener(rcxMain.inlineToggle);
chrome.tabs.onSelectionChanged.addListener(rcxMain.onTabSelect);
chrome.runtime.onMessage.addListener(
	function(request, sender, response) {
		switch (request.type) {
			case 'enable?':
				console.log('enable?');
				rcxMain.onTabSelect(sender.tab.id);
				break;
			case 'xsearch':
				console.log('xsearch');
				var matchLengthPtr = Module._malloc(4);
				var prefixLengthPtr = Module._malloc(4);
				var html = Module.ccall('rikaigu_search', 'string', ['string', 'string', 'number'],
						[request.text, request.prefix, request.dictOption, matchLengthPtr, prefixLengthPtr]);
				var matchLen = Module.getValue(matchLengthPtr, 'i32');
				var prefixLength = Module.getValue(prefixLengthPtr, 'i32');
				Module._free(matchLengthPtr);
				Module._free(prefixLengthPtr);
				response({type: request.type, html, matchLen, prefixLength});
				//Module.ccall('rikaigu_dump_profile_info', null, []);
				break;
			case 'resetDict':
				console.log('resetDict');
				rcxMain.resetDict();
				break;
			case 'translate':
				console.log('translate');
				if (request.title in translateCache) {
					var res = translateCache[request.title];
					res.lastAccess = new Date().getTime();
					response({type: request.type, html: res.html});
				} else {
					var html = Module.ccall('rikaigu_translate', 'string', ['string'], [request.title]);
					if (request.title.length < 1000) {
						translateCache[request.title] = {
							html,
							lastAccess: new Date().getTime()
						};
						translateCache.__count__ += 1;
						while (translateCache.__count__ > 10) {
							var min = translateCache[request.title].lastAccess, argmin = request.title;
							for (var k in translateCache) {
								if (translateCache[k].lastAccess && min > translateCache[k].lastAccess) {
									min = translateCache[k].lastAccess;
									argmin = k;
								}
							}
							delete translateCache[argmin];
							translateCache.__count__ -= 1;
						}
					}
					response({type: request.type, html});
				}
				//response({type: request.type, html: null, entry: e});
				break;
			case 'makehtml':
				console.error('makehtml');
				//var html = rcxMain.dict.makeHtml(request.entry);
				//response(html);
				break;
			case 'switchOnlyReading':
				console.log('switchOnlyReading');
				if (rcxMain.config.onlyreading == 'true')
					rcxMain.config.onlyreading = 'false';
				else
					rcxMain.config.onlyreading = 'true';
				localStorage['onlyreading'] = rcxMain.config.onlyreading;
				rcxMain.updateConfig();
				break;
			case 'copyToClip':
				console.log('copyToClip');
				rcxMain.copyToClip(sender.tab, request.entry);
				break;
			default:
				console.log(request);
		}
	});

// FIXME is this condition necessary?
if (initStorage("v0.9.4", true)) {
	// v0.7
	initStorage("popupcolor", "blue");
	initStorage("highlight", true);

	// v0.8
	// No changes to options

	// V0.8.5
	initStorage("textboxhl", false);

	// v0.8.6
	initStorage("onlyreading", false);
	// v0.8.8
	if (localStorage['highlight'] == "yes")
		localStorage['highlight'] = "true";
	if (localStorage['highlight'] == "no")
		localStorage['highlight'] = "false";
	if (localStorage['textboxhl'] == "yes")
		localStorage['textboxhl'] = "true";
	if (localStorage['textboxhl'] == "no")
		localStorage['textboxhl'] = "false";
	if (localStorage['onlyreading'] == "yes")
		localStorage['onlyreading'] = "true";
	if (localStorage['onlyreading'] == "no")
		localStorage['onlyreading'] = "false";
	initStorage("copySeparator", "tab");
	initStorage("maxClipCopyEntries", "7");
	initStorage("lineEnding", "n");
	initStorage("minihelp", "true");
	initStorage("disablekeys", "false");
	initStorage("kanjicomponents", "true");

	for (i = 0; i * 2 < rcxDict.prototype.numList.length; i++) {
		initStorage(rcxDict.prototype.numList[i * 2], "true")
	}

	// v0.8.92
	initStorage("popupDelay", "150");
	initStorage("showOnKey", "");

	// v0.9.2
	initStorage("defaultDict", "words");
}
initStorage('kanjiinfo', 'H L E DK N V Y P IN I U');

/**
 * Initializes the localStorage for the given key.
 * If the given key is already initialized, nothing happens.
 *
 * @author Teo (GD API Guru)
 * @param key The key for which to initialize
 * @param initialValue Initial value of localStorage on the given key
 * @return true if a value is assigned or false if nothing happens
 */
function initStorage(key, initialValue) {
	var currentValue = localStorage[key];
	if (!currentValue) {
		localStorage[key] = initialValue;
		return true;
	}
	return false;
}

rcxMain.config = {};
rcxMain.config.css = localStorage["popupcolor"];
rcxMain.config.highlight = localStorage["highlight"];
rcxMain.config.textboxhl = localStorage["textboxhl"];
rcxMain.config.onlyreading = localStorage["onlyreading"];
rcxMain.config.copySeparator = localStorage["copySeparator"];
rcxMain.config.maxClipCopyEntries = localStorage["maxClipCopyEntries"];
rcxMain.config.lineEnding = localStorage["lineEnding"];
rcxMain.config.minihelp = localStorage["minihelp"];
rcxMain.config.popupDelay = parseInt(localStorage["popupDelay"]);
rcxMain.config.disablekeys = localStorage["disablekeys"];
rcxMain.config.showOnKey = localStorage["showOnKey"];
rcxMain.config.kanjicomponents = localStorage["kanjicomponents"];
rcxMain.config.kanjiinfo = localStorage['kanjiinfo'];
rcxMain.config.defaultDict = localStorage["defaultDict"];

