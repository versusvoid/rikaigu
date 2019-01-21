#include "api.h"
#include "deinflector.h"
#include "dentry.h"
#include "dictionaries.h"
#include "html_render.h"
#include "utils.h"

#include <crfpp.h>
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

static std::shared_ptr<CRFPP::Tagger> tagger;
static std::shared_ptr<CRFPP::Model> model;
static std::shared_ptr<const char> model_file_content;

bool crf_init(const char* model_file_content, uint32_t length)
{
	std::locale::global(std::locale("en_US.UTF-8"));
	::model_file_content.reset(model_file_content, reinterpret_cast<void(*)(const char*)>(free));
	model.reset(CRFPP::createModelFromArray("", model_file_content, length));
	if (!model)
	{
		std::cerr << "can't create model from file" << std::endl;
		return false;
	}
	tagger.reset(model->createTagger());
	if (!tagger)
	{
		model.reset();
		std::cerr << "can't create tagger from model" << std::endl;
		return false;
	}
	return true;
}

struct AnnotateAndAddConvertor
{
	void reserve(size_t) {}

	bool operator() (size_t, wchar_t character, const char* in, size_t character_length)
	{
		char annotated[4 + 2 + 1];
		std::copy(in, in + character_length, annotated);
		annotated[character_length] = '\t';

		if (character >= 0x4e00 && character <= 0x9fa5) {
			annotated[character_length + 1] = 'K';
		} else if (character >= 0x3040 && character <= 0x309f) {
			annotated[character_length + 1] = 'h';
		} else if (character >= 0x30a1 && character <= 0x30fe) {
			annotated[character_length + 1] = 'k';
		} else {
			annotated[character_length + 1] = 'm';
		}
		annotated[character_length + 2] = '\0';
		tagger->add(annotated);

		return true;
	}
};
static AnnotateAndAddConvertor annotate_and_add_convertor;

int32_t crf_split(const char* utf8_string) {
	if (tagger == NULL) return -1;

	tagger->clear();
	if (!stream_utf8_convertor(utf8_string, annotate_and_add_convertor)) {
		return -2;
	}
	if (!tagger->parse())
	{
		std::cerr << "Can't parse" << std::endl;
	}

	for (size_t i = 0; i < tagger->size(); ++i) {
		if (tagger->y2(i)[0] == 'S') {
			return int32_t(i);
		}
	}
	return 0;
}

std::string append_prefix(const char* utf8_text, const char* utf8_prefix)
{
	std::string res;
	size_t p = 0;
	if ((utf8_text[p] & 0b11000000) == 0b11000000)
	{
		while ((utf8_text[p + 1] & 0b11000000) == 0b10000000)
		{
			p += 1;
		}
	}
	res.append(utf8_text, p + 1);

	size_t end = strlen(utf8_prefix);
	p = end - 1;
	while (end != 0)
	{
		while (p > 0 && (utf8_prefix[p] & 0b11000000) == 0b10000000)
		{
			p -= 1;
		}
		res.append(utf8_prefix + p, end - p);
		end = p;
		p = end - 1;
	}

	return res;
}

std::string prepend_prefix(const char* utf8_text, const char* utf8_prefix, int prefix_length)
{
	size_t p = strlen(utf8_prefix);
	while (prefix_length > 0)
	{
		p -= 1;
		while ((utf8_prefix[p] & 0b11000000) == 0b10000000)
		{
			p -= 1;
		}
		prefix_length -= 1;
	}

	return std::string(utf8_prefix + p) + utf8_text;
}

std::string crf_extend(const char* utf8_text, const char* utf8_prefix, int32_t* prefix_length)
{
	std::string crf_input = append_prefix(utf8_text, utf8_prefix);
	*prefix_length = crf_split(crf_input.c_str());
	if (*prefix_length > 0) {
		return prepend_prefix(utf8_text, utf8_prefix, *prefix_length);
	} else {
		*prefix_length = 0;
		return std::string();
	}
}

