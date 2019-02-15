#ifndef DENTRY_H
#define DENTRY_H
#include <stdint.h>

#include <vector>
#include <string>

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
	// TODO persistent id's
	uint32_t offset_aka_id;
	std::string kanji_string;
	std::string reading_string;
	std::string definition_string;

	std::vector<size_t> all_readings_indices;

	std::vector<SenseGroup> _sense_groups;
	std::vector<KanjiGroup> _kanji_groups;
	std::vector<Writing> _readings;

	bool _name;
	int _freq;
	uint32_t _all_pos;

	void parse_sense_groups();
	void parse_kanji_groups();
	void parse_readings();
public:
	DEntry(uint32_t offset, const std::string& dictionaryLine, bool name);

	uint32_t id();
	bool name();
	int freq() const;
	uint32_t all_pos();

	// TODO mb filter in render?
	void filter_writings(const std::string& the_only_writing);
	void filter_senses(const std::vector<std::pair<int, int>>& sense_indices);

	const std::vector<SenseGroup>& sense_groups();
	const std::vector<KanjiGroup>& kanji_groups();
	const std::vector<Writing>& readings();
};

#endif // DENTRY_H
