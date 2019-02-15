#ifndef DICTIONARIES_H
#define DICTIONARIES_H
#include "dentry.h"

#include <map>
#include <cmath>

struct WordResult
{
	DEntry dentry;
	std::string reason;
	size_t match_symbols_length;
	size_t match_bytes_length;

	WordResult(const DEntry& dentry,
			const std::string& reason = "",
			size_t match_symbols_length = 0,
			size_t match_bytes_length = 0)
		: dentry(dentry)
		, reason(reason)
		, match_symbols_length(match_symbols_length)
		, match_bytes_length(match_bytes_length)
	{}

	inline double score() const
	{
		const auto scale = 0.3;
		const auto bias = 1.0;
		return scale*std::log(dentry.freq() + 1) - match_symbols_length + bias;
	}
};


struct KanjiResult
{
	std::string kanji;
	std::map<std::string, std::string> misc;
	std::vector<std::string> onkun;
	std::string nanori;
	std::string bushumei;
	std::string eigo;
};



struct SearchResult
{
	std::string source;
	size_t max_match_symbols_length;
	bool names;
	bool more;
	std::vector<WordResult> data;
	KanjiResult kanji;

	SearchResult();
	SearchResult(const KanjiResult& kanji);

};

SearchResult search(const char* text);

SearchResult word_search(const char* word, bool names_dictionary);

bool dictionaries_init(const char* filename, const char* content, uint32_t length);

#endif // DICTIONARIES_H
