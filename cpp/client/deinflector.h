#ifndef DEINFLECTOR_H
#define DEINFLECTOR_H
#include "utils.h"

#include <list>
#include <map>
#include <set>
#include <vector>
#include <string>

struct DeinflectRule
{
};

struct Rule
{
	bool expression;

	uint32_t source_type;

	std::string to;
	uint32_t target_type;
	std::string reason;

	uint32_t after_type;
	std::set<std::string> after_form;
	uint32_t offset;
	std::vector<std::pair<int, int>> sense_indices;

	Rule(bool expression = false)
		: expression(expression)
	{}
};

struct SuffixLengthRulesGroup
{
	size_t suffix_length;
	std::multimap<std::string, Rule> rules;

	SuffixLengthRulesGroup(size_t suffix_length)
		: suffix_length(suffix_length)
	{}
};

struct CandidateExpression
{
	const Rule* expression_rule;
	std::string expression_writing;
	std::string reason;
};

struct Candidate
{
	std::string word;
	uint32_t type;
	std::string reason;
	std::vector<CandidateExpression> expressions;
	std::set<std::string> expected_forms;

	Candidate(const std::string& word, uint32_t type)
		: word(word)
		, type(type)
	{}

	Candidate(const std::string& word, uint32_t type,
			const Rule* new_expression,
			const std::string& new_expression_writing,
			const std::string& new_expression_reason,
			const std::vector<CandidateExpression>& expressions,
			const std::set<std::string>& expected_forms)
		: word(word)
		, type(type)
		, expressions(expressions)
		, expected_forms(expected_forms)
	{
		this->expressions.push_back({new_expression, new_expression_writing, new_expression_reason});
	}
};

class Deinflector
{
	std::vector<SuffixLengthRulesGroup> rules_groups;
public:

	Deinflector(const string_view& deinflect, const string_view& expressions);

	std::list<Candidate> deinflect(const std::string& word);
};

#endif // DEINFLECTOR_H
