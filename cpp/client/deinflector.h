#ifndef DEINFLECTOR_H
#define DEINFLECTOR_H
#include "utils.h"

#include <list>
#include <map>
#include <set>
#include <vector>
#include <string>

struct Rule
{
	uint32_t source_type;

	std::string to;
	uint32_t target_type;
	std::string reason;

	uint32_t after_type;
	std::set<std::string> after_form;
	uint32_t offset;
	std::vector<std::pair<int, int>> sense_indices;
};

struct SuffixLengthRulesGroup
{
	size_t suffix_length;
	std::multimap<std::string, Rule> rules;

	SuffixLengthRulesGroup(size_t suffix_length)
		: suffix_length(suffix_length)
	{}
};

struct Candidate
{
	std::string word;
	uint32_t type;
	std::string reason;
	std::set<std::string> expected_forms;

	Candidate(const std::string& word, uint32_t type)
		: word(word)
		, type(type)
	{}

	Candidate(const std::string& word, uint32_t type,
			const std::set<std::string>& expected_forms)
		: word(word)
		, type(type)
		, expected_forms(expected_forms)
	{}
};

class Deinflector
{
	std::vector<SuffixLengthRulesGroup> rules_groups;
public:

	Deinflector(const string_view& deinflect);

	std::list<Candidate> deinflect(const std::string& word);
};

#endif // DEINFLECTOR_H
