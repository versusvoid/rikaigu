#include "utils.h"
#include "api.h"

#include <cassert>
#include <unordered_map>
#include <map>
#include <vector>
#include <tuple>
#include <algorithm>


std::vector<std::string> split(const std::string_view& str, char sep, bool add_empty)
{
	PROFILE
	std::vector<std::string> res;
	if (str.length() == 0)
	{
		if (add_empty) res.emplace_back(str);
		return res;
	}

	std::size_t start = 0, end = str.find(sep);
	while (end != std::string::npos)
	{
		if (add_empty || end > start) res.emplace_back(str.substr(start, end - start));
		start = end + 1;
		end = str.find(sep, start);
	}
	if (start < str.length())
	{
		res.emplace_back(str.substr(start));
	}
	return res;
}


Config config = {
	false, true,
	WORDS,
	// see `kanji_numbers` in html_render.cpp
	{"H", "L", "E", "DK", "N", "V", "Y", "P", "IN", "I", "U"}
};

void rikaigu_set_config(
		bool only_reading,
		bool kanji_components,
		int default_dictionary,
		const char* kanji_info,
		const char* review_list)
{
	config.only_reading = only_reading;
	config.kanji_components = kanji_components;
	config.default_dictionary = Dictionary(default_dictionary);

	config.kanji_info.clear();
	for (auto& kanji_info_key : split(kanji_info, ' ', false))
	{
		config.kanji_info.emplace(kanji_info_key);
	}

	config.review_list.clear();
	std::cout << "review list: " << review_list << std::endl;
	for (auto& kv : split(review_list, '|', false))
	{
		auto sep = kv.find(',');
		assert(sep != std::string::npos);
		uint32_t id;
		// auto res = std::from_chars(kv.c_str(), kv.c_str() + sep, id);
		// assert(res.ec == std::errc());
		id = std::stoi(kv.substr(0, sep));
		std::cout << "Review entry: " << id << " - " << kv.substr(sep + 1) << std::endl;
		config.review_list.emplace(id, kv.substr(sep + 1));
	}
}


string_view::string_view()
	: data(nullptr)
	, length(0)
{}

string_view::operator bool() const
{
	return length != 0;
}

void string_view::reset()
{
	if (data != nullptr)
	{
		free((void*)data);
	}
	data = nullptr;
	length = 0;
}

void string_view::assign(const char *data, uint32_t length)
{
	reset();
	this->data = data;
	this->length = length;
}

static std::map<std::pair<const char*, int>, std::pair<size_t, size_t>> profile_info;
profiler::profiler(const char *function, int line)
	: start(std::chrono::steady_clock::now())
	, function(function)
	, line(line)
{
}

profiler::~profiler()
{
	auto duration = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - start).count();
	auto key = std::make_pair(function, line);
	auto it = profile_info.find(key);
	if (it == profile_info.end())
	{
		profile_info[key] = std::make_pair(duration, 1);
	}
	else
	{
		it->second.first += duration;
		it->second.second += 1;
	}
}

void rikaigu_dump_profile_info()
{
	std::vector<std::tuple<const char*, int, size_t, size_t>> ordered;
	for (auto& kv : profile_info)
	{
		ordered.push_back(std::make_tuple(kv.first.first, kv.first.second, kv.second.first, kv.second.second));
	}
	std::sort(ordered.begin(), ordered.end(), [] (auto& r1, auto& r2) { return std::get<2>(r1) > std::get<2>(r2);});

	for (auto& r : ordered)
	{
		std::cout << std::get<0>(r) << ":" << std::get<1>(r) << " - "
				<< float(std::get<2>(r)) / float(std::get<3>(r))
				<< ", total: " << std::get<2>(r) << " " << std::get<3>(r)
				<< std::endl;
	}
}
