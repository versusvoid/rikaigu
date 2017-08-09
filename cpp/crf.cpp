#include "api.h"
#include "deinflector.h"
#include "dentry.h"
#include "dictionaries.h"
#include "html_render.h"
#include "utils.h"

#include <crfxx/api.h>

#include <cstring>
#include <string>
#include <cwchar>
#include <locale>
#include <functional>
#include <memory>
#include <vector>
#include <map>
#include <set>
#include <algorithm>
#include <iostream>
#include <cstdlib>
#include <cassert>

static Tagger* tagger = nullptr;

bool crf_init(const char* filename, char* file_content, uint32_t length)
{
	printf("crf_init(%s)\n", filename);
	if (tagger == nullptr)
	{
		std::locale::global(std::locale("en_US.UTF-8"));
		printf("crf_init() making tagger\n");
		tagger = makeTagger();
	}

	if (0 == strcmp(filename, "data/weights.bin"))
	{
		printf("%u weights\n", length / sizeof(float));
		setWeights(tagger, file_content, length);
	}
	else
	{
		assert(strcmp(filename, "data/features.bin") == 0);
		setFeatureIndex(tagger, file_content, length);
	}

	return true;
}

struct AnnotateAndAddConvertor
{
	// changes with start
	size_t prefix_utf8_length;
	std::vector<size_t> code_point_to_utf8_pos;

	// absolute
	size_t start_utf8_pos;
	size_t current_utf8_length;
	size_t end_utf8_pos;

	void reset(size_t prefix_utf8_length)
	{
		this->prefix_utf8_length = prefix_utf8_length;
		this->start_utf8_pos = 0;
		this->current_utf8_length = 0;
		this->end_utf8_pos = 0;
		this->code_point_to_utf8_pos.clear();
	}

	void reserve(size_t) {}

	bool operator() (size_t, wchar_t character, const char*, size_t character_length)
	{
		if (character <= 0xffff)
		{
			add(tagger, (char16_t)character);
			printf("%d\n", int(character));
			code_point_to_utf8_pos.push_back(current_utf8_length);
			current_utf8_length += character_length;
		}
		// Kanji with code >= 0xffff are always separate words. So we can short-cut here
		else if (current_utf8_length == start_utf8_pos + prefix_utf8_length) // if our search starts with kanji >= 0xffff
		{
			// we want to search only it
			start_utf8_pos = current_utf8_length;
			end_utf8_pos = current_utf8_length + character_length;
			prefix_utf8_length = 0;
			code_point_to_utf8_pos.resize(1, 0);
			clear(tagger);
			printf("-------------------------\n");
			add(tagger, (char16_t)character);
			printf("%d\n", int(character));
			return false;
		}
		else if (current_utf8_length > start_utf8_pos + prefix_utf8_length) // if we meet it after some characters
		{
			// we want to search up until it
			end_utf8_pos = current_utf8_length;
			return false;
		}
		else // if we meet it before search start
		{
			// we want to search after it
			clear(tagger);
			printf("-------------------------\n");
			current_utf8_length += character_length;
			prefix_utf8_length -= current_utf8_length - start_utf8_pos;
			start_utf8_pos = current_utf8_length;
			code_point_to_utf8_pos.resize(1, 0);
		}
		return true;
	}
};
static AnnotateAndAddConvertor annotate_and_add_convertor;

std::string crf_extend(const char* utf8_prefix, const char* utf8_text, int32_t* prefix_symbols_length)
{
	printf("crf_exend() tagger = %p\n", tagger);
	if (tagger == NULL) return "";

	clear(tagger);
	std::string joined = utf8_prefix;
	annotate_and_add_convertor.reset(joined.length());
	joined.append(utf8_text);

	printf("before stream_utf8_convertor() %zu %zu\n", joined.size(), annotate_and_add_convertor.prefix_utf8_length);

	if (!stream_utf8_convertor(joined.c_str(), annotate_and_add_convertor)) {
		return "";
	}
	if (annotate_and_add_convertor.prefix_utf8_length == 0)
	{
		return "";
	}
	if (annotate_and_add_convertor.start_utf8_pos > 0 && annotate_and_add_convertor.end_utf8_pos > 0)
	{
		joined = joined.substr(annotate_and_add_convertor.start_utf8_pos,
			annotate_and_add_convertor.end_utf8_pos - annotate_and_add_convertor.start_utf8_pos);
	}
	else if (annotate_and_add_convertor.start_utf8_pos > 0)
	{
		joined = joined.substr(annotate_and_add_convertor.start_utf8_pos);
	}
	else if (annotate_and_add_convertor.end_utf8_pos > 0)
	{
		joined = joined.substr(0, annotate_and_add_convertor.end_utf8_pos);
	}

	printf("before parse() %zu %zu\n", joined.size(), annotate_and_add_convertor.prefix_utf8_length);
	printf("parsing %s\n", joined.c_str());
	auto& res = parse(tagger);
	for (auto& tag : res) { printf("%d ", int(tag)); }
	printf("\n");

	size_t symbol_start = annotate_and_add_convertor.code_point_to_utf8_pos.size();
	size_t start = annotate_and_add_convertor.prefix_utf8_length;

	auto i = 0U;
	for (; i < annotate_and_add_convertor.code_point_to_utf8_pos.size() && annotate_and_add_convertor.code_point_to_utf8_pos[i] <= annotate_and_add_convertor.prefix_utf8_length; ++i)
	{
		if (res[i] == 1)
		{
			symbol_start = i;
			start = annotate_and_add_convertor.code_point_to_utf8_pos[i];
		}
	}
	if (start == annotate_and_add_convertor.prefix_utf8_length)
	{
		return "";
	}
	*prefix_symbols_length = i - symbol_start - 1;

	size_t end = joined.length();
	for (i += 1; i < annotate_and_add_convertor.code_point_to_utf8_pos.size(); ++i)
	{
		if (res[i] == 1)
		{
			end = annotate_and_add_convertor.code_point_to_utf8_pos[i];
			break;
		}
	}

	return joined.substr(start, end - start);
}

