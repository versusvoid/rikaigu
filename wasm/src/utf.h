#include <stddef.h>
#include <uchar.h>

#include "state.h"

wchar_t decode_utf16_wchar(const char16_t* text);

int utf16_compare(const char16_t* a, const size_t alen, const char16_t* b, const size_t blen);

size_t utf16_drop_code_point(const char16_t* data, size_t pos);

void input_kata_to_hira(input_t* input);
