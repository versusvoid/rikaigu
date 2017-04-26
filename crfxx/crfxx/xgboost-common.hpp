#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <cstdint>
#include <functional>
#include <fstream>
#include <cstring>
#include <cassert>

struct sample_t
{
	std::u16string sequence;
	std::string classes;
	std::string tags;

	inline size_t size() const { return sequence.size(); }
};

typedef std::vector<std::vector<uint32_t>> sample_features_t;
typedef std::vector<sample_t> samples_t;
typedef std::unordered_map<std::u16string, uint32_t> feature_index_t;

std::ostream& operator<<(std::ostream& out, const std::u16string& str)
{
	char mb[5];
	for (auto c : str)
	{
		mb[wctomb(mb, c)] = 0;
		out << mb;
	}
	return out;
}

#define NUM_LABELS 2

sample_t read_sample(const std::u16string& line)
{
	sample_t result;

	char tag = 'M';
	for (auto& character : line)
	{
		if (character == char16_t(' '))
		{
			tag = 'S';
			continue;
		}

		result.sequence.push_back(character);
		result.tags.push_back(tag);
		tag = 'M';

		if (character >= 0x4e00 && character <= 0x9fa5) {
			result.classes.push_back('K');
		} else if (character >= 0x3040 && character <= 0x309f) {
			result.classes.push_back('h');
		} else if (character >= 0x30a1 && character <= 0x30fe) {
			result.classes.push_back('k');
		} else {
			result.classes.push_back('m');
		}
	}

	result.sequence.shrink_to_fit();
	result.classes.shrink_to_fit();
	result.tags.shrink_to_fit();

	return result;
}

static std::unordered_set<std::u16string> endings;
void load_endings()
{
	std::ifstream input("data/deinflect.dat");
	std::string line;
	while (std::getline(input, line))
	{
		if (uint8_t(line[0]) < 0x80) continue;

		std::u16string key;
		mbstate_t ps;
		memset(&ps, 0, sizeof(ps));
		size_t i = 0;
		bool seen_tab = false;
		while (i < line.length())
		{
			wchar_t character;
			const size_t count = mbrtowc(&character, line.data() + i, line.length() - i, &ps);
			if (character > 0xffff)
			{
				throw std::logic_error("Unexpected character in deinflect " + line);
			}
			i += count;
			if (count == 1)
			{
				assert(character == L'\t');
				if (seen_tab) break;
				endings.insert(key);
				key.clear();
				seen_tab = true;
				continue;
			}
			assert(count > 0 && count <= 4);
			key += char16_t(character);
		}
		endings.insert(key);
	}
	endings.erase(u"");
}

#define RECORD_FEATURE(key, value) \
{ \
	feature_id = get_feature_id(key); \
	if (feature_id >= 0) \
	{ \
		features.emplace_back(I(feature_id)); \
		feature_values.emplace_back(value); \
	} \
}
template <typename I>
void get_unigram_features(const sample_t& sample, uint32_t i,
	const std::function<int(const std::u16string&)>& get_feature_id,
	std::vector<I>& features, std::vector<float>& feature_values)
{
	int feature_id;
	char16_t key = u'а';
	for (int start : {-5, -1, 0, 1, 5})
	{
		std::u16string symbol_feature;
		std::u16string symbol_class_feature;
		for (int len : {1, 2, 3, 3, 5, 6})
		{
			if (start + len - 1 > 2) break;
			int index = int(i) + start + len - 1;
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
				symbol_feature += sample.sequence[index];
				symbol_class_feature += char16_t(sample.classes[index]);
			}

			RECORD_FEATURE(std::u16string(u"U") + key + symbol_feature, 1.0)
			++key;
			RECORD_FEATURE(std::u16string(u"U") + key + symbol_class_feature, 1.0)
			++key;
		}
	}

	RECORD_FEATURE(u"Uposition", i)
	for (auto j = 0U; j < i; ++j)
	{
		auto it = endings.find(sample.sequence.substr(j, i - j));
		if (it != endings.end())
		{
			RECORD_FEATURE(u"Uinflection" + *it, 1.0)
		}
	}
}

template<typename I>
void multigram_features(const std::string& tags, uint32_t i,
	const std::function<int(const std::u16string&)>& get_feature_id,
	std::vector<I>& features, std::vector<float>& feature_values)
{
	int feature_id;
	if (i > 0)
	{
		std::u16string f(u"B0");
		f += char16_t(tags.at(i - 1));
		RECORD_FEATURE(f, 1.0)
		if (i > 1)
		{
			f = u"B1";
			f += char16_t(tags.at(i - 2));
			RECORD_FEATURE(f, 1.0)

			f = u"B2";
			f += char16_t(tags.at(i - 2));
			f += char16_t(tags.at(i - 1));
			RECORD_FEATURE(f, 1.0)
		}
	}

	float len = 0.0;
	while (i > 0)
	{
		--i;
		if (tags.at(i) == 'S') break;
		len += 1.0;
	}
	RECORD_FEATURE(u"Bstraight", len);
}

int get_feature_id(const feature_index_t& feature_index, const std::u16string& key)
{
	auto it = feature_index.find(key);
	if (it == feature_index.end())
	{
		return -1;
	}
	else
	{
		return int(it->second);
	}
}
