#include "deinflector.h"
#include "word_types.h"

#include <list>
#include <iostream>
#include <algorithm>
#include <numeric>
#include <cassert>


Deinflector::Deinflector(const string_view& deinflect, const string_view& expressions)
{
	const char* p = deinflect.data;
	const char* end = deinflect.data + deinflect.length;
	while (p < end)
	{
		if (*p == '#' || *p == ' ' || *p == '\t' || *p == '\n')
		{
			p = std::find(p, end, '\n') + 1;
			continue;
		}
		const char* const line_end = std::find(p, end, '\n');

		std::string from;
		Rule rule;
		int column = 0;
		while (p < line_end)
		{
			const char* const column_end = std::find(p, line_end, '\t');
			column += 1;
			switch (column)
			{
				case 1:
					from = std::string(p, column_end);
					break;
				case 2:
					rule.to = std::string(p, column_end);
					break;
				case 3:
					rule.source_type = inflection_type_to_int(p, column_end);
					break;
				case 4:
					rule.target_type = inflection_type_to_int(p, column_end);
					break;
				case 5:
					rule.reason = std::string(p, column_end);
					break;
				default:
					std::cerr << "Invalid deinflect rule: " << std::string(p, line_end) << std::endl;
					break;
			}
			p = column_end + 1;
		}
		while (from.length() >= rules_groups.size())
		{
			rules_groups.push_back(SuffixLengthRulesGroup(rules_groups.size()));
		}
		rules_groups.at(from.length()).rules.insert(std::make_pair(from, rule));

		p = line_end + 1;
	}

	uint32_t all_verbs_type = 0;
	for (auto& kv : INFLECTION_TYPES)
	{
		if (kv.first[0] == 'v')
		{
			all_verbs_type |= kv.second;
		}
	}
	INFLECTION_TYPES["v"] = all_verbs_type;

	std::vector<std::string> from;
	Rule rule(true);
	p = expressions.data;
	end = expressions.data + expressions.length;
	while (p < end)
	{
		if (*p == '#' || *p == ' ' || *p == '\t' || *p == '\n')
		{
			p = std::find(p, end, '\n') + 1;
			continue;
		}
		const char* const line_end = std::find(p, end, '\n');

		int column = 0;
		while (p < line_end)
		{
			const char* const column_end = std::find(p, line_end, '\t');
			column += 1;
			switch (column)
			{
				case 1:
					assert(p < column_end);
					from.push_back(std::string(p, column_end));
					break;
				case 2:
					rule.source_type = inflection_type_to_int(p, column_end);
					break;
				case 3:
					rule.after_type = *p == '*'? ANY_TYPE : inflection_type_to_int(p, column_end);
					break;
				case 4:
					while (p < column_end)
					{
						const char* const part_end = std::find(p, column_end, '|');
						assert(p < part_end);
						rule.after_form.insert(std::string(p, part_end));
						p = part_end + 1;
					}
					break;
				case 5:
					assert(p < column_end);
					if (std::all_of(p, column_end, isdigit))
					{
						rule.offset = uint32_t(std::stoul(std::string(p, column_end)));
					}
					break;
				case 6:
					while (p < column_end)
					{
						const char* const part_end = std::find(p, column_end, '|');
						const char* coma = std::find(p, part_end, ',');

						assert(p < coma);
						assert(coma + 1 < part_end);
						rule.sense_indices.push_back(std::make_pair(
							std::stoi(std::string(p, coma)),
							std::stoi(std::string(coma + 1, part_end))
						));
						p = part_end + 1;
					}
					break;
				case 7:
					rule.reason = std::string(p, column_end);
					break;
				default:
					std::cerr << "Invalid expression: " << std::string(p, line_end) << std::endl;
					break;
			}
			p = column_end + 1;
		}
		if (column == 1)
		{
			p = line_end + 1;
			continue;
		}

		for (auto& from_string : from)
		{
			while (from_string.length() >= rules_groups.size())
			{
				rules_groups.push_back(SuffixLengthRulesGroup(rules_groups.size()));
			}
			rules_groups.at(from_string.length()).rules.insert(std::make_pair(from_string, rule));
		}
		rule = Rule(true);
		from.clear();

		p = line_end + 1;
	}

	rules_groups.erase(std::remove_if(rules_groups.begin(), rules_groups.end(), [](SuffixLengthRulesGroup& r) {
		return r.rules.empty();
	}), rules_groups.end());
}

std::list<Candidate> Deinflector::deinflect(const std::string& word)
{
	PROFILE
//	std::cout << "deinflect( " << word << " )" << std::endl;

	std::list<Candidate> r;
	r.emplace_back(word,
	// Original word can have any type
		ANY_TYPE);

	for (auto candidate_it = r.begin(); candidate_it != r.end(); ++candidate_it)
	{
		const Candidate& candidate = *candidate_it;

		for (size_t j = 0; j < rules_groups.size(); ++j)
		{
			const SuffixLengthRulesGroup& g = rules_groups.at(j);
			if (g.suffix_length > candidate.word.length()) break;

			const std::string end = candidate.word.substr(candidate.word.length() - g.suffix_length);
			auto range = g.rules.equal_range(end);
			if (range.first == g.rules.end()) continue;

			for (auto it = range.first; it != range.second; ++it)
			{
				const Rule& rule = it->second;
				// If rule isn't applicable to this word
				if ((candidate.type & rule.source_type) == 0)
				{
					continue;
				}
				if (!candidate.expected_forms.empty()
						&& candidate.expected_forms.count(rule.reason) == 0
						&& candidate.expected_forms.count("*") == 0)
				{
					continue;
				}

				std::string new_word = candidate.word.substr(0, candidate.word.length() - g.suffix_length);
				if (!rule.expression)
				{
					// Inflection
					new_word += rule.to;
					if (new_word.length() <= 1) continue;

//					printf("%s -> %s due %s\n", candidate.word.c_str(), new_word.c_str(), rule.reason.c_str());

					r.emplace_back(new_word, rule.target_type);
					if (candidate.reason.length() > 0)
					{
						r.back().reason = rule.reason + " &lt; " + candidate.reason;
					}
					else
					{
						r.back().reason = rule.reason;
					}
					r.back().expressions = candidate.expressions;
					r.back().expressions_forms = candidate.expressions_forms;

				}
				else if (g.suffix_length < candidate.word.length() && config.deinflect_expressions)
				{
					// Expression
					if (!candidate.expressions.empty() &&
							(candidate.expressions.back()->after_type & rule.source_type) == 0)
					{
						continue;
					}

//					printf("Expression %s\n", end.c_str());

					size_t numSpecials = 0;
					if (rule.after_form.count("negative stem") > 0)
					{
						numSpecials += 1;
						auto new_special = new_word + u8"ない";
						if (new_word == u8"せ")
						{
							new_special = u8"しない";
						}

						r.emplace_back(new_special, INFLECTION_TYPES["adj-i"],
							candidate.expressions_forms, end,
							candidate.expressions, &rule,
							std::set<std::string>{"negative", "masu stem"}
						);
					}

					if (rule.after_form.count("provisional stem") > 0)
					{
						numSpecials += 1;
						r.emplace_back(new_word + u8"ば", INFLECTION_TYPES["raw"],
							candidate.expressions_forms, end,
							candidate.expressions, &rule,
							std::set<std::string>{"-ba"}
						);
					}

					if (rule.after_form.count("adjective stem") > 0)
					{
						numSpecials += 1;
						r.emplace_back(new_word + u8"い", INFLECTION_TYPES["adj-i"],
							candidate.expressions_forms, end,
							candidate.expressions, &rule,
							std::set<std::string>{"negative"}
						);
					}

					if (rule.after_form.count("past stem") > 0)
					{
						numSpecials += 1;
						for (auto& copula : {u8"た", u8"だ"})
						{
							r.emplace_back(new_word + copula, INFLECTION_TYPES["raw"],
								candidate.expressions_forms, end,
								candidate.expressions, &rule,
								std::set<std::string>{"past"}
							);
						}
					}

					if (numSpecials < rule.after_form.size())
					{
						r.emplace_back(new_word, rule.after_type,
							candidate.expressions_forms, end,
							candidate.expressions, &rule,
							rule.after_form
						);
					}
				}
			}
		}
	}

	for (auto it = r.begin(); it != r.end();)
	{
		if (!it->expressions.empty())
		{
			auto after_type = it->expressions.back()->after_type;
			if ((it->type & after_type) == 0)
			{
				it = r.erase(it);
				continue;
			}
			it->type &= after_type;
		}
		++it;
	}
	return r;
}
