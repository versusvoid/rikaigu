#include <dlib/dnn.h>
#include <dlib/data_io.h>

#include "utf16.h"

#include <unordered_map>
#include <locale>
#include <iconv.h>

using namespace dlib;

typedef matrix<float, 1> vector_t;

std::unordered_map<std::u16string, vector_t> load_vectors(const char* filename)
{
	std::unordered_map<std::u16string, vector_t> result;
	std::ifstream input(filename);
	std::string line;
	iconv_t convertor = iconv_open("UTF-8", "UTF-16");
	while (std::getline(input, line))
	{
		std::u16string key(5, 0);
		char* in = &line[0];
		size_t left = line.find(' ');

		char* out = (char*)&key[0];
		size_t availiable = (key.length() + 1)*sizeof (char16_t);
		key.resize(iconv(convertor, &in, &left, &out, &availiable));


		vector_t vector(15);
		auto start = line.find(' ') + 1;
		auto index = 0U;
		while (start != std::string::npos)
		{
			auto end = line.find(' ', start);
			if (end == std::string::npos)
			{
				end = line.length() + 1;
			}
			vector(index) = std::stof(line.substr(start, end - start));
			index += 1;
		}

		result.emplace(key, vector);
	}

	return result;
}

void load_samples(const char* filename, const std::unordered_map<std::u16string, vector_t>& char_vectors,
	std::vector<vector_t>& training_images, std::vector<unsigned long>& training_labels)
{
#define MAX_LEN 15
	utf16_file input(filename);
	std::u16string line;
	while (input.getline(line))
	{
		std::vector<
	}
}

int main(int, char* argv[])
{
	std::locale::global(std::locale("en_US.UTF-8"));
	using net_type =
		loss_multiclass_log<
			fc<10,
			relu<fc<84,
			relu<fc<120,
			max_pool<2,2,2,2,relu<con<16,5,5,1,1,
			max_pool<2,2,2,2,relu<con<6,5,5,1,1,
			input<vector_t
			>>>>>>>>>>>>;


	std::unordered_map<std::u16string, vector_t> char_vectors = load_vectors(argv[1]);

	std::vector<vector_t> training_images;
	std::vector<unsigned long> training_labels;
	load_samples(argv[2], char_vectors, training_images, training_labels);



	net_type net;
	dnn_trainer<net_type> trainer(net);
	trainer.set_learning_rate(0.01);
	trainer.set_min_learning_rate(0.00001);
	trainer.set_mini_batch_size(128);
	trainer.be_verbose();

//load_mnist_dataset()

	trainer.set_synchronization_file("mnist_sync", std::chrono::seconds(60));


	return 0;
}
