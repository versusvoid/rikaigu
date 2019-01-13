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
static string_view expressions;
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
static wchar_t ch[] = {
	0x3092, 0x3041, 0x3043, 0x3045, 0x3047, 0x3049, 0x3083, 0x3085, 0x3087, 0x3063, 0x30FC, 0x3042, 0x3044, 0x3046,
	0x3048, 0x304A, 0x304B, 0x304D, 0x304F, 0x3051, 0x3053, 0x3055, 0x3057, 0x3059, 0x305B, 0x305D, 0x305F, 0x3061,
	0x3064, 0x3066, 0x3068, 0x306A, 0x306B, 0x306C, 0x306D, 0x306E, 0x306F, 0x3072, 0x3075, 0x3078, 0x307B, 0x307E,
	0x307F, 0x3080, 0x3081, 0x3082, 0x3084, 0x3086, 0x3088, 0x3089, 0x308A, 0x308B, 0x308C, 0x308D, 0x308F, 0x3093
};
static wchar_t cv[] = {
	0x30F4, 0xFF74, 0xFF75, 0x304C, 0x304E, 0x3050, 0x3052, 0x3054, 0x3056, 0x3058, 0x305A, 0x305C, 0x305E, 0x3060,
	0x3062, 0x3065, 0x3067, 0x3069, 0xFF85, 0xFF86, 0xFF87, 0xFF88, 0xFF89, 0x3070, 0x3073, 0x3076, 0x3079, 0x307C
};
static wchar_t cs[] = {0x3071, 0x3074, 0x3077, 0x307A, 0x307D};

struct KanaConvertor
{
	wchar_t previous;
	std::string out;
	size_t out_offset;
	std::vector<size_t> true_length_mapping;

	KanaConvertor()
		: previous(0)
		, out_offset(0)
		, true_length_mapping({0})
	{}

	void reserve(const size_t bytes)
	{
		out.resize(bytes);
	}

	void drop_last()
	{
		size_t j = out_offset - 1;
		while ((out.at(j) & 0b11000000) == 0b10000000) {
			j -= 1;
		}
		out_offset = j;
	}

	void shrink()
	{
		out.resize(out_offset);
	}

	bool operator() (const size_t i, wchar_t u, const char*, const size_t)
	{
		// Half & full-width katakana to hiragana conversion.
		// Note: katakana `vu` is never converted to hiragana
		wchar_t v = u;

		if (u <= 0x3000) return false;

		// Full-width katakana to hiragana
		if ((u >= 0x30A1) && (u <= 0x30F3)) {
			u -= 0x60;
		}
		// Half-width katakana to hiragana
		else if ((u >= 0xFF66) && (u <= 0xFF9D)) {
			u = ch[u - 0xFF66];
		}
		// Voiced (used in half-width katakana) to hiragana
		else if (u == 0xFF9E) {
			if ((previous >= 0xFF73) && (previous <= 0xFF8E)) {
				drop_last();
				u = cv[previous - 0xFF73];
			}
		}
		// Semi-voiced (used in half-width katakana) to hiragana
		else if (u == 0xFF9F) {
			if ((previous >= 0xFF8A) && (previous <= 0xFF8E)) {
				drop_last();
				u = cs[previous - 0xFF8A];
			}
		}
		// Ignore J~
		else if (u == 0xFF5E) {
			previous = 0;
			return true;
		}

		if (out_offset + 4 > out.size())
		{
			out.resize(out.size() * 2);
		}
		int written = wctomb(&out[0] + out_offset, u);
		if (written < 0)
		{
			out.clear();
			return false;
		}
		out_offset += size_t(written);
		true_length_mapping.resize(out_offset + 1, 0);
		true_length_mapping.at(out_offset) = i + 1; // Need to keep real length because of the half-width semi/voiced conversion
		previous = v;

		return true;
	}
};

std::vector<uint32_t> find(IndexFile* index, const std::string& word)
{
	PROFILE
//	printf("find(%s)\n", word.c_str());

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
	if (a.dentry.freq() != b.dentry.freq())
	{
		return a.dentry.freq() < b.dentry.freq();
	}
	if (a.match_symbols_length != b.match_symbols_length)
	{
		return a.match_symbols_length > b.match_symbols_length;
	}
	if (a.dentry.name() != b.dentry.name())
	{
		return a.dentry.name() < b.dentry.name();
	}
	if (a.expressions.empty() != b.expressions.empty())
	{
		return a.expressions.empty() > b.expressions.empty();
	}
	return a.reason.empty() > b.reason.empty();
}

static size_t line_buffer_size = 0;
static char* line = nullptr;

inline void sort_and_limit(SearchResult& res)
{
	// Sort by match length and then by commonnesss
	std::sort(res.data.begin(), res.data.end(), compare);
	if (res.data.size() > 5) {
		res.more = true;
	}
	res.data.erase(res.data.begin() + std::min(5L, long(res.data.size())), res.data.end());
}

SearchResult word_search(const char* word, bool names_dictionary)
{
	PROFILE
//	std::cout << "word_search( " << word << " )" << std::endl;
	KanaConvertor convertor;
	SearchResult result;
	if (!stream_utf8_convertor(word, convertor))
	{
		return result;
	}
	convertor.shrink();
	result.source = convertor.out;
//	printf("convertor.out = %s\n", convertor.out.c_str());

	FILE* dict = nullptr;
	IndexFile* index = nullptr;
	int maxTrim = 0;

	if (names_dictionary)
	{
		dict = fopen("names.dat", "r");
		index = &names_index;
		maxTrim = 7;
		result.names = true;
//		std::cout << "doNames" << std::endl;
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
	while (convertor.out.length() > 0)
	{
		std::list<Candidate> trys;

		if (names_dictionary)
		{
			trys.emplace_back(convertor.out, 0);
		}
		else
		{
			trys = deinflector->deinflect(convertor.out);
		}

		for (auto candidate_it = trys.begin(); candidate_it != trys.end(); ++candidate_it)
		{
			Candidate& u = *candidate_it;

			auto it = cache.find(u.word);
			if (it == cache.end()) {
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
//				printf("Line at index %u for word '%s' is '%.*s'\n", ofs, u.word.c_str(), line_length, line);
//				std::cout << "dentry: " << std::string(line, line_length - 1) << std::endl;

				DEntry dentry(ofs, std::string(line, line_length - 1), names_dictionary);
				if (names_dictionary)
				{
					dentry.filter_writings(convertor.out);
				}

				// > second and further - a de-inflected word.
				// Each type has associated bit. If bit-and gives 0
				// than deinflected word does not match this dentry.
				if (candidate_it != trys.begin() && (dentry.all_pos() & u.type) == 0) {
//					std::cout << "Mismatch: "
//						<< std::bitset<32>(dentry.all_pos()).to_string() << " and "
//						<< std::bitset<32>(u.type).to_string() << std::endl;
					continue;
				}
				// TODO confugirable number of entries
				if (count >= maxTrim) {
					result.more = true;
					if (names_dictionary) break;
				}

				have.insert(ofs);
				++count;

				size_t true_length = convertor.true_length_mapping.at(convertor.out.length());
				if (max_length == 0)
				{
					max_length = true_length;
				}

				std::vector<ExpressionResult> expressions;
				for (auto i = 0U; i < u.expressions.size(); ++i)
				{
					const CandidateExpression& expr = u.expressions[i];
					fseek(dict, expr.expression_rule->offset, SEEK_SET);
					ssize_t line_length = getline(&line, &line_buffer_size, dict);
					if (line_length == -1)
					{
						std::cerr << "Too bad" << std::endl;
						continue;
					}
					DEntry expression_dentry(expr.expression_rule->offset, std::string(line, line_length - 1),
						names_dictionary);
					expression_dentry.filter_writings(expr.expression_writing);
					expression_dentry.filter_senses(expr.expression_rule->sense_indices);
					expressions.emplace_back(ExpressionResult{expression_dentry, expr.reason});
				}
				result.data.emplace_back(dentry, u.reason,
					true_length, convertor.out.length(),
					std::move(expressions));
			}
		}
		if (count >= maxTrim) break;

		convertor.drop_last();
		convertor.shrink();
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
KanjiResult kanji_search(const char* kanji)
{

	KanjiResult result;

	wchar_t kanji_code;
	mbstate_t ps;
	memset(&ps, 0, sizeof(ps));
	size_t len = mbrtowc(&kanji_code, kanji, strlen(kanji), &ps);
	if (len == size_t(-1) || len == size_t(-2))
	{
		std::cerr << "Invalid utf8: " << kanji << std::endl;
		return result;
	}

	std::string kanji_str(kanji, len);
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

SearchResult search(const char* text)
{
	PROFILE
	Dictionary dictionary = config.default_dictionary;

	SearchResult res;
	do
	{
		switch (dictionary)
		{
			case WORDS:
				res = word_search(text, false);
				if (dictionary == config.default_dictionary)
				{
					SearchResult res2 = word_search(text, true);
					res.data.insert(res.data.end(), res2.data.begin(), res2.data.end());
					res.max_match_symbols_length = std::max(res.max_match_symbols_length, res2.max_match_symbols_length);
					sort_and_limit(res);
				}
				break;
			case NAMES:
				res = word_search(text, true);
				break;
			case KANJI:
				res = kanji_search(text);
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
	}
	else if (0 == strcmp(filename, "data/expressions.dat"))
	{
		expressions.assign(content, length);
	}

	if (deinflect && expressions)
	{
		deinflector = std::make_shared<Deinflector>(deinflect, expressions);
		deinflect.reset();
		expressions.reset();
	}

	return true;
}
