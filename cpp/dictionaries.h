#ifndef DICTIONARIES_H
#define DICTIONARIES_H
#include "dentry.h"

#include <map>


struct WordResult
{
	DEntry dentry;
	std::string reason;
	size_t match_symbols_length;
	size_t match_bytes_length;
	std::string expression;
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
	std::string title;
	size_t max_match_symbols_length;
	bool names;
	bool more;
	std::vector<WordResult> data;
	KanjiResult kanji;

	SearchResult();
	SearchResult(const KanjiResult& kanji);

};


enum SearchMode {
	FORCE_KANJI = 1,
	DEFAULT_DICT = 2,
	NEXT_DICT = 3,
};

SearchResult word_search(const char* word, bool names_dictionary, int max = -1);
SearchResult search(const char* text, SearchMode search_mode);

bool dictionaries_init(const char* filename, const char* content, uint32_t length);

#endif // DICTIONARIES_H
