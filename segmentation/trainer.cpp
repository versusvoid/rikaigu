#include <iostream>
#include <dlib/svm_threaded.h>
#include <dlib/sparse_vector.h>
#include <dlib/rand.h>
#include <codecvt>

#include "filter_feature_index.h"
#include "train_feature_index.h"
#include "feature_extractor.hpp"

enum Label : unsigned long
{
	START = 1,
	MIDDLE = 0,
};

std::shared_ptr<filter_feature_index> compute_initial_index(const char* filename,
	std::vector<std::vector<char16_t>>& samples,
	std::vector<std::vector<unsigned long>>& labels)
{
	std::locale::global(std::locale("en_US.UTF-8"));

	feature_extractor<filter_feature_index> fe;

	dlib::matrix<unsigned long,1,1> fake_y;
	auto fake_set_feature = [] (unsigned long){};

	std::ifstream corpus(filename, std::ios::binary);

	std::vector<char> buffer(2<<16, 0);
	const char16_t* utf16_buffer = reinterpret_cast<const char16_t*>(buffer.data());
	size_t line_no = 0;
	uint32_t write_offset = 0;
	while(corpus.read(&buffer[write_offset], std::streamsize(buffer.size())) && corpus.gcount() > 0)
	{
		assert(corpus.gcount() % 2 == 0);
		const auto length = (write_offset + uint32_t(corpus.gcount())) / 2;
		const char16_t* start = utf16_buffer;
		const char16_t* end = std::find(start, start + length, char16_t('\n'));
		while (end < utf16_buffer + length)
		{
			std::vector<char16_t> sample;
			std::vector<unsigned long> sample_labels;


			line_no += 1;
			if (line_no % 10000 == 0)
			{
				std::cout << filename << ": " << line_no << std::endl;
			}

//			char mb[5];
			while (start < end)
			{
//				mb[wctomb(mb, wchar_t(*start))] = 0;
//				std::cout << mb;
				if (*start == char16_t(' '))
				{
					sample_labels.back() = START;
				}
				else
				{
					sample.push_back(*start);
					sample_labels.push_back(MIDDLE);
				}
				++start;
			}
//			std::cout << std::endl;
//			std::getchar();

			sample.shrink_to_fit();
			sample_labels.shrink_to_fit();

			for (auto i = 0U; i < sample.size(); ++i)
			{
				fe.get_features(fake_set_feature, sample, fake_y, i);
			}

			samples.push_back(std::move(sample));
			labels.push_back(std::move(sample_labels));


			start = end + 1;
			end = std::find(start, utf16_buffer + length, char16_t('\n'));
		}

		if (start < utf16_buffer + length)
		{
			write_offset = uint32_t(end - start) * sizeof(char16_t);
			memmove((void*)utf16_buffer, (void*)start, write_offset);
		}
		else
		{
			write_offset = 0;
		}
	}

	samples.shrink_to_fit();
	labels.shrink_to_fit();

	return fe.index;
}

int main()
{
	std::vector<std::vector<char16_t> > samples;
	std::vector<std::vector<unsigned long> > labels;
	std::shared_ptr<filter_feature_index> initial_index = compute_initial_index("l-cv.csv", samples, labels);
	std::cout << "initial index done" << std::endl;
	std::shared_ptr<train_feature_index>  train_index = std::make_shared<train_feature_index>(initial_index->features, "feature-index.bin");
	std::cout << "train index created" << std::endl;

	feature_extractor<train_feature_index> fe(train_index);

	dlib::structural_sequence_labeling_trainer<feature_extractor<train_feature_index>> trainer(fe);
	std::cout << "trainer created" << std::endl;
	trainer.set_epsilon(0.0001);
	trainer.set_num_threads(8);
	trainer.set_max_cache_size(0);
	trainer.set_c(9);
	trainer.be_verbose();

	const long num_in_test = samples.size()/5;
	const long num_in_train = samples.size() - num_in_test;

	decltype(samples) x_test, x_train;
	std::vector<std::vector<unsigned long> > y_test, y_train;

	long next_test_idx = 0;

	dlib::matrix<double> confusion_matrix(2, 2);
	confusion_matrix = 0;

	int true_first = 0;
	int num_samples = 0;

	auto labeler = trainer.train(samples, labels);
	std::vector<unsigned long> pred;
	for (unsigned long i = 0; i < samples.size(); ++i)
	{
		labeler.label_sequence(samples[i], pred);

		bool seen_first = false;
		num_samples += 1;
		for (unsigned long j = 0; j < pred.size(); ++j)
		{
			const unsigned long truth = labels[i][j];
			if (truth >= static_cast<unsigned long>(confusion_matrix.nr()))
			{
				// ignore labels the labeler doesn't know about.
				continue;
			}

			if (!seen_first && pred[j] == 1)
			{
				seen_first = true;
				if (truth == pred[j])
				{
					true_first += 1;
				}
			}

			confusion_matrix(truth, pred[j]) += 1;
		}
	}
	/*
	for (long i = 0; i < 5; ++i)
	{
		x_test.clear();
		y_test.clear();
		x_train.clear();
		y_train.clear();

		// load up the test samples
		for (long cnt = 0; cnt < num_in_test; ++cnt)
		{
			x_test.push_back(samples[next_test_idx]);
			y_test.push_back(labels[next_test_idx]);
			next_test_idx = (next_test_idx + 1)%samples.size();
		}

		// load up the training samples
		long next = next_test_idx;
		for (long cnt = 0; cnt < num_in_train; ++cnt)
		{
			x_train.push_back(samples[next]);
			y_train.push_back(labels[next]);
			next = (next + 1)%samples.size();
		}

		auto labeler = trainer.train(x_train,y_train);
		std::vector<unsigned long> pred;
		for (unsigned long i = 0; i < samples.size(); ++i)
		{
			labeler.label_sequence(samples[i], pred);

			bool seen_first = false;
			num_samples += 1;
			for (unsigned long j = 0; j < pred.size(); ++j)
			{
				const unsigned long truth = labels[i][j];
				if (truth >= static_cast<unsigned long>(confusion_matrix.nr()))
				{
					// ignore labels the labeler doesn't know about.
					continue;
				}

				if (!seen_first && pred[j] == 1)
				{
					seen_first = true;
					if (truth == pred[j])
					{
						true_first += 1;
					}
				}

				confusion_matrix(truth, pred[j]) += 1;
			}
		}

	} // for (long i = 0; i < folds; ++i)
	*/

	double precision = confusion_matrix(1, 1) / (confusion_matrix(1, 1) + confusion_matrix(0, 1));
	double recall = confusion_matrix(1, 1) / (confusion_matrix(1, 1) + confusion_matrix(1, 0));
	double f1 = 2 * precision * recall / (precision + recall);
	double first_accuracy = double(true_first) / double(num_samples);

	std::ofstream stats("dlib.stats", std::ios::app);
	std::ostream* streams[] = {&std::cout, &stats};
	for (std::ostream* stream : streams)
	{
		*stream << "\ncross-validation:" << std::endl;
		*stream << confusion_matrix;
		*stream << "precision = " << precision << std::endl;
		*stream << "recall = " << recall << std::endl;
		*stream << "f1 = " << f1 << std::endl;
		*stream << "first start accuracy = " << first_accuracy << std::endl;
		*stream << "label accuracy: "<< dlib::sum(dlib::diag(confusion_matrix))/dlib::sum(confusion_matrix) << std::endl;
	}


	// Learn to do sequence labeling from the dataset
//	dlib::sequence_labeler<feature_extractor<train_feature_index>> labeler = trainer.train(samples, labels);
//	dlib::serialize("weights.bin") << labeler.get_weights();
}
