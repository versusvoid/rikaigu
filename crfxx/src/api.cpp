#include <crfxx/api.h>

#include <unordered_map>
#include <sstream>

#include "encode.h"

struct Tagger
{

	Predictor<train_feature_index_t> predictor;
	sample_t sample;

};

Tagger* makeTagger()
{
	return new Tagger;
}

void setFeatureIndex(Tagger* tagger, char* feature_index, uint32_t length)
{
	std::istringstream in(std::string(feature_index, length));
	tagger->predictor.feature_index = new train_feature_index_t(load_feature_index(in));
	free(feature_index);
}

void setWeights(Tagger* tagger, char* weights)
{
	tagger->predictor.weights = (double*)weights;
}

void deleteTagger(Tagger* tagger)
{
	free(const_cast<double*>(tagger->predictor.weights));
	delete tagger;
}

void clear(Tagger* tagger)
{
	tagger->sample.clear();
}

void add(Tagger* tagger, char16_t character)
{
	tagger->sample.emplace_back(symbol_t{character, symbolClass(character), 0});
}

const std::vector<uint32_t>& parse(Tagger* tagger)
{
	return predict(tagger->predictor, tagger->sample);
}
