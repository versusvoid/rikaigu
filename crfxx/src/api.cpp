#include <api.h>

#include <unordered_map>
#include <sstream>

#include "encode.h"

struct Tagger
{

	Predictor<train_feature_index_t> predictor;
	sample_t sample;

};

Tagger* make_tagger(char* feature_index_file, char* model_file)
{
	auto tagger = new Tagger;
	tagger->predictor.weights = (double*)model_file;

	std::istringstream in(feature_index_file);
	tagger->predictor.feature_index = new train_feature_index_t(std::move(load_feature_index(in)));
	free(feature_index_file);

	return tagger;
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
