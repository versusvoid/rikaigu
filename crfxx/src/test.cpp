#include <cstring>

#include "common.hpp"

weights_t load_weights(const char* filename)
{
	std::ifstream in(filename, std::ios::binary);
	weights_t result;
	while (!in.eof())
	{
		float w;
		in.read((char*)&w, sizeof(w));
		result.push_back(w);
	}
	result.pop_back();
	return result;
}

train_feature_index_t load_feature_index(const char* filename)
{
	std::ifstream in(filename);
	train_feature_index_t result;
	std::string line;
	while (std::getline(in, line))
	{
		auto p = line.find('\t');
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
		uint32_t feature_id = std::stoul(line.substr(p + 1));
		result[key] = feature_id;
		result.num_features = std::max(result.num_features,
			feature_id + uint32_t(key[0] == u'B' ? 2 * NUM_LABELS : NUM_LABELS));
	}

	return result;
}

int main(int argc, char *argv[])
{
	if (argc < 4)
	{
		std::cerr << "Not enough arguments. Usage: " << argv[0]
			<< " feature-index.file weights.file samples.file [samples.file...]" << std::endl;
		return 1;
	}
	main_init();

	train_feature_index_t feature_index = load_feature_index(argv[1]);
	weights_t weights = load_weights(argv[2]);
	std::cout << feature_index.num_features << " " << weights.size() << std::endl;
	assert(weights.size() == feature_index.num_features);
	for (auto i = 3; i < argc; ++i)
	{
		test(weights, feature_index, argv[i]);
	}
}
