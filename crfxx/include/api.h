#include <vector>
#include <cstdint>

struct Tagger;

Tagger* make_tagger(char* feature_index, char* model_file);

void deleteTagger(Tagger* tagger);

void clear(Tagger* tagger);

void add(Tagger* tagger, char16_t character);

const std::vector<uint32_t>& parse(Tagger* tagger);
