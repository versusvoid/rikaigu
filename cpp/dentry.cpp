#include "dentry.h"
#include "word_types.h"
#include "utils.h"

#include <iostream>
#include <map>
#include <algorithm>

DEntry::DEntry(const std::string& dictionary_line, bool name)
	: name(name)
	, _freq(1e9)
	, _all_pos(0)
{
	PROFILE
	auto parts = split(dictionary_line, '\t');
	kanji_string = parts.at(0);
	if (parts.size() == 4 || (
			parts.size() == 3
				&&
			std::all_of(parts.back().begin(), parts.back().end(), isdigit)
			))
	{
		_freq = std::stoi(parts.at(parts.size() - 1));
		definition_string = parts.at(parts.size() - 2);
		if (parts.size() == 4)
		{
			reading_string = parts.at(1);
		}
	}
	else
	{
		definition_string = parts.at(parts.size() - 1);
		if (parts.size() == 3)
		{
			reading_string = parts.at(1);
		}
	}
}

int DEntry::freq() {
	return _freq;
}

uint32_t DEntry::all_pos()
{
	if (!definition_string.empty())
	{
		parse_sense_groups();
	}
	return _all_pos;
}

const std::vector<SenseGroup>& DEntry::sense_groups()
{
	if (!definition_string.empty())
	{
		parse_sense_groups();
	}
	return _sense_groups;
}

const std::vector<KanjiGroup>& DEntry::kanji_groups()
{
	if (!kanji_string.empty())
	{
		parse_kanji_groups();
	}
	return _kanji_groups;
}

const std::vector<Writing>& DEntry::readings()
{
	if (!reading_string.empty())
	{
		parse_readings();
	}
	return _readings;
}

static std::map<std::string, std::string> names_abbreviations = {
	    {"c", "company name"},
	    {"f", "female given name or forename"},
	    {"g", "given name or forename, gender not specified"},
	    {"m", "given name or forename, gender not specified"},
	    {"o", "organization name"},
	    {"p", "full name of a particular person"},
	    {"pl", "place name"},
	    {"pr", "product name"},
	    {"s", "railway station"},
	    {"su", "family or surname"},
	    {"u", "unclassified name"},
	    {"w", "work of art, literature, music, etc. name"},
};
void DEntry::parse_sense_groups()
{
	PROFILE

	for (auto& sense_group : split(definition_string, '\\'))
	{
		size_t p = sense_group.find(';');
		_sense_groups.push_back({
			split(sense_group.substr(0, p), ','),
			split(sense_group.substr(p + 1), '`')
		});
		if (name)
		{
			for(auto& type : _sense_groups.back().types)
			{
				type = names_abbreviations.at(type);
			}
		}
		else
		{
			_all_pos |= inflection_type_to_int(_sense_groups.back().types);
		}
	}
	definition_string.clear();
}

void DEntry::parse_readings()
{
	PROFILE

	for (auto& reading : split(reading_string, ';'))
	{
		size_t p = reading.find('|');
		_readings.push_back({
			p == std::string::npos,
			reading.substr(0, p),
		});
		all_readings_indices.push_back(all_readings_indices.size());
	}
	reading_string.clear();
}

void DEntry::parse_kanji_groups()
{
	PROFILE

	for (auto& kanji_group_str : split(kanji_string, ';'))
	{
		size_t p = kanji_group_str.find('#');

		KanjiGroup kanji_group;
		if (p != std::string::npos)
		{
			for (auto& reading : split(kanji_group_str.substr(p + 1), ','))
			{
				kanji_group.readings.push_back(std::stoul(reading));
			}
			kanji_group_str = kanji_group_str.substr(0, p);
		}
		else
		{
			kanji_group.readings = all_readings_indices;
		}

		for (auto& kanji : split(kanji_group_str, ','))
		{
			p = kanji.find('|');
			kanji_group.kanjis.push_back({
				p == std::string::npos,
				kanji.substr(0, p)
			});
		}
		_kanji_groups.push_back(kanji_group);
	}
	kanji_string.clear();
}
