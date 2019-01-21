#ifndef HTML_RENDER_H
#define HTML_RENDER_H
#include "dictionaries.h"

const char* make_html(SearchResult& result);

bool render_init(const char* radicals_file_content, uint32_t length);

#endif // HTML_RENDER_H
