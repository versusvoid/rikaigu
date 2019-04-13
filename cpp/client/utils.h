#ifndef UTILS_H
#define UTILS_H
#include <emscripten.h>
#include <cstring>
#include <cwchar>
#include <iostream>
#include <chrono>
#include <set>
#include <map>
#include <vector>

struct string_view
{
	const char* data;
	uint32_t length;

	string_view();

	operator bool() const;

	void reset();
	void assign(const char* data, uint32_t length);
};

struct profiler
{
	std::chrono::steady_clock::time_point start;
	const char* function;
	int line;

	profiler(const char* function, int line);
	~profiler();
};

enum Dictionary : int
{
	WORDS = 0,
	NAMES = 1,
	KANJI = 2
};

struct Config
{
	bool only_reading;
	bool kanji_components;
	Dictionary default_dictionary;
	std::set<std::string> kanji_info;
	std::map<uint32_t, std::string> review_list;
};
extern Config config;

std::vector<std::string> split(const std::string_view& str, char sep, bool add_empty = true);

extern "C" {
void EMSCRIPTEN_KEEPALIVE rikaigu_dump_profile_info();
}

//#define PROFILE profiler __profiler__(__FUNCTION__, __LINE__);
#define PROFILE
#endif // UTILS_H
