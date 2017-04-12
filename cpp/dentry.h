#ifndef DENTRY_H
#define DENTRY_H
#include <stdint.h>

#include <vector>
#include <string>

std::vector<std::string> split(const std::string& str, char sep);

struct SenseGroup
{
	std::vector<std::string> types;
	std::vector<std::string> senses;

};

struct Writing
{
	bool common;
	std::string text;
};

struct KanjiGroup
{
	std::vector<size_t> readings;
	std::vector<Writing> kanjis;
};

class DEntry
{
	bool name;
	std::string kanji_string;
	std::string reading_string;
	std::string definition_string;

	std::vector<size_t> all_readings_indices;

	std::vector<SenseGroup> _sense_groups;
	std::vector<KanjiGroup> _kanji_groups;
	std::vector<Writing> _readings;

	int _freq;
	uint32_t _all_pos;

	void parse_sense_groups();
	void parse_kanji_groups();
	void parse_readings();
public:

	DEntry(const std::string& dictionaryLine, bool name);

	int freq();
	uint32_t all_pos();

	void filter_writings(const std::string& the_only_writing);
	void filter_senses(const std::vector<std::pair<int, int>>& sense_indices);

	const std::vector<SenseGroup>& sense_groups();
	const std::vector<KanjiGroup>& kanji_groups();
	const std::vector<Writing>& readings();
};

#endif // DENTRY_H
