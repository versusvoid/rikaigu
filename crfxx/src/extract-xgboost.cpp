#include <iostream>
#include <cassert>
#include <fstream>
#include <thread>
#include <cstdlib>
#include <algorithm>
#include <numeric>
#include <random>

#include <unordered_map>
#include <xgboost/c_api.h>

#include "utf16.h"
#include "xgboost-common.hpp"

int record_feature(feature_index_t& feature_index, const std::u16string& key)
{
	auto it = feature_index.find(key);
	if (it != feature_index.end())
	{
		it->second += 1;
		return -1;
	}
	else
	{
		feature_index[key] = 1;
		return -1;
	}
}

void make_features(const sample_t& sample,
	const std::function<int(const std::u16string&)>& get_feature_id)
{
	std::vector<uint32_t> fake_features;
	std::vector<float> fake_values;
	for (auto i = 0U; i < sample.size(); ++i)
	{
		get_unigram_features<uint32_t>(sample, i, get_feature_id, fake_features, fake_values);
		multigram_features(sample.tags, i, get_feature_id, fake_features, fake_values);
	}
}

#define MIN_FEATURE_COUNT 100
void filter_features(feature_index_t& feature_index)
{
	uint32_t new_feature_id = 0;
	for(auto it = feature_index.begin(); it != feature_index.end();)
	{
		if (it->second < MIN_FEATURE_COUNT)
		{
			it = feature_index.erase(it);
		}
		else
		{
			it->second = new_feature_id;
			new_feature_id += 1;
			++it;
		}
	}
}

void dump_feature_index(feature_index_t& feature_index, const char* features_index_filename)
{
	std::ofstream out(features_index_filename, std::ios::binary);
	for (auto& kv : feature_index)
	{
		out << kv.first << ':' << std::to_string(kv.second) << std::endl;
	}
}

feature_index_t make_features_from_samples(const char* samples_filename)
{
	feature_index_t feature_index;

	std::ifstream corpus(samples_filename, std::ios::binary);
	utf16_file input(samples_filename);
	std::u16string line;
	uint32_t line_no = 0;
	auto feature_recorder = std::bind(record_feature, std::ref(feature_index), std::placeholders::_1);
	while(input.getline(line))
	{
		line_no += 1;
		if (line_no % 10000 == 0)
		{
			std::cout << samples_filename << ": " << line_no << std::endl;
		}

		if (line.length() > 0)
		{
			auto sample = read_sample(line);
			make_features(sample, feature_recorder);
		}
	}
	std::cout << feature_index.size() << " raw features" << std::endl;
	filter_features(feature_index);
	std::cout << feature_index.size() << " filtered features" << std::endl;
	dump_feature_index(feature_index, "segmentation/features.txt");

	return feature_index;
}

struct csr_matrix_t {
	std::vector<float> data;
	std::vector<unsigned> indices;
	std::vector<bst_ulong> indptr;
	std::vector<float> labels;
};


static std::random_device RANDOM_DEVICE;
void shuffle(csr_matrix_t& matrix)
{
	csr_matrix_t result;
	result.data.reserve(matrix.data.size());
	result.indices.reserve(matrix.indices.size());
	result.labels.reserve(matrix.labels.size());
	result.indptr.reserve(matrix.indptr.size());

	std::vector<uint32_t> permutation(matrix.labels.size(), 0);
	std::iota(permutation.begin(), permutation.end(), 0);
	std::shuffle(permutation.begin(), permutation.end(), std::mt19937(RANDOM_DEVICE()));

	for(auto index : permutation) {

		result.labels.push_back(matrix.labels.at(index));

		result.indptr.push_back(result.indices.size());

		auto start = matrix.indptr.at(index);
		auto end = index == matrix.indptr.size() - 1? matrix.indices.size() : matrix.indptr.at(index + 1);
		for(bst_ulong j = start; j < end; ++j) {
			result.indices.push_back(matrix.indices.at(j));
			result.data.push_back(matrix.data.at(j));
		}
	}

	matrix = std::move(result);
}

std::ostream& operator<<(std::ostream& out, const std::vector<float>& vs)
{
	for (auto v : vs)
	{
		out << v << " ";
	}
	return out;
}

void samples_to_dmatrix(const feature_index_t& feature_index, const char* samples_filename)
{
	csr_matrix_t matrix;
	std::ifstream corpus(samples_filename, std::ios::binary);
	utf16_file input(samples_filename);
	std::u16string line;
	uint32_t line_no = 0;
	samples_t samples;
	auto feature_getter = std::bind(get_feature_id, std::ref(feature_index), std::placeholders::_1);
	while(input.getline(line))
	{
		line_no += 1;
		if (line_no % 10000 == 0)
		{
			std::cout << samples_filename << ": " << line_no << std::endl;
		}

		if (line.length() > 0)
		{
			auto sample = read_sample(line);
			for (auto i = 0U; i < sample.size(); ++i)
			{
				matrix.indptr.push_back(matrix.indices.size());
				matrix.labels.push_back(float(sample.tags[i] == 'S'));
				get_unigram_features(sample, i, feature_getter, matrix.indices, matrix.data);
				multigram_features(sample.tags, i, feature_getter, matrix.indices, matrix.data);
			}
			/*
			std::cout << sample.sequence << std::endl
				<< sample.classes << std::endl
				<< sample.tags << std::endl
				<< matrix.labels << std::endl;
			std::getchar();
			*/

			samples.emplace_back(sample);
		}
	}

	shuffle(matrix);
	matrix.indptr.push_back(matrix.indices.size());

	std::string out_filename(samples_filename);
	out_filename = out_filename.substr(0, out_filename.find('.')) + ".dmatrix";

	DMatrixHandle xgb_set;
	XGDMatrixCreateFromCSREx(matrix.indptr.data(), matrix.indices.data(), matrix.data.data(),
						   matrix.indptr.size(), matrix.data.size(), feature_index.size(), &xgb_set);
	XGDMatrixSetFloatInfo(xgb_set, "label", matrix.labels.data(), matrix.labels.size());
	XGDMatrixSaveBinary(xgb_set, out_filename.c_str(), 0);
}

int main(int argc, char *argv[])
{
	if (argc != 3) throw std::logic_error("Need two arguments");
	std::locale::global(std::locale("en_US.UTF-8"));
	load_endings();

	std::cout << argv[1] << " " << argv[2] << std::endl;

	feature_index_t feature_index = make_features_from_samples(argv[1]);
	samples_to_dmatrix(feature_index, argv[1]);
	samples_to_dmatrix(feature_index, argv[2]);


	return 0;
}
