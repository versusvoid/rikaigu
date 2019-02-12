#include "deinflector.h"
#include "word_types.h"

#include <list>
#include <iostream>
#include <algorithm>
#include <numeric>
#include <cassert>


Deinflector::Deinflector(const string_view& deinflect)
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
				// Inflection
				new_word += rule.to;
				if (new_word.length() <= 1) continue;

				// printf("%s -> %s due %s\n", candidate.word.c_str(), new_word.c_str(), rule.reason.c_str());

				r.emplace_back(new_word, rule.target_type);
				if (candidate.reason.length() > 0)
				{
					r.back().reason = rule.reason + " &lt; " + candidate.reason;
				}
				else
				{
					r.back().reason = rule.reason;
				}
			}
		}
	}

	return r;
}
