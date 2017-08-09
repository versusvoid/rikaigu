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

void setWeights(Tagger* tagger, char* weights, uint32_t length)
{
	float* float_weights = reinterpret_cast<float*>(weights);
	size_t num = length / sizeof(float);
	double* double_weights = (double*)malloc(num * sizeof(double));
	for (auto i = 0U; i < num; ++i)
	{
		double_weights[i] = float_weights[i];
	}
	tagger->predictor.weights = double_weights;
	free(weights);
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
	printf("%u expanded features, %zu base features\n", tagger->predictor.feature_index->num_features, tagger->predictor.feature_index->map.size());
	auto& res = predict(tagger->predictor, tagger->sample);
	for (auto i = 0U; i < tagger->sample.size(); ++i)
	{
		printf("%d %d\n", int(tagger->sample[i].symbol), int(res[i]));
	}
	return res;
}
