#include "dentry.h"
#include "word_types.h"
#include "utils.h"
#include "config.h"

#include <iostream>
#include <map>
#include <algorithm>
#include <cassert>

DEntry::DEntry(uint32_t offset, const std::string& dictionary_line, bool name)
	: offset_aka_id(offset)
	, _name(name)
	, _freq(UNKNOWN_WORD_FREQ_ORDER)
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

uint32_t DEntry::id()
{
	return offset_aka_id;
}

bool DEntry::name()
{
	return _name;
}

int DEntry::freq() const
{
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

void DEntry::filter_writings(const std::string &the_only_writing)
{
	parse_readings();
	parse_kanji_groups();

	for (auto i = 0U; i < _kanji_groups.size(); ++i)
	{
		for (auto j = 0U; j < _kanji_groups[i].kanjis.size(); ++j)
		{
			if (_kanji_groups[i].kanjis[j].text == the_only_writing)
			{
				if (_kanji_groups[i].readings.size() != _readings.size())
				{
					std::vector<Writing> new_readings;
					std::vector<size_t> new_readings_indices;
					for (auto& reading_index : _kanji_groups[i].readings)
					{
						new_readings.emplace_back(_readings[reading_index]);
						new_readings_indices.push_back(new_readings_indices.size());
					}
					_readings = new_readings;
					_kanji_groups[i].readings = new_readings_indices;
				}

				_kanji_groups[i].kanjis.erase(_kanji_groups[i].kanjis.begin(), _kanji_groups[i].kanjis.begin() + j);
				_kanji_groups[i].kanjis.erase(_kanji_groups[i].kanjis.begin() + 1, _kanji_groups[i].kanjis.end());

				_kanji_groups.erase(_kanji_groups.begin(), _kanji_groups.begin() + i);
				_kanji_groups.erase(_kanji_groups.begin() + 1, _kanji_groups.end());

				return;
			}
		}
	}

	for (size_t i = 0U; i < _readings.size(); ++i)
	{
		if (_readings[i].text == the_only_writing)
		{
			std::vector<KanjiGroup> new_kanji_groups;
			for(auto& group : _kanji_groups)
			{
				if (std::find(group.readings.begin(), group.readings.end(), i) != group.readings.end())
				{
					new_kanji_groups.emplace_back(group);
				}
			}
			_kanji_groups = new_kanji_groups;

			return;
		}
	}
}

void DEntry::filter_senses(const std::vector<std::pair<int, int> > &sense_indices)
{
	parse_sense_groups();
	std::vector<SenseGroup> new_sense_groups;
	for(auto it = sense_indices.begin(); it != sense_indices.end();)
	{
		const int sense_group_index = it->first;
		const SenseGroup& sense_group = _sense_groups[sense_group_index];
		std::vector<std::string> new_senses;
		for(;it != sense_indices.end() && sense_group_index == it->first; ++it)
		{
			new_senses.emplace_back(sense_group.senses[it->second]);
		}
		new_sense_groups.push_back({sense_group.types, new_senses});
	}
	_sense_groups = new_sense_groups;
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
		// Make sure readings are parsed before parsing kanji
		readings(); // FIXME WTF T___T

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
		if (_name)
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
