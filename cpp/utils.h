#ifndef UTILS_H
#define UTILS_H
#include <emscripten.h>
#include <cstring>
#include <cwchar>
#include <iostream>
#include <chrono>
#include <set>
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
};
extern Config config;

std::vector<std::string> split(const std::string& str, char sep);

extern "C" {
void EMSCRIPTEN_KEEPALIVE rikaigu_dump_profile_info();
}

//#define PROFILE profiler __profiler__(__FUNCTION__, __LINE__);
#define PROFILE

template <typename Convertor>
bool stream_utf8_convertor(const char* in, Convertor& convertor)
{
	PROFILE
	size_t byte_length = strlen(in);
	convertor.reserve(byte_length);
	const char* end = in + byte_length;

	mbstate_t ps;
	memset(&ps, 0, sizeof(ps));
	size_t i = 0;
	while (in < end) {
		wchar_t character;
		const size_t count = mbrtowc(&character, in, byte_length, &ps);
		if (count == size_t(-1) || count == size_t(-2) || count > 4) {
			std::cerr << "Error processing utf8" << std::endl;
			return false;
		}
		if (!convertor(i, character, in, count)) return true;
		i += 1;
		in += count;
		byte_length -= count;
	}
	if (byte_length != 0) {
		std::cerr << "Invalid utf8 input" << std::endl;
		return false;
	}

	return true;
}

#endif // UTILS_H
