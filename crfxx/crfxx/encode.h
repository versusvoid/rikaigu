#include <vector>
#include <string>
#include <cstdint>

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

sample_t read_sample(const std::u16string& line);
