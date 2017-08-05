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

int main(int argc, char *argv[])
{
	if (argc < 4)
	{
		std::cerr << "Not enough arguments. Usage: " << argv[0]
			<< " feature-index.file weights.file samples.file [samples.file...]" << std::endl;
		return 1;
	}
	main_init();

	std::ifstream in(argv[1]);
	train_feature_index_t feature_index = load_feature_index(in);
	weights_t weights = load_weights(argv[2]);
	std::cout << feature_index.num_features << " " << weights.size() << std::endl;
	assert(weights.size() == feature_index.num_features);
	for (auto i = 3; i < argc; ++i)
	{
		test(weights, feature_index, argv[i]);
	}
}
