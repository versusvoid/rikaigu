#include <unordered_map>
#include <iostream>
#include <cassert>

#include "encode.h"
#include "utf16.h"

sample_t read_sample(const std::u16string& line)
{
	std::vector<symbol_t> result;

	uint8_t tag = 1; // S
	for (auto& character : line)
	{
		if (character == char16_t(' '))
		{
			tag = 1;
			continue;
		}

		result.push_back({character, symbolClass(character), tag});
		tag = 0;
	}

	for (auto i = 0U; i < result.size(); ++i)
	{
		result[i].tag <<= 2;
		result[i].tag |= (i + 1 < result.size() ? result[i + 1].tag << 1 : 0);
		result[i].tag |= (i + 2 < result.size() ? result[i + 2].tag : 0);
	}

	result.shrink_to_fit();

	return result;
}

void test(const weights_t& weights, const train_feature_index_t& feature_index, const char* filename)
{
	auto input = utf16_file(filename);
	double tp = 0.0, tn = 0.0, fp = 0.0, fn = 0.0, true_first = 0.0, true_last = 0.0, num_samples = 0.0;

	Predictor<train_feature_index_t> predictor;
	predictor.feature_index = &feature_index;
	predictor.weights = weights.data();

	std::u16string line;
	uint32_t line_no = 0;
	while(input.getline(line))
	{
		if (line.empty()) continue;

		const auto sample = read_sample(line);
		const std::vector<uint32_t>& prediction = predict(predictor, sample);
		assert(prediction.size() >= sample.size());
		bool first_start = true;
		uint32_t sample_true_last = 1;
		for (auto i = 0U; i < sample.size(); ++i)
		{
			const uint32_t gold = sample[i].tag >> 2;
			const uint32_t predicted = prediction[i];
			if (gold == 0 and predicted == 0)
			{
				tn += 1;
			}
			else if (gold == 1 and predicted == 1)
			{
				tp += 1;
				true_first += (first_start ? 1 : 0);
				first_start = false;
				sample_true_last = 1;
			}
			else if (gold == 0 and predicted == 1)
			{
				fp += 1;
				first_start = false;
				sample_true_last = 0;
			}
			else
			{
				fn += 1;
				first_start = false;
				sample_true_last = 0;
			}
		}

		true_first += (first_start ? 1 : 0);
		true_last += sample_true_last;
		num_samples += 1;

		line_no += 1;
		if (line_no % 500000 == 0)
		{
			std::cout << filename << ": " << line_no << std::endl;
		}
	}

	double precision = tp / (tp + fp);
	double recall = tp / (tp + fn);
	double true_first_ratio = true_first / num_samples;
	double true_last_ratio = true_last / num_samples;
	double f1 = 2 * precision * recall / (precision + recall);
	std::cout << filename << ":" << std::endl;
	std::cout << num_samples << std::endl;
	std::cout << true_first << std::endl;
	std::cout << tp << "\t\t" << fp << std::endl;
	std::cout << fn << "\t\t" << tn << std::endl;
	std::cout
		<< "tfirst = " << true_first_ratio
		<< ", tlast = " << true_last_ratio
		<< ", recall = " << recall
		<< ", precision = " << precision
		<< ", F1 = " << f1 << std::endl;
}

void main_init()
{
	std::locale::global(std::locale("en_US.UTF-8"));
	std::cout.setf(std::ios::fixed, std::ios::floatfield);
	std::cout.precision(5);
}
