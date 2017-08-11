#pragma once
#include <vector>
#include <string>
#include <cstdint>
#include <unordered_map>
#include <memory>

static const std::vector<std::string> tags = {
	"MMM",
	"MMS",
	"MSM",
	"MSS",
	"SMM",
	"SMS",
	"SSM",
	"SSS"
};
const size_t NUM_LABELS = tags.size();

struct symbol_t
{
	char16_t symbol;
	char symbol_class;
	uint8_t tag;
};

typedef std::vector<symbol_t> sample_t;
typedef std::vector<std::vector<uint32_t>> sample_features_t;
typedef std::vector<sample_t> samples_t;
typedef std::vector<double> weights_t;

template<typename feature_index_t>
inline void record_feature(feature_index_t& feature_index, const std::u16string& key, std::vector<uint32_t>& features)
{
	int feature_id = feature_index.get_feature_id(key);
	if (feature_id >= 0)
	{
		features.push_back(uint32_t(feature_id));
	}
}

template<typename feature_index_t>
void make_features(const sample_t& sample,
	feature_index_t& feature_index,
	sample_features_t& unigram_features,
	sample_features_t& bigram_features)
{
	if (unigram_features.size() < sample.size())
	{
		unigram_features.resize(sample.size());
		bigram_features.resize(sample.size());
	}

	for (auto i = 0; size_t(i) < sample.size(); ++i)
	{
		std::vector<uint32_t>& symbol_unigram_features = unigram_features[i];
		symbol_unigram_features.clear();

		char16_t key = u'а';
		for (auto start : {-2, -1, 0, 1, 2})
		{
			std::u16string symbol_feature;
			std::u16string symbol_class_feature;
			for (auto len : {1, 2, 3})
			{
				if (start + len - 1 > 2) break;
				int index = i + start + len - 1;
				if (index < 0 || size_t(index) >= sample.size())
				{
					std::string number = std::to_string(index < 0 ? index : index + 1 - int(sample.size()));
					symbol_feature.append(u"S[");
					symbol_feature.append(number.begin(), number.end());
					symbol_feature.append(u"]");

					symbol_class_feature.append(u"C[");
					symbol_class_feature.append(number.begin(), number.end());
					symbol_class_feature.append(u"]");
				}
				else
				{
					symbol_feature += sample[index].symbol;
					symbol_class_feature += char16_t(sample[index].symbol_class);
				}

				record_feature(feature_index, std::u16string(u"U") + key + symbol_feature, symbol_unigram_features);
				++key;
				record_feature(feature_index, std::u16string(u"U") + key + symbol_class_feature, symbol_unigram_features);
				++key;
			}
		}

		if (i > 0)
		{
			std::vector<uint32_t>& symbol_bigram_features = bigram_features[i];
			symbol_bigram_features.clear();
			record_feature(feature_index, u"B", symbol_bigram_features);

			std::u16string f = u"B1";
			f += char16_t(sample[i - 1].symbol_class);
			f += char16_t(sample[i].symbol_class);
			if (size_t(i + 1) < sample.size())
			{
				f += char16_t(sample[i + 1].symbol_class);
			}
			else
			{
				f += u"C[1]";
			}
			record_feature(feature_index, f, symbol_bigram_features);
		}
	}
}

inline symbol_t read_symbol(char16_t symbol);

struct Node
{
	double alpha;
	double beta;
	double cost;
	double bestCost;
	size_t prev;
	std::vector<double> lpath;
	std::vector<double> rpath;

	Node()
		: alpha(0.0)
		, beta(0.0)
		, cost(0.0)
		, bestCost(0.0)
		, prev(NUM_LABELS)
	{}
};

template<typename feature_index_t>
struct Predictor
{
	const feature_index_t* feature_index;
	const double* weights;

	std::vector<std::vector<uint32_t>> unigram_features;
	std::vector<std::vector<uint32_t>> bigram_features;
	std::vector<std::vector<Node>> nodes;
	std::vector<uint32_t> result_;
};


#define COST_FACTOR 1.0
template<typename feature_index_t>
void calcCost(Predictor<feature_index_t>& predictor, size_t x, size_t y)
{
	Node& n = predictor.nodes[x][y];
	n.cost = 0.0;
	for (auto feature_id : predictor.unigram_features[x])
	{
		n.cost += COST_FACTOR*predictor.weights[feature_id + y];
	}

	for (auto i = 0U; i < n.lpath.size(); ++i)
	{
		n.lpath[i] = 0.0;
		for (auto feature_id : predictor.bigram_features[x])
		{
			n.lpath[i] += COST_FACTOR*predictor.weights[feature_id + i * NUM_LABELS + y];
		}
		predictor.nodes[x-1][(i << 2) | (y >> 1)].rpath[y & 0b1] = n.lpath[i];
	}
}

template<typename feature_index_t>
void buildLattice(Predictor<feature_index_t>& predictor, const sample_t& sample)
{
	if (predictor.nodes.size() < sample.size())
	{
		size_t old_size = predictor.nodes.size();
		predictor.nodes.resize(sample.size());
		for (auto i = old_size; i < predictor.nodes.size(); ++i)
		{
			predictor.nodes[i].resize(NUM_LABELS);
			if (i == 0) continue;

			for (auto y12 = 0U; y12 < 2 * NUM_LABELS; ++y12)
			{
				auto y1 = y12 >> 1;
				auto y2 = y12 & 0b111;
				predictor.nodes[i - 1][y1].rpath.push_back(0.0);
				predictor.nodes[i][y2].lpath.push_back(0.0);
			}
		}
	}

	for (size_t i = 0; i < sample.size(); ++i)
	{
		for (size_t j = 0; j < NUM_LABELS; ++j)
		{
			calcCost(predictor, i, j);
		}
	}
}

template<typename feature_index_t>
void viterbi(Predictor<feature_index_t>& predictor, const sample_t& sample)
{
	for (size_t i = 0; i < sample.size(); ++i)
	{
		for (size_t j = 0; j < NUM_LABELS; ++j)
		{
			double bestCost = -1e37;
			ssize_t best = -1;
			Node& n = predictor.nodes[i][j];
			for (auto k = 0U; k < n.lpath.size(); ++k)
			{
				size_t prev_y = (k << 2) | (j >> 1);
				double cost = predictor.nodes[i-1][prev_y].bestCost + n.lpath[k] + n.cost;
				if (cost > bestCost)
				{
					bestCost = cost;
					best  = ssize_t(prev_y);
				}
			}
			n.prev = best;
			n.bestCost = (best != -1) ? bestCost : n.cost;
		}
	}

	double bestc = -1e37;
	size_t y = NUM_LABELS;
	size_t s = sample.size() - 1;
	for (size_t j = 0; j < NUM_LABELS; ++j)
	{
		if (bestc < predictor.nodes[s][j].bestCost)
		{
			y  = j;
			bestc = predictor.nodes[s][j].bestCost;
		}
	}

	if (predictor.result_.size() < sample.size())
	{
		predictor.result_.resize(sample.size(), 0);
	}
	size_t i = sample.size();
	while (i > 0)
	{
		--i;
		predictor.result_[i] = uint32_t(y >> 2);
		y = predictor.nodes[i][y].prev;
	}
}

template<typename feature_index_t>
const std::vector<uint32_t>& predict(Predictor<feature_index_t>& predictor, const sample_t& sample)
{
	make_features(sample, *predictor.feature_index, predictor.unigram_features, predictor.bigram_features);

//	std::cout << "sample:\n" << std::make_pair(sample, features) << std::endl;

	buildLattice(predictor, sample);
	viterbi(predictor, sample);

//	std::cout << "lattice:\n" << nodes;

	return predictor.result_;
}

struct train_feature_index_t
{
	uint32_t num_features;
	std::unordered_map<std::u16string, uint32_t> map;
	train_feature_index_t()
		: num_features(0)
	{}

	int get_feature_id(const std::u16string& key) const
	{
		auto it = map.find(key);
		if (it != map.end())
		{
			return int(it->second);
		}
		else
		{
			return -1;
		}
	}
};
train_feature_index_t load_feature_index(std::istream& in);

inline char symbolClass(char16_t character)
{
	if (character >= 0x4e00 && character <= 0x9fa5)
	{
			return 'K';
	}
	else if (character >= 0x3040 && character <= 0x309f)
	{
		return 'h';
	}
	else if (character >= 0x30a1 && character <= 0x30fe)
	{
		return 'k';
	}
	else
	{
		return 'm';
	}
}
