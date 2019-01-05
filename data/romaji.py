import re
import sys

conversion_table = {
	"あ": ["a"],
	"い": ["i"],
	"う": ["u"],
	"え": ["e"],
	"お": ["o"],
	"か": ["ka"],
	"が": ["ga"],
	"き": ["ki"],
	"きゃ": ["kya"],
	"きゅ": ["kyu"],
	"きょ": ["kyo"],
	"ぎ": ["gi"],
	"ぎゃ": ["gya"],
	"ぎゅ": ["gyu"],
	"ぎょ": ["gyo"],
	"く": ["ku"],
	"ぐ": ["gu"],
	"け": ["ke"],
	"げ": ["ge"],
	"こ": ["ko"],
	"ご": ["go"],
	"さ": ["sa"],
	"ざ": ["za"],
	"し": ["shi", "si"],
	"しぃ": ["shii"],
	"しぇ": ["she"],
	"しゃ": ["sha", "sya"],
	"しゅ": ["shu", "syu"],
	"しょ": ["sho", "syo"],
	"じ": ["ji", "zi"],
	"じぇ": ["je", "ze"],
	"じゃ": ["zya", "ja"],
	"じゅ": ["zyu", "ju"],
	"じょ": ["zyo", "jo"],
	"す": ["su"],
	"ず": ["zu"],
	"せ": ["se"],
	"ぜ": ["ze"],
	"そ": ["so"],
	"ぞ": ["zo"],
	"た": ["ta"],
	"だ": ["da"],
	"ち": ["chi", "ti"],
	"ちぃ": ["chii"],
	"ちぇ": ["che", "te"],
	"ちゃ": ["cha", "tya"],
	"ちゅ": ["chu", "tyu"],
	"ちょ": ["cho", "tyo"],
	"ぢ": ["dzi", "dji", "ji", "di", "zi"],
	"ぢゃ": ["dya", "dja", "dza", "zya", "ja"],
	"ぢゅ": ["dyu", "dju", "dzu", "zyu", "ju"],
	"ぢょ": ["dyo", "djo", "dzo", "zyo", "jo"],
	"つ": ["tsu", "tu"],
	"づ": ["dzu", "du", "zu"],
	"て": ["te"],
	"てぃ": ["ti"],
	"で": ["de"],
	"と": ["to"],
	"ど": ["do"],
	"な": ["na"],
	"に": ["ni"],
	"にゃ": ["nya"],
	"にゅ": ["nyu"],
	"にょ": ["nyo"],
	"ぬ": ["nu"],
	"ね": ["ne"],
	"の": ["no"],
	"は": ["ha"],
	"ば": ["ba"],
	"ぱ": ["pa"],
	"ひ": ["hi"],
	"ひゃ": ["hya"],
	"ひゅ": ["hyu"],
	"ひょ": ["hyo"],
	"び": ["bi"],
	"びゃ": ["bya"],
	"びゅ": ["byu"],
	"びょ": ["byo"],
	"ぴ": ["pi"],
	"ぴゃ": ["pya"],
	"ぴゅ": ["pyu"],
	"ぴょ": ["pyo"],
	"ふ": ["fu", "hu"],
	"ふぁ": ["fa", "ha"],
	"ふぉ": ["fo", "ho"],
	"ぶ": ["bu"],
	"ぷ": ["pu"],
	"ぷぅ": ["puu", "puu"],
	"へ": ["he"],
	"べ": ["be"],
	"ぺ": ["pe"],
	"ほ": ["ho"],
	"ぼ": ["bo"],
	"ぽ": ["po"],
	"ま": ["ma"],
	"み": ["mi"],
	"みぃ": ["mii"],
	"みゃ": ["mya"],
	"みゅ": ["myu"],
	"みょ": ["myo"],
	"む": ["mu"],
	"め": ["me"],
	"も": ["mo"],
	"や": ["ya"],
	"ゆ": ["yu"],
	"よ": ["yo"],
	"ら": ["ra"],
	"り": ["ri"],
	"りぃ": ["rii"],
	"りゃ": ["rya"],
	"りゅ": ["ryu"],
	"りょ": ["ryo"],
	"る": ["ru"],
	"るぅ": ["ruu"],
	"れ": ["re"],
	"れぇ": ["re"],
	"ろ": ["ro"],
	"わ": ["wa"],
	"ゐ": ["i", "wi"],
	"ゑ": ["e", "we"],
	"を": ["o", "wo"],
	"ん": ["n'", "n", "m"],
}

for k, values in list(conversion_table.items()):
	conversion_table[k + 'ー'] = [v + v[-1] for v in values]
for k, values in list(conversion_table.items()):
	conversion_table['っ' + k] = [v[0] + v for v in values]

conversion_table["ああ"] = ["aa", "ā"]
conversion_table["いい"] = ["ii", "ī"]
conversion_table["うう"] = ["uu", "ū"]
conversion_table["えい"] = ["ei", "ē"]
conversion_table["ええ"] = ["ee", "ē"]
conversion_table["おう"] = ["ou", "ō"]
conversion_table["おお"] = ["oo", "ō"]

skip = 180
count = 0
def is_romajination(hiragana, word):
	global skip, count
	if len(word) < len(hiragana):
		return False
	# original_hiragana = hiragana
	word = word.lower()
	original_word = word
	while len(hiragana) > 0 and len(word) > 0:
		for i in range(4, 0, -1):
			values = conversion_table.get(hiragana[:i])
			if values is None:
				continue
			for v in values:
				if word.startswith(v):
					hiragana = hiragana[i:]
					word = word[len(v):]
					break
			else:
				continue
			break
		else:
			break

	res = len(hiragana) == 0 and len(word) == 0
	if not res and re.fullmatch('[a-z]+', original_word) is not None:
		count += 1
		#print(count, original_hiragana, original_word, file=sys.stderr)
		if count > skip:
			#input()
			pass
	return res
