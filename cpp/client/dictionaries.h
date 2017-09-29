#ifndef DICTIONARIES_H
#define DICTIONARIES_H
#include "dentry.h"

#include <map>

struct ExpressionResult
{
	DEntry dentry;
	std::string reason;
};

struct WordResult
{
	DEntry dentry;
	std::string reason;
	size_t match_symbols_length;
	size_t match_bytes_length;
	std::vector<ExpressionResult> expressions;

	WordResult(const DEntry& dentry,
			const std::string& reason = "",
			size_t match_symbols_length = 0,
			size_t match_bytes_length = 0,
			const std::vector<ExpressionResult>&& expressions = {})
		: dentry(dentry)
		, reason(reason)
		, match_symbols_length(match_symbols_length)
		, match_bytes_length(match_bytes_length)
		, expressions(std::move(expressions))
	{}
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

bool dictionaries_init(const char* filename, const char* content, uint32_t length);

#endif // DICTIONARIES_H
