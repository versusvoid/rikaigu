#include "dictionaries.h"
#include "deinflector.h"
#include "utils.h"

#include <emscripten.h>
#include <algorithm>
#include <memory>
#include <cstring>
#include <cassert>
#include <bitset>
#include <array>

struct IndexFile
{
	const char* content;
	uint32_t length;

	const uint32_t* offsets_start;
	const uint32_t* offsets_end;
	const char* index_start;
	const char* index_end;

	IndexFile()
		: content(nullptr)
		, length(0)
		, offsets_start(nullptr)
		, offsets_end(nullptr)
		, index_start(nullptr)
		, index_end(nullptr)
	{}

	void reset()
	{
		if (content != nullptr)
		{
			free((void*)content);
		}
		content = nullptr;
		length = 0;
		index_end = index_start = nullptr;
		offsets_start = offsets_end = nullptr;
	}

	void assign(const char* content, uint32_t length)
	{
		reset();

		this->content = content;
		this->length = length;

		uint32_t indices_length = *reinterpret_cast<const uint32_t*>(this->content);
		offsets_start = reinterpret_cast<const uint32_t*>(this->content) + 1;
		offsets_end = reinterpret_cast<const uint32_t*>(this->content + indices_length);

		index_start = this->content + indices_length;
		index_end = this->content + this->length;
	}
};


static IndexFile dictionary_index;

static IndexFile names_index;

struct KanjiIndexEntry
{
	uint32_t kanji_code_point;
	uint32_t offset;

	operator uint32_t() const
	{
		return kanji_code_point;
	}
};
static const KanjiIndexEntry* kanji_index = nullptr;
static uint32_t kanji_index_length = 0;

static string_view deinflect;
static std::shared_ptr<Deinflector> deinflector;


SearchResult::SearchResult()
	: max_match_symbols_length(0)
	, names(false)
	, more(false)
{}
SearchResult::SearchResult(const KanjiResult& kanji)
	: max_match_symbols_length(kanji.kanji.length() > 0 ? 1 : 0)
	, kanji(kanji)
{}

	// Katakana -> hiragana conversion tables
static const wchar_t ch[] = {
	0x3092, 0x3041, 0x3043, 0x3045, 0x3047, 0x3049, 0x3083, 0x3085, 0x3087, 0x3063, 0x30FC, 0x3042, 0x3044, 0x3046,
	0x3048, 0x304A, 0x304B, 0x304D, 0x304F, 0x3051, 0x3053, 0x3055, 0x3057, 0x3059, 0x305B, 0x305D, 0x305F, 0x3061,
	0x3064, 0x3066, 0x3068, 0x306A, 0x306B, 0x306C, 0x306D, 0x306E, 0x306F, 0x3072, 0x3075, 0x3078, 0x307B, 0x307E,
	0x307F, 0x3080, 0x3081, 0x3082, 0x3084, 0x3086, 0x3088, 0x3089, 0x308A, 0x308B, 0x308C, 0x308D, 0x308F, 0x3093
};
static const wchar_t cv[] = {
	0x30F4, 0xFF74, 0xFF75, 0x304C, 0x304E, 0x3050, 0x3052, 0x3054, 0x3056, 0x3058, 0x305A, 0x305C, 0x305E, 0x3060,
	0x3062, 0x3065, 0x3067, 0x3069, 0xFF85, 0xFF86, 0xFF87, 0xFF88, 0xFF89, 0x3070, 0x3073, 0x3076, 0x3079, 0x307C
};
static const wchar_t cs[] = {0x3071, 0x3074, 0x3077, 0x307A, 0x307D};

static const wchar_t long_vowel_mark_mapping_min = L'ぁ';
static const wchar_t long_vowel_mark_mapping_max = L'ゔ';
static const wchar_t long_vowel_mark_mapping[] = {
	/*ぁ:*/L'ー', /*あ:*/L'あ', /*ぃ:*/L'ー', /*い:*/L'い', /*ぅ:*/L'ー', /*う:*/L'う', /*ぇ:*/L'ー', /*え:*/L'い',
	/*ぉ:*/L'ー', /*お:*/L'う', /*か:*/L'あ', /*が:*/L'あ', /*き:*/L'い', /*ぎ:*/L'い', /*く:*/L'う', /*ぐ:*/L'う',
	/*け:*/L'い', /*げ:*/L'い', /*こ:*/L'う', /*ご:*/L'う', /*さ:*/L'あ', /*ざ:*/L'あ', /*し:*/L'い', /*じ:*/L'い',
	/*す:*/L'う', /*ず:*/L'う', /*せ:*/L'い', /*ぜ:*/L'い', /*そ:*/L'う', /*ぞ:*/L'う', /*た:*/L'あ', /*だ:*/L'あ',
	/*ち:*/L'い', /*ぢ:*/L'い', /*っ:*/L'\0', /*つ:*/L'う', /*づ:*/L'う', /*て:*/L'い', /*で:*/L'い', /*と:*/L'う',
	/*ど:*/L'う', /*な:*/L'あ', /*に:*/L'い', /*ぬ:*/L'う', /*ね:*/L'い', /*の:*/L'う', /*は:*/L'あ', /*ば:*/L'あ',
	/*ぱ:*/L'あ', /*ひ:*/L'い', /*び:*/L'い', /*ぴ:*/L'い', /*ふ:*/L'う', /*ぶ:*/L'う', /*ぷ:*/L'う', /*へ:*/L'い',
	/*べ:*/L'い', /*ぺ:*/L'い', /*ほ:*/L'う', /*ぼ:*/L'う', /*ぽ:*/L'う', /*ま:*/L'あ', /*み:*/L'い', /*む:*/L'う',
	/*め:*/L'い', /*も:*/L'う', /*ゃ:*/L'あ', /*や:*/L'あ', /*ゅ:*/L'う', /*ゆ:*/L'う', /*ょ:*/L'う', /*よ:*/L'う',
	/*ら:*/L'あ', /*り:*/L'い', /*る:*/L'う', /*れ:*/L'い', /*ろ:*/L'う', /*ゎ:*/L'ー', /*わ:*/L'あ', /*ゐ:*/L'い',
	/*ゑ:*/L'い', /*を:*/L'\0', /*ん:*/L'\0', /*ゔ:*/L'ー',
};

void drop_last_utf8(std::string& utf8_text)
{
	size_t j = utf8_text.length() - 1;
	while ((utf8_text.at(j) & 0b11000000) == 0b10000000)
	{
		j -= 1;
	}
	utf8_text.resize(j);
}

wchar_t utf16_to_wchar(const char16_t* utf16)
{
	if (*utf16 >= 0xD800 && *utf16 <= 0xDBFF)
	{
		return 0x10000 + (wchar_t(*utf16 - 0xD800) << 10) + wchar_t(*(utf16 + 1) - 0xDC00);
	}
	else
	{
		return *utf16;
	}
}

wchar_t kata_to_hira_character(const wchar_t c, const wchar_t previous, std::vector<wchar_t> out)
{
	// Full-width katakana to hiragana
	if (c >= L'ァ' && c <= L'ン')
	{
		return c - 0x60;
	}
	// Half-width katakana to hiragana
	else if (c >= L'ｦ' && c <= L'ﾝ')
	{
		return ch[c - L'ｦ'];
	}
	// Voiced (used in half-width katakana) to hiragana
	else if (c == L'ﾞ')
	{
		if (previous >= L'ｳ' && previous <= L'ﾎ')
		{
			out.pop_back();
			return cv[previous - L'ｳ'];
		}
	}
	// Semi-voiced (used in half-width katakana) to hiragana
	else if (c == L'ﾟ')
	{
		if (previous >= L'ﾊ' && previous <= L'ﾎ')
		{
			out.pop_back();
			return cs[previous - L'ﾊ'];
		}
	}
	else if (c == L'ー' && previous != 0 && previous >= long_vowel_mark_mapping_min && previous <= long_vowel_mark_mapping_max)
	{
		auto mapped = long_vowel_mark_mapping[previous - long_vowel_mark_mapping_min];
		//printf("Have long vovel and mapped: %d\n", mapped);
		if (mapped != 0)
		{
			return mapped;
		}
	}
	return c;
}

std::pair<std::string, std::vector<size_t>> kata_utf16_to_hira_utf8(const char16_t* utf16_text)
{
	std::vector<wchar_t> res;
	std::vector<size_t> code_points_length_mapping;

	size_t in_offset = 0;
	size_t num_code_points = 0;
	while (utf16_text[in_offset] != 0)
	{
		wchar_t c = utf16_to_wchar(utf16_text + in_offset);
		if (c > 0xFFFF)
		{
			in_offset += 2;
		}
		else
		{
			in_offset += 1;
		}
		num_code_points += 1;

		if (c <= 0x3000 || c == L'～')
		{
			break;
		}

		c = kata_to_hira_character(c, res.size() > 0 ? res.back() : 0, res);
		res.push_back(c);

		if (code_points_length_mapping.size() < res.size())
		{
			code_points_length_mapping.push_back(num_code_points);
		}
		else
		{
			code_points_length_mapping.back() = num_code_points;
		}
	}
	res.push_back(L'\0');

	std::string utf8;
	utf8.resize(res.size()*4);
	size_t written = wcstombs(utf8.data(), res.data(), utf8.size());
	if (written == size_t(-1))
	{
		utf8.clear();
		code_points_length_mapping.clear();
		printf("Error converting to utf8");
	}
	else
	{
		utf8.resize(written);
	}
	return {utf8, code_points_length_mapping};
}

std::vector<uint32_t> find(IndexFile* index, const std::string& word)
{
	PROFILE
	//printf("find(%s)\n", word.c_str());

	const char* beg = index->index_start;
	const char* end = index->index_end;

	long indices_offset = -1;
	while (beg < end) {
		const char* mi = reinterpret_cast<const char*>((intptr_t(beg) + intptr_t(end)) >> 1);
		const char* word_start = std::find(
				std::make_reverse_iterator(mi),
				std::make_reverse_iterator(beg),
				char(0b11111000)
			).base();
		if (word_start > beg)
		{
			word_start += 3;
		}
		const char* word_end = std::find(mi, end, char(0b11111000));

		int order = word.compare(0, word.length(), word_start, size_t(word_end - word_start));
		if (order < 0) {
			end = word_start;
		} else if (order > 0) {
			beg = word_end + 4;
		} else {
			beg = word_end + 4;
			indices_offset = word_end[1] | (word_end[2] << 7) | (word_end[3] << 14);
			break;
		}
	}
	if (indices_offset == -1)
	{
		return std::vector<uint32_t>();
	}

	const uint32_t* offsets_start = index->offsets_start + indices_offset;
	const uint32_t* offsets_end = index->offsets_end;

	if (beg < index->index_end)
	{
		const char* next_word_end = std::find(beg, index->index_end, char(0b11111000));
		offsets_end = index->offsets_start + (
			next_word_end[1] | (next_word_end[2] << 7) | (next_word_end[3] << 14)
		);
	}

	return std::vector<uint32_t>(offsets_start, offsets_end);
}

static bool compare(WordResult& a, WordResult& b)
{
	// TODO match source and target script (katakana, hiragana)
	// and, generally, use better model, you dummy
	if (a.dentry.freq() != b.dentry.freq())
	{
		return a.score() < b.score();
	}
	if (a.match_symbols_length != b.match_symbols_length)
	{
		return a.match_symbols_length > b.match_symbols_length;
	}
	if (a.dentry.name() != b.dentry.name())
	{
		return a.dentry.name() < b.dentry.name();
	}
	return a.reason.empty() > b.reason.empty();
}

static size_t line_buffer_size = 0;
static char* line = nullptr;

void squash_names(std::vector<WordResult>& res)
{
	for (auto i = 1U; i < res.size(); ++i)
	{
		if (res[i - 1].match_symbols_length != res[i].match_symbols_length) continue;
		if (res[i - 1].dentry.try_join(res[i].dentry))
		{
			res.erase(res.begin() + i);
			i -= 1;
		}
	}
}

const std::size_t MAX_ENTRIES = 32;
inline void sort_and_limit(SearchResult& res)
{
	// Sort by match length and then by commonnesss
	std::sort(res.data.begin(), res.data.end(), compare);
	squash_names(res.data);
	if (res.data.size() > MAX_ENTRIES) {
		res.more = true;
	}
	res.data.erase(res.data.begin() + std::min(MAX_ENTRIES, res.data.size()), res.data.end());
}

SearchResult word_search(std::string utf8_text, std::vector<size_t> code_points_length_mapping, bool names_dictionary)
{
	PROFILE
	//std::cout << "word_search( " << word << " )" << std::endl;
	SearchResult result;
	result.source = utf8_text;

	FILE* dict = nullptr;
	IndexFile* index = nullptr;
	int maxTrim = 0;

	if (names_dictionary)
	{
		dict = fopen("names.dat", "r");
		index = &names_index;
		maxTrim = 7;
		result.names = true;
	}
	else
	{
		dict = fopen("dict.dat", "r");
		index = &dictionary_index;
		maxTrim = 5;
	}

	if (line == nullptr)
	{
		line_buffer_size = 1024;
		line = reinterpret_cast<char*>(malloc(line_buffer_size));
	}

	size_t max_length = 0;
	std::map<std::string, std::vector<uint32_t>> cache;
	std::set<size_t> have;
	int count = 0;
	while (utf8_text.length() > 0)
	{
		std::list<Candidate> trys;

		if (names_dictionary)
		{
			trys.emplace_back(utf8_text, 0);
		}
		else
		{
			trys = deinflector->deinflect(utf8_text);
		}

		for (auto candidate_it = trys.begin(); candidate_it != trys.end(); ++candidate_it)
		{
			Candidate& u = *candidate_it;

			auto it = cache.find(u.word);
			if (it == cache.end())
			{
				std::vector<uint32_t> ix = find(index, u.word);
				it = cache.insert(std::make_pair(u.word, ix)).first;
			}

			for (auto ofs : it->second)
			{
				if (have.count(ofs) > 0) continue;

				fseek(dict, ofs, SEEK_SET);
				ssize_t line_length = getline(&line, &line_buffer_size, dict);
				if (line_length == -1)
				{
					std::cerr << "Too bad" << std::endl;
					continue;
				}
				//printf("Line at index %u for word '%s' is '%.*s'\n", ofs, u.word.c_str(), line_length, line);
				//std::cout << "dentry: " << std::string(line, line_length - 1) << std::endl;

				DEntry dentry(ofs, std::string(line, line_length - 1), names_dictionary);
				if (names_dictionary)
				{
					dentry.filter_writings(utf8_text);
				}

				// > second and further - a de-inflected word.
				// Each type has associated bit. If bit-and gives 0
				// than deinflected word does not match this dentry.
				if (candidate_it != trys.begin() && (dentry.all_pos() & u.type) == 0)
				{
					//std::cout << "Mismatch: "
						//<< std::bitset<32>(dentry.all_pos()).to_string() << " and "
						//<< std::bitset<32>(u.type).to_string() << std::endl;
					continue;
				}
				// TODO confugirable number of entries
				if (count >= maxTrim)
				{
					result.more = true;
					if (names_dictionary) break;
				}

				have.insert(ofs);
				++count;

				if (max_length == 0)
				{
					max_length = code_points_length_mapping.back();
				}

				result.data.emplace_back(dentry, u.reason, code_points_length_mapping.back(), utf8_text.length());
			}
		}
		if (count >= maxTrim) break;

		drop_last_utf8(utf8_text);
		code_points_length_mapping.pop_back();
	} // while word.length > 0

	fclose(dict);

	if (!names_dictionary)
	{
		sort_and_limit(result);
	}

	result.max_match_symbols_length = max_length;
	return result;
}

std::string find_kanji(const uint32_t kanji_code_point)
{
	auto entry = std::lower_bound(kanji_index, kanji_index + kanji_index_length, kanji_code_point);
	if (entry == kanji_index + kanji_index_length) return "";

	FILE* kanji_dict = fopen("kanji.dat", "r");
	fseek(kanji_dict, entry->offset, SEEK_SET);
	ssize_t line_length = getline(&line, &line_buffer_size, kanji_dict);
	if (line_length == -1)
	{
		std::cerr << "Tooo bad" << std::endl;
		return "";
	}
	std::string result(line, line_length - 1);
	fclose(kanji_dict);
	return result;
}

static const char* hex = "0123456789ABCDEF";
KanjiResult kanji_search(const char16_t* kanji)
{
	KanjiResult result;

	wchar_t kanji_code = utf16_to_wchar(kanji);
	if (kanji_code < 0x3000)
	{
		return result;
	}


	std::string kanji_definition = find_kanji(uint32_t(kanji_code));
	if (kanji_definition.empty())
	{
		return result;
	}

	auto parts = split(kanji_definition, '|');
	if (parts.size() != 6)
	{
		return result;
	}

	result.kanji = parts.at(0);
	std::string& code = result.misc["U"];
	for (int i = (kanji_code > 0xFFFF ? (kanji_code > 0xFFFFF ? 20 : 16) : 12); i >= 0; i -= 4)
	{
		code.push_back(hex[(kanji_code >> i) & 15]);
	}

	for (auto& b : split(parts.at(1), ' '))
	{
		size_t i = 0;
		while (i < b.length() and b[i] >= 'A' and b[i] <= 'Z')
		{
			i += 1;
		}
		if (i == 0) continue;
		std::string key = b.substr(0, i);
		auto it = result.misc.find(key);
		if (it == result.misc.end())
		{
			result.misc[key] = b.substr(i);
		}
		else
		{
			it->second.push_back(' ');
			it->second.append(b.substr(i));
		}
	}


	result.onkun = split(parts.at(2), ' ');
	for (auto& part : split(parts.at(3), ' '))
	{
		if (!result.nanori.empty())
		{
			result.nanori += u8"、 ";
		}
		result.nanori += part;
	}
	for (auto& part : split(parts.at(4), ' '))
	{
		if (!result.bushumei.empty())
		{
			result.bushumei += u8"、 ";
		}
		result.bushumei += part;
	}
	result.eigo = parts.at(5);

	return result;
}

SearchResult search(const char16_t* utf16_text)
{
	PROFILE
	Dictionary dictionary = config.default_dictionary;
	const auto& [utf8, code_points_length_mapping] = kata_utf16_to_hira_utf8(utf16_text);
	//printf("Converted to: %s\n", utf8.c_str());

	SearchResult res;
	do
	{
		switch (dictionary)
		{
			case WORDS:
				res = word_search(utf8, code_points_length_mapping, false);
				if (dictionary == config.default_dictionary)
				{
					SearchResult res2 = word_search(utf8, code_points_length_mapping, true);
					res.data.insert(res.data.end(), res2.data.begin(), res2.data.end());
					res.max_match_symbols_length = std::max(res.max_match_symbols_length, res2.max_match_symbols_length);
					sort_and_limit(res);
				}
				break;
			case NAMES:
				res = word_search(utf8, code_points_length_mapping, true);
				break;
			case KANJI:
				res = kanji_search(utf16_text);
				break;
		}
		if (res.max_match_symbols_length > 0) break;
		dictionary = Dictionary((dictionary + 1) % 3);

	} while (dictionary != config.default_dictionary);

	return res;
}

bool dictionaries_init(const char* filename, const char* content, uint32_t length)
{
	if (0 == strcmp(filename, "data/dict.idx"))
	{
		dictionary_index.assign(content, length);
	}
	else if (0 == strcmp(filename, "data/names.idx"))
	{
		names_index.assign(content, length);
	}
	else if (0 == strcmp(filename, "data/kanji.idx"))
	{
		static_assert(sizeof(KanjiIndexEntry) == 8, "Expected KanjiIndexEntry to take 8 bytes");
		static_assert(alignof(KanjiIndexEntry) == 4, "Expected KanjiIndexEntry to align at 4 bytes");
		kanji_index = reinterpret_cast<const KanjiIndexEntry*>(content);
		kanji_index_length = length / sizeof (KanjiIndexEntry);
	}
	else if (0 == strcmp(filename, "data/deinflect.dat"))
	{
		deinflect.assign(content, length);
		deinflector = std::make_shared<Deinflector>(deinflect);
		deinflect.reset();
	}

	return true;
}
