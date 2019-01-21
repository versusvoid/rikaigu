"use strict";

class Deinflector {

	constructor(rulesArray, expressions) {
		const rules = [];
		for (var i = 0; i < rulesArray.length; ++i) {
			const columns = rulesArray[i].split('\t');
			if (columns.length !== 5) {
				console.error('Invalid line in `deinflect.dat`:', rulesArray[i]);
				continue;
			}

			var rulesGroupByLength = rules[columns[0].length];
			if (!rulesGroupByLength) {
				rulesGroupByLength = rules[columns[0].length] = {
					suffixLength: columns[0].length
				}
			}
			if (!(columns[0] in rulesGroupByLength)) {
				rulesGroupByLength[columns[0]] = [];
			}

			const rule = {
				from: columns[0],
				to: columns[1],
				sourceType: inflectionTypeToInt(columns[2].split('|'), true),
				targetType: inflectionTypeToInt(columns[3].split('|'), true),
				reason: columns[4]
			};
			rulesGroupByLength[rule.from].push(rule);
		}

		var allVerbsType = 0;
		for (var k in INFLECTION_TYPES) {
			if (k.startsWith('v')) {
				allVerbsType |= INFLECTION_TYPES[k];
			}
		}
		INFLECTION_TYPES['v'] = allVerbsType;

		var from = [];
		for(var i = 0; i < expressions.length; ++i) {
			const columns = expressions[i].split('\t');
			from.push(columns[0]);
			if (columns.length === 1) {
				continue;
			}
			if (columns.length != 6) {
				console.error('Invalid expression line:', expressions[i]);
				from = [];
				continue;
			}
			const rule = {
				from,
				sourceType: INFLECTION_TYPES[columns[1]],
				afterType: columns[2] === '*' ? INFLECTION_TYPES.__any__ : inflectionTypeToInt(columns[2].split('|'), true),
				//afterForms: columns[3] === '*' ? null : new Set(columns[3].split('|')),
				afterForms: new Set(columns[3].split('|')),
				offset: parseInt(columns[4]),
				senseIndices: columns[5]
			};

			for (var suffix of from) {
				var rulesGroupByLength = rules[suffix.length];
				if (!rulesGroupByLength) {
					rulesGroupByLength = rules[suffix.length] = {
						suffixLength: suffix.length
					}
				}
				if (!(suffix in rulesGroupByLength)) {
					rulesGroupByLength[suffix] = [];
				}
				rulesGroupByLength[suffix].push(rule);
			}
			from = [];
		}

		this._rules = rules.filter(o => !!o);
		//console.log(this._rules);
		this._expressionReplacementRules = [
			{
				suffix: '\u3070',
				form: 'provisional stem',
				expectedForms: new Set(['-ba'])
			},
			{
				suffix: '\u306a\u3044',
				form: 'negative stem',
				expectedForms: new Set(['negative'])
			},
			{
				suffix: '\u3044',
				form: 'adjective stem',
				type: INFLECTION_TYPES['adj-i'],
				expectedForms: new Set('negative')
			},
			{
				suffix: '',
				form: null
			}
		];
	}

	_checkExpression(conj) {
		var res = !conj.expressions || (conj.expressions[0].afterType & conj.type) !== 0;
		if (res && conj.expressions) {
			conj.expression = conj.expressions.map(e => e.from[0]).join('+');
			conj.type &= conj.expressions[0].afterType;
		}
		return res;
	}

	deinflect(word) {
		//console.log('deinflect(', word, ')');
		var r = [];
		var have = {};
		r.push({
			word,
		// Original word can have any type
			type: INFLECTION_TYPES.__any__,
			reason: ''
		});
		have[word] = 0;


		var i = -1;
		while (++i < r.length) {
			word = r[i].word;
			var wordLen = word.length;
			var type = r[i].type;

			for (var j = 0; j < this._rules.length; ++j) {
				var g = this._rules[j];
				if (g.suffixLength > wordLen) continue;

				var end = word.substr(-g.suffixLength);
				if (!(end in g)) continue;

				var rules = g[end];
				for (var k = 0; k < rules.length; ++k) {
					var rule = rules[k];
					// If rule isn't applicable to this word
					if ((type & rule.sourceType) === 0) continue;
					if (('expectedForms' in r[i])
							&& !r[i].expectedForms.has(rule.reason)
							&& !r[i].expectedForms.has('*')) {
						continue;
					}

					var newWord = word.substr(0, word.length - g.suffixLength);
					if ('to' in rule) {
						// Inflection
						newWord += rule.to;
						if (newWord.length <= 1) continue;
						if (newWord in have) {
							// If we have already obtained this new word through other
							// chain of deinflections - update only it's type.
							// We union types to denote that it can have any of these types
							r[have[newWord]].type = (o.type | rule.targetType);
							continue;
						}
						have[newWord] = r.length;

						var o = {};
						if (r[i].reason.length > 0) {
							o.reason = rule.reason + ' &lt; ' + r[i].reason;
						} else {
							o.reason = rule.reason;
						}
						if ('expressions' in r[i]) {
							o.expressions = r[i].expressions.slice();
						}
						// We know exact type of deinflected word -
						// it is specified by the rule we just applied
						o.type = rule.targetType;
						o.word = newWord;
						r.push(o);

					} else if (g.suffixLength < wordLen) {
						// Expression
						if ('expressions' in r[i] && (r[i].expressions[0].afterType & rule.sourceType) === 0) {
							continue;
						}

						var numSpecials = 0;
						if (rule.afterForms.has('negative stem')) {
							numSpecials += 1;
							var newSpecial = newWord + '\u306a\u3044';
							if (newWord === 'せ') {
								newSpecial = '\u3057\u306a\u3044';
							}
							if (newSpecial in have) {
								console.error("Well, that's strange", word, newSpecial);
								continue;
							}
							have[newSpecial] = r.length;

							r.push({
								reason: '',
								expressions: [rule],
								type: INFLECTION_TYPES['adj-i'],
								word: newSpecial,
								expectedForms: new Set(['negative', 'masu stem'])
							});
							if ('expressions' in r[i]) {
								Array.prototype.push.apply(r[r.length - 1].expressions, r[i].expressions);
							}
						}

						if (rule.afterForms.has('provisional stem')) {
							numSpecials += 1;
							const newSpecial = newWord + '\u3070';
							if (newSpecial in have) {
								console.error("Well, that's strange", word, newSpecial);
								continue;
							}
							have[newSpecial] = r.length;

							r.push({
								reason: '',
								expressions: [rule],
								type: INFLECTION_TYPES['raw'],
								word: newSpecial,
								expectedForms: new Set('-ba')
							});
							if ('expressions' in r[i]) {
								Array.prototype.push.apply(r[r.length - 1].expressions, r[i].expressions);
							}
						}

						if (rule.afterForms.has('adjective stem')) {
							numSpecials += 1;
							const newSpecial = newWord + '\u3044';
							if (newSpecial in have) {
								console.error("Well, that's strange", word, newSpecial);
								continue;
							}
							have[newSpecial] = r.length;

							r.push({
								reason: '',
								expressions: [rule],
								type: INFLECTION_TYPES['adj-i'],
								word: newSpecial,
								expectedForms: new Set('negative')
							});
							if ('expressions' in r[i]) {
								Array.prototype.push.apply(r[r.length - 1].expressions, r[i].expressions);
							}
						}

						if (numSpecials < rule.afterForms.size) {
							if (newWord in have) {
								console.error("Well, that's strange", word, newWord);
								continue;
							}
							have[newWord] = r.length;

							r.push({
								reason: '',
								expressions: [rule],
								type: INFLECTION_TYPES.__any__, //& rule.afterType,
								word: newWord,
								expectedForms: rule.afterForms
							});
							if ('expressions' in r[i]) {
								Array.prototype.push.apply(r[r.length - 1].expressions, r[i].expressions);
							}
						}
					}
				}
			}
		}

		//console.log(r);
		r =  r.filter(this._checkExpression, this);
		//console.log(r);
		return r;
	}


}
