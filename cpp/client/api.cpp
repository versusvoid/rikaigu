#include "api.h"
#include "dictionaries.h"
#include "html_render.h"
#include "utils.h"

#include <locale>
#include <iostream>
#include <clocale>
#include <cstring>
#include <cassert>

static bool locale_initialized = false;
static void initialize_locale()
{
	if (locale_initialized) return;

	std::locale::global(std::locale("C.UTF-8"));

	mbstate_t ps;
	memset(&ps, 0, sizeof(ps));

	const char love[] = u8"愛";
	wchar_t character;
	size_t count = mbrtowc(&character, love, sizeof(love), &ps);
	assert(count == 3);
	assert(character == 0x611b);

	memset(&ps, 0, sizeof(ps));
	const char perch[] = u8"𩺊";
	count = mbrtowc(&character, perch, sizeof(perch), &ps);
	assert(count == 4);
	assert(character == 0x29e8a);

	locale_initialized = true;
}

bool rikaigu_set_file(const char* filename, char* data, uint32_t length)
{
	initialize_locale();

	if (0 == strcmp(filename, "data/radicals.dat"))
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

//	printf("rikaigu_search(%s, %s)\n", utf8_text, utf8_prefix);
	SearchResult res = search(utf8_text);
	*prefix_symbols_length = 0;
//	printf("Plain search res.max_match_symbols_length = %zu\n", res.max_match_symbols_length);
	*match_symbols_length = int32_t(res.max_match_symbols_length) - *prefix_symbols_length;
	return  make_html(res);
}
