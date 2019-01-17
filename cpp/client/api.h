#ifndef API_H
#define API_H
#include <emscripten.h>
#include <cstdint>

extern "C" {
void EMSCRIPTEN_KEEPALIVE rikaigu_set_config(
	bool only_reading,
	bool kanji_components,
	bool deinflect_expressions,
	int default_dictionary,
	const char* kanji_info,
	const char* review_list);

bool EMSCRIPTEN_KEEPALIVE rikaigu_set_file(const char* filename, char* data, uint32_t length);

const char* EMSCRIPTEN_KEEPALIVE rikaigu_search(const char* utf8_text, const char* utf8_prefix,
	int32_t* match_symbols_length, int32_t* prefix_symbols_length);

const char* EMSCRIPTEN_KEEPALIVE rikaigu_review_entries_for_sentence(const char* utf8_text);
}
#endif // API_H
