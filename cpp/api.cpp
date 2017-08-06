#include "api.h"
#include "crf.h"
#include "dictionaries.h"
#include "html_render.h"
#include "utils.h"

#include <locale>
#include <iostream>
#include <cstring>
#include <cassert>

bool rikaigu_set_file(const char* filename, char* data, uint32_t length)
{
	if (0 == strcmp(filename, "data/model.bin"))
	{
		return crf_init(filename, data, length);
	}
	else if (0 == strcmp(filename, "data/radicals.dat"))
	{
		return render_init(data, length);
	}
	else
	{
		return dictionaries_init(filename, data, length);
	}

}

const char* rikaigu_search(const char* utf8_text, const char* utf8_prefix,
		int32_t* match_symbols_length, int32_t* prefix_symbols_length)
{
	PROFILE
	SearchResult res = search(utf8_text);
	*prefix_symbols_length = 0;
	if (config.smart_segmentation && utf8_prefix[0] != '\0' && config.default_dictionary == WORDS)
	{
		std::string extended_text = crf_extend(utf8_prefix, utf8_text, prefix_symbols_length);
		if (extended_text.size() > 0)
		{
			SearchResult res2 = search(extended_text.c_str());
			if (res2.max_match_symbols_length >= res.max_match_symbols_length + *prefix_symbols_length)
			{
				res = res2;
			}
			else
			{
				*prefix_symbols_length = 0;
			}
		}
		else
		{
			assert(*prefix_symbols_length == 0);
		}
	}
	*match_symbols_length = int32_t(res.max_match_symbols_length) - *prefix_symbols_length;
	return  make_html(res);
}
