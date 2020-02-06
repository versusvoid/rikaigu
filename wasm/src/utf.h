#include <stddef.h>

#include "state.h"

wchar_t decode_utf16_wchar(const char16_t** pText);

int utf16_compare(const char16_t* a, const size_t alen, const char16_t* b, const size_t blen);

size_t utf16_drop_code_point(const char16_t* data, size_t pos);

void input_kata_to_hira(input_t* input);

bool utf16_utf8_kata_to_hira_eq(
	const char16_t* key, const size_t key_length,
	const char* utf8, const size_t utf8_length
);

bool is_hiragana(const char16_t* word, const size_t length);
