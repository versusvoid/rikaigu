// We map types to bit flags for fast intersection operation
var INFLECTION_TYPES = {
	__next__: 1,
	__any__: 0
};
function inflectionTypeToInt(typesArray, initNew) {
	var type_int = 0;
	typesArray.forEach(function(type) {
		if (!(type in INFLECTION_TYPES)) {
			if (!initNew) return;
			var type_bit = INFLECTION_TYPES.__next__;
			INFLECTION_TYPES.__next__ = (INFLECTION_TYPES.__next__ << 1);
			INFLECTION_TYPES.__any__ = (INFLECTION_TYPES.__any__ | type_bit);
			INFLECTION_TYPES[type] = type_bit;
		}
		type_int = (type_int | INFLECTION_TYPES[type]);
	});
	return type_int;
}

class Entry {

	constructor(dictionaryLine) {
		const parts = dictionaryLine.split('\t');
		this._kanjiString = parts[0];
		if (parts.length === 4 || (parts.length === 3 && /^\d+$/.test(parts[parts.length - 1]))) {
			this._freqString = parts[parts.length - 1];
			this._definitionString = parts[parts.length - 2];
			this._readingsString = (parts.length === 4 ? parts[1] : '');
		} else {
			this._freq = 1e9;
			this._definitionString = parts[parts.length - 1];
			this._readingsString = (parts.length === 3 ? parts[1] : '');
		}
	}


	_parseFreq() {
		this._freq = parseInt(this._freqString);
		return this._freq;
	}

	get freq() {
		return this._freq || this._parseFreq();
	}


	_parseSenseGroups() {
		this._senseGroups = this._definitionString.split('\\');
		this._allPos = 0;
		for (var i = 0; i < this._senseGroups.length; ++i) {
			const groupString = this._senseGroups[i];
			const p = groupString.indexOf(';');
			this._senseGroups[i] = {
				pos: groupString.substring(0, p).split(','),
				senses: groupString.substring(p + 1).split('`')
			}
			this._allPos |= inflectionTypeToInt(this._senseGroups[i].pos);
		}
		return [this._senseGroups, this._allPos];
	}

	get senseGroups() {
		return this._senseGroups || this._parseSenseGroups()[0];
	}

	get allPos() {
		return this._allPos || this._parseSenseGroups()[1];
	}


	_parseReadings() {
		this._readings = this._readingsString.split(';');
		this._allReadingsIndices = [];
		for (var i = 0; i < this._readings.length; ++i) {
			this._allReadingsIndices.push(i);
			const parts = this._readings[i].split('|');
			this._readings[i] = {
				text: parts[0],
				uncommon: parts.length > 1
			};
		}
		return this._readings;
	}

	get readings() {
		return this._readings || this._parseReadings();
	}


	_parseKanjiGroups() {
		this._kanjiGroups = this._kanjiString.split(';');
		for (var i = 0; i < this._kanjiGroups.length; ++i) {
			const parts = this._kanjiGroups[i].split('#');

			var readings = this._allReadingsIndices;
			if (parts.length > 1) {
				readings = parts[1].split(',').map(function(i) { return parseInt(i); });
			}

			const kanjis = parts[0].split(',').map(function(k) {
				const parts = k.split('|');
				return {
					text: parts[0],
					uncommon: parts.length > 1
				};
			});

			this._kanjiGroups[i] = { readings, kanjis };
		}
		return this._kanjiGroups;
	}

	get kanjiGroups() {
		return this._kanjiGroups || this._parseKanjiGroups();
	}

}
