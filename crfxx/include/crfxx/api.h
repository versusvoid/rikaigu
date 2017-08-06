#include <vector>
#include <cstdint>

struct Tagger;

Tagger* makeTagger();

void setFeatureIndex(Tagger* tagger, char* feature_index, uint32_t length);

void setWeights(Tagger* tagger, char* weights);

void deleteTagger(Tagger* tagger);

void clear(Tagger* tagger);

void add(Tagger* tagger, char16_t character);

const std::vector<uint32_t>& parse(Tagger* tagger);
