#include <iostream>
#include <cassert>
#include <fstream>
#include <thread>
#include <cstdlib>
#include <algorithm>
#include <numeric>
#include <random>
#include <cstring>

#include <unordered_map>
#include <xgboost/c_api.h>

#include "utf16.h"
#include "xgboost-common.hpp"


static std::array<char, NUM_LABELS> LABELS = {'M', 'S'};
std::string iterated(BoosterHandle booster, const feature_index_t& feature_index, const sample_t& sample)
{
	auto feature_getter = std::bind(get_feature_id, std::ref(feature_index), std::placeholders::_1);
	std::string result;

	std::vector<unsigned> features;
	std::vector<float> values;

	for (auto i = 0U; i < sample.size(); ++i)
	{
		get_unigram_features(sample, i, feature_getter, features, values);
		multigram_features(result, i, feature_getter, features, values);

		bst_ulong indptr[2] = {0, features.size()};

		DMatrixHandle dmatrix;
		XGDMatrixCreateFromCSREx(indptr, features.data(), values.data(), 2, 1, feature_index.size(), &dmatrix);

		bst_ulong len;
		const float* predicted;
		XGBoosterPredict(booster, dmatrix, 0, 0, &len, &predicted);
		result.push_back(LABELS[uint32_t(predicted[0] > 0.5f)]);

		XGDMatrixFree(dmatrix);
		features.clear();
		values.clear();
	}

	return result;
}

void test(BoosterHandle booster, const feature_index_t& feature_index, const char* filename)
{
	double tp = 0.0, tn = 0.0, fp = 0.0, fn = 0.0, true_last = 0.0, num_samples = 0.0;
	std::ifstream corpus(filename, std::ios::binary);
	utf16_file input(filename);
	std::u16string line;
	uint32_t line_no = 0;
	while(input.getline(line))
	{
		line_no += 1;
		if (line_no % 10000 == 0)
		{
			std::cout << filename << ": " << line_no << std::endl;
		}

		if (line.empty()) continue;

		auto sample = read_sample(line);
		const auto prediction = iterated(booster, feature_index, sample);
		assert(prediction.size() == sample.size());
		bool sample_true_last = true;
		for (auto i = 0U; i < prediction.size(); ++i)
		{
			const char gold = sample.tags[i];
			if (gold == 'M' and prediction[i] == 'M')
			{
				tn += 1;
			}
			else if (gold == 'S' and prediction[i] == 'S')
			{
				tp += 1;
				sample_true_last = true;
			}
			else if (gold == 'M' and prediction[i] == 'S')
			{
				fp += 1;
				sample_true_last = false;
			}
			else
			{
				fn += 1;
				sample_true_last = false;
			}
		}
		true_last += double(sample_true_last);
		num_samples += 1;
	}

	double precision = tp / (tp + fp);
	double recall = tp / (tp + fn);
	double true_last_ratio = true_last / num_samples;
	double f1 = 2 * precision * recall / (precision + recall);
	std::cout << filename << ":" << std::endl;
	std::cout << " \t\t \t\t0->1" << std::endl;
	std::cout << " \t\t" << tn << "\t\t" << fp << std::endl;
	std::cout << "1->0\t\t" << fn << "\t\t" << tp << std::endl;
	std::cout
		<< "tlast = " << true_last_ratio
		<< ", recall = " << recall
		<< ", precision = " << precision
		<< ", F1 = " << f1 << std::endl;
}

feature_index_t load_feature_index(const char* filename)
{
	feature_index_t result;
	std::ifstream input(filename);
	std::string line;
	while (std::getline(input, line))
	{
		auto p = line.find(':');
		assert(p != std::string::npos);

		std::u16string key;
		mbstate_t ps;
		memset(&ps, 0, sizeof(ps));
		size_t i = 0;
		while (i < p)
		{
			wchar_t character;
			const size_t count = mbrtowc(&character, line.data() + i, p - i, &ps);
			if (character > 0xffff)
			{
				throw std::logic_error("Unexpected character in feature " + line);
			}
			assert(count > 0 && count <= 4);
			key += char16_t(character);
			i += count;
		}
		result[key] = std::stoul(line.substr(p + 1));
	}
	return result;
}

int main(int argc, char *argv[])
{
	if (argc != 4) throw std::logic_error("Need three arguments");
	std::locale::global(std::locale("en_US.UTF-8"));
	load_endings();

	std::cout << argv[1] << " " << argv[2] << " " << argv[3] << std::endl;

	feature_index_t feature_index = load_feature_index(argv[1]);

	BoosterHandle booster;
	assert(XGBoosterCreate(nullptr, 0, &booster) == 0);
	assert(XGBoosterLoadModel(booster, argv[2]) == 0);
	assert(XGBoosterSetParam(booster, "nthread", "1") == 0);

	test(booster, feature_index, argv[3]);
	return 0;
}
