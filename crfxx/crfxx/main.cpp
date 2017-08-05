#include <iostream>
#include <cassert>
#include <fstream>
#include <thread>
#include <cstdlib>
#include <algorithm>
#include <numeric>

#include <unordered_map>
#include <boost/program_options.hpp>

#include "lbfgs.h"
#include "utf16.h"
#include "encode.h"

namespace po = boost::program_options;

struct extract_feature_index_t : std::unordered_map<std::u16string, uint32_t>
{
	int get_feature_id(const std::u16string& key)
	{
		auto it = find(key);
		if (it != end())
		{
			it->second += 1;
			return -1;
		}
		else
		{
			(*this)[key] = 1;
			return -1;
		}
	}
};

struct train_feature_index_t : std::unordered_map<std::u16string, uint32_t>
{
	uint32_t num_features;
	train_feature_index_t()
		: num_features(0)
	{}

	int get_feature_id(const std::u16string& key) const
	{
		auto it = find(key);
		if (it != end())
		{
			return int(it->second);
		}
		else
		{
			return -1;
		}
	}
};

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

std::ostream& operator<<(std::ostream& out, const std::pair<sample_t, sample_features_t>& sample)
{
	char mb[5];
	assert(sample.first.size() == sample.second.size());
	for (auto i = 0U; i < sample.first.size(); ++i)
	{
		auto& s = sample.first[i];
		mb[wctomb(mb, s.symbol)] = 0;
		out << mb << '\t' << s.symbol_class << '\t' << s.tag << '\t';
		for (auto feature_id : sample.second[i])
		{
			out << feature_id << " ";
		}
		out << std::endl;
	}
	return out;
}

sample_t read_sample_and_extract_features(const std::u16string& line, extract_feature_index_t& feature_index)
{
	std::vector<symbol_t> symbols = read_sample(line);
	std::vector<std::vector<uint32_t>> unigram_features, bigram_features;
	make_features(symbols, feature_index, unigram_features, bigram_features);

	return symbols;
}

#define MIN_FEATURE_COUNT 1000
train_feature_index_t filter_features(const extract_feature_index_t& feature_index)
{
	train_feature_index_t filtered;
	uint32_t new_feature_id = 0;
	for(auto it = feature_index.begin(); it != feature_index.end(); ++it)
	{
		if (it->second >= MIN_FEATURE_COUNT)
		{
			filtered[it->first] = new_feature_id;
			new_feature_id += (it->first[0] == u'B' ? 2*NUM_LABELS : NUM_LABELS);
		}
	}
	filtered.num_features = new_feature_id;

	return filtered;
}

void dump_feature_index(train_feature_index_t& feature_index, const char* features_index_filename)
{
	std::ofstream out(features_index_filename);
	std::set<std::u16string> keys;
	for (auto& kv : feature_index)
	{
		out << kv.first << '\t' << std::to_string(kv.second) << std::endl;
//		keys.insert(kv.first);
		/*
		out.write((char*)kv.first.data(), kv.first.length()*sizeof (char16_t));
		out.write("\0\t", 2);

		const std::string id = std::to_string(kv.second);
		const std::u16string utf16_id(id.begin(), id.end());
		out.write((char*)utf16_id.data(), utf16_id.length()*sizeof (char16_t));
		out.write("\0\n", 2);
		*/
	}
	for (auto key : keys)
	{
		std::cout << key << std::endl;
	}
}

train_feature_index_t load_feature_index(const char* filename)
{
	std::ifstream in(filename);
	train_feature_index_t result;
	std::string line;
	uint32_t num_features = 0;
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
		num_features = std::max(num_features, feature_id + uint32_t(key[0] == u'B' ? NUM_LABELS * NUM_LABELS : NUM_LABELS));
	}

	result.num_features = num_features;
	return result;
}

std::tuple<train_feature_index_t, samples_t> read_features_and_samples(const char* corpus_filename)
{
	extract_feature_index_t feature_index;
	samples_t samples;

	utf16_file input(corpus_filename);
	std::u16string line;
	uint32_t line_no = 0;
	while(input.getline(line))
	{
		line_no += 1;
		if (line_no % 10000 == 0)
		{
			std::cout << corpus_filename << ": " << line_no << std::endl;
		}

		if (line.length() > 0)
		{
			samples.emplace_back(read_sample_and_extract_features(line, feature_index));
		}
	}
	samples.shrink_to_fit();
	std::cout << samples.size() << " samples" << std::endl;

	std::cout << feature_index.size() << " raw features" << std::endl;
	train_feature_index_t filtered = filter_features(feature_index);
	std::cout << filtered.num_features << " filtered and tagged features" << std::endl;
	dump_feature_index(filtered, "features.bin");

	return std::make_tuple(filtered, samples);
}

#define MINUS_LOG_EPSILON 50
inline double logsumexp(double x, double y, bool flg) {
	if (flg) return y;  // init mode
	const double vmin = std::min(x, y);
	const double vmax = std::max(x, y);
	if (vmax > vmin + MINUS_LOG_EPSILON) {
		return vmax;
	} else {
		return vmax + std::log(std::exp(vmin - vmax) + 1.0);
	}
}

void calcAlpha(std::vector<std::vector<Node>>& nodes, size_t x, size_t y)
{
	Node& n = nodes[x][y];
	n.alpha = 0.0;
	for (auto i = 0U; i < n.lpath.size(); ++i)
	{
		size_t prev_y = (i << 2) | (y >> 1);
		n.alpha = logsumexp(n.alpha, n.lpath[i] + nodes[x-1][prev_y].alpha, i == 0);
	}
	n.alpha += n.cost;
}

void calcBeta(std::vector<std::vector<Node>>& nodes, size_t x, size_t y)
{
	Node& n = nodes[x][y];
	n.beta = 0.0;
	for (auto i = 0U; i < n.rpath.size(); ++i)
	{
		size_t next_y = ((y << 1) & 0b111) | i;
		n.beta = logsumexp(n.beta, n.rpath[i] + nodes[x+1][next_y].beta, i == 0);
	}
	n.beta += n.cost;
}

std::ostream& operator<<(std::ostream& out, const std::vector<std::vector<Node>>& lattice)
{
	for (auto& nodes_i : lattice)
	{
		for (auto& node : nodes_i)
		{
			out << "Node{ alpha=" << node.alpha
				<< ", beta=" << node.beta
				<< ", cost=" << node.cost
				<< ", bestCost=" << node.bestCost
				<< ", prev=" << node.prev
				<< ", lpath={" << std::endl;
			for (auto i = 0U; i < node.lpath.size(); ++i)
			{
				out << '\t' << node.lpath[i] << std::endl;
			}
			out << "}, rpath={" << std::endl;
			for (auto i = 0U; i < node.rpath.size(); ++i)
			{
				out << '\t' << node.rpath[i] << std::endl;
			}
			out << "} }\t";
		}
		std::cout << std::endl;
	}
	return out;
}


struct TrainPredictor : Predictor<train_feature_index_t>
{
	double Z_;
	TrainPredictor(const train_feature_index_t& feature_index, const double* weights)
	{
		this->feature_index = &feature_index;
		this->weights = weights;
	}


	void forwardBackward(const sample_t& sample)
	{
		for (size_t i = 0; i < sample.size(); ++i) {
			for (size_t j = 0; j < NUM_LABELS; ++j) {
				calcAlpha(nodes, i, j);
			}
		}

		size_t i = sample.size() - 1;
		for (size_t j = 0; j < NUM_LABELS; ++j) {
			nodes[i][j].beta = nodes[i][j].cost;
		}
		while (i > 0)
		{
			--i;
			for (size_t j = 0; j < NUM_LABELS; ++j) {
				calcBeta(nodes, i, j);
			}
		}

		Z_ = 0.0;
		for (size_t j = 0; j < NUM_LABELS; ++j) {
			Z_ = logsumexp(Z_, nodes[0][j].beta, j == 0);
		}
	}

	void calcExpectation(size_t x, size_t y, std::vector<double>& expected)
	{
		const Node& node = nodes[x][y];
		const double c = std::exp(node.alpha + node.beta - node.cost - Z_);
		for (auto feature_id : unigram_features[x])
		{
			expected[feature_id + y] += c;
		}

		for (auto feature_id : bigram_features[x])
		{
			for (auto i = 0U; i < node.lpath.size(); ++i)
			{
				size_t prev_y = (i << 2) | (y >> 1);
				const double c = std::exp(nodes[x-1][prev_y].alpha + node.lpath[i] + node.beta - Z_);
				expected[feature_id + i*NUM_LABELS + y] += c;
			}
		}
	}


	double gradient(const sample_t& sample, std::vector<double>& expected)
	{
		if (sample.empty()) return 0.0;

		predict(*this, sample);

		forwardBackward(sample);

		/*
		std::cout << "forwardBackward:\n" << nodes;
		std::cout << "Z_ = " << Z_ << std::endl;
		*/

		double s = 0.0;

		for (size_t i = 0; i < sample.size(); ++i)
		{
			for (size_t j = 0; j < NUM_LABELS; ++j)
			{
				calcExpectation(i, j, expected);
			}
		}


		for (size_t i = 0; i < sample.size(); ++i)
		{
			auto y = sample[i].tag;
			for (auto feature_id : unigram_features[i])
			{
				--expected[feature_id + y];
			}
			s += nodes[i][y].cost;  // UNIGRAM cost

			if (i == 0) continue;

			size_t prev_y = sample[i - 1].tag >> 2;
			for (auto feature_id : bigram_features[i])
			{
				--expected[feature_id + prev_y * NUM_LABELS + y];
			}
			s += nodes[i][y].lpath[prev_y];
		}

/*
		std::cout << "s = " << s << std::endl;
		for (auto e : expected)
		{
			std::cout << e << " ";
		}
		std::cout << std::endl;
*/

		return Z_ - s ;
	}

	int eval(const sample_t& sample)
	{
		assert(sample.size() <= result_.size());
		int err = 0;
		for (size_t i = 0; i < sample.size(); ++i)
		{
			if (sample[i].tag != result_[i])
			{
				++err;
			}
		}
		return err;
	}
};

int main_test(int, char*[])
{
	std::locale::global(std::locale("en_US.UTF-8"));
	std::array<double, 8 + 8*8> weights = {{
		0.2277, 0.5562, -0.8271, 0.1732, 0.5766, 0.6755, 0.6696, 0.5387, -0.5272, -0.1661, 0.1718, 0.6204, -0.8499,
		-0.1671, 0.6117, 0.1135, 0.7622, -0.0028, 0.0451, 0.2367, -0.2144, 0.6808, 0.3066, -0.2559, -0.9013, -0.2359,
		-0.8393, 0.4544, 0.9062, 0.8766, -0.8139, 0.4308, -0.1595, -0.8759, -0.4251, -0.6401, -0.6595, 0.0779, 0.0961,
		-0.1691, -0.3485, 0.8815, -0.8278, -0.0943, -0.0695, -0.641, -0.2377, 0.064, -0.7586, -0.1627, -0.0313, 0.6813,
		0.2844, -0.3523, 0.1633, 0.748, -0.635, -0.3963, 0.8417, 0.8207, 0.1813, 0.3449, -0.4297, -0.9229, -0.1472,
		0.902, 0.7855, 0.7293, -0.0101, -0.926, 0.9603, -0.4158
	}};

	train_feature_index_t fake_features;
	fake_features[u"Uа毲"] = 0;
	fake_features[u"B"] = NUM_LABELS;

	TrainPredictor p(fake_features, weights.data());
	sample_t sample = {
		{ u'毲', 'a', false },
		{ u'浨', 'b', false },
		{ u'劽', 'c', false },
		{ u'泮', 'a', false },
		{ u'崶', 'b', true },
		{ u'矏', 'a', false },
		{ u'漐', 'a', false },
		{ u'翈', 'b', false },
		{ u'掏', 'b', false },
		{ u'爎', 'b', false },
	};
	std::vector<double> expected(weights.size(), 0.0);
	p.gradient(sample, expected);
	for (auto& v : p.result_)
	{
		std::cout << v << " ";
	}
	std::cout << std::endl;

	return 0;
}

struct CRFEncoderTask
{
	const samples_t* samples;
	size_t start_i;
	size_t thread_num;
	double obj;
	std::vector<double> expected;

	TrainPredictor predictor;

	int zeroone;
	int err;

	CRFEncoderTask(size_t start_i, size_t thread_num, const samples_t* samples, size_t num_weights,
			TrainPredictor&& predictor)
		: samples(samples)
		, start_i(start_i)
		, thread_num(thread_num)
		, expected(num_weights)
		, predictor(std::move(predictor))
	{}

	void run() {
		obj = 0.0;
		err = zeroone = 0;
		std::fill(expected.begin(), expected.end(), 0.0);
		for (size_t i = start_i; i < samples->size(); i += thread_num)
		{
			obj += predictor.gradient((*samples)[i], expected);
			int error_num = predictor.eval((*samples)[i]);
//			std::cout << "sample #" << i << ": " << error_num << std::endl;
			err += error_num;
			if (error_num)
			{
				++zeroone;
			}
		}
	}

};

typedef std::vector<double> weights_t;

bool runCRF(const samples_t& samples,
	const train_feature_index_t& feature_index,
	weights_t& weights,
	size_t maxitr,
	double C,
	double eta,
	uint32_t thread_num,
	bool orthant)
{
	double old_obj = 1e+37;
	int    converge = 0;
	LBFGS lbfgs;
	std::vector<CRFEncoderTask> tasks;

	thread_num = std::max(1U, thread_num);

	for (auto i = 0U; i < thread_num; ++i)
	{
		tasks.emplace_back(i, thread_num, &samples, weights.size(), TrainPredictor(feature_index, &weights[0]));
	}

	size_t num_labels = 0;
	for (auto& sample : samples)
	{
		num_labels += sample.size();
	}

	for (size_t itr = 0; itr < maxitr; ++itr)
	{
		std::vector<std::thread> threads;
		for (size_t i = 0; i < thread_num; ++i)
		{
			threads.emplace_back(&CRFEncoderTask::run, &tasks[i]);
		}

		for (auto& thread : threads)
		{
			thread.join();
		}

		for (size_t i = 1; i < thread_num; ++i)
		{
			tasks[0].obj += tasks[i].obj;
			tasks[0].err += tasks[i].err;
			tasks[0].zeroone += tasks[i].zeroone;
			for (size_t k = 0; k < weights.size(); ++k)
			{
				tasks[0].expected[k] += tasks[i].expected[k];
			}
		}

		size_t num_nonzero = 0;
		if (orthant)
		{   // L1
			for (size_t k = 0; k < weights.size(); ++k)
			{
				tasks[0].obj += std::abs(weights[k] / C);
				if (weights[k] != 0.0)
				{
					++num_nonzero;
				}
			}
		}
		else
		{
			num_nonzero = weights.size();
			for (size_t k = 0; k < weights.size(); ++k)
			{
				tasks[0].obj += (weights[k] * weights[k] /(2.0 * C));
				tasks[0].expected[k] += weights[k] / C;
			}
		}

		double diff = (itr == 0 ? 1.0 : std::abs(old_obj - tasks[0].obj)/old_obj);
		std::cout << "iter="  << itr
				  << " per-tag error=" << double(tasks[0].err) / num_labels
				  << " per-sentence error=" << double(tasks[0].zeroone) / samples.size()
				  << " nonzero weights=" << num_nonzero
				  << " obj=" << tasks[0].obj
				  << " diff="  << diff << '%' << std::endl;
		old_obj = tasks[0].obj;

		if (diff < eta)
		{
			converge++;
		}
		else
		{
			converge = 0;
		}

		if (itr > maxitr || converge == 3)
		{
			break;  // 3 is ad-hoc
		}

		if (lbfgs.optimize(weights.size(),
						   &weights[0],
						   tasks[0].obj,
						   &tasks[0].expected[0], orthant, C) <= 0) {
			return false;
		}
	}

	return true;
}

weights_t train(const samples_t& samples, const train_feature_index_t& feature_index)
{
	weights_t weights(feature_index.num_features);
	std::fill(weights.begin(), weights.end(), 0.0);
	runCRF(samples, feature_index, weights, 100000, 1.0, 0.0001, 8, true);

	return weights;
}

void test(const weights_t& weights, const train_feature_index_t& feature_index, const char* filename)
{
	auto input = utf16_file(filename);
	double tp = 0.0, tn = 0.0, fp = 0.0, fn = 0.0, true_first = 0.0, true_last = 0.0, num_samples = 0.0;
	TrainPredictor predictor(feature_index, weights.data());
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
			const uint32_t predicted = prediction[i] >> 2;
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

void dump_weights(const weights_t& weights, const char* filename)
{
	std::ofstream out(filename, std::ios::binary);
	for (auto w : weights)
	{
		float float_weight = float(w);
		out.write((char*)&float_weight, sizeof(float_weight));
	}
	out.flush();
}

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

void train(char* argv[])
{
	train_feature_index_t feature_index;
	samples_t samples;
	std::tie(feature_index, samples) = read_features_and_samples(argv[1]);
	auto weights = train(samples, feature_index);
	std::cout << feature_index.num_features << " " << weights.size() << std::endl;
	assert(weights.size() == feature_index.num_features);
	test(weights, feature_index, argv[1]);
	test(weights, feature_index, argv[2]);
	dump_weights(weights, "model.bin");
}

void test(char* argv[])
{
	train_feature_index_t feature_index = load_feature_index(argv[1]);
	weights_t weights = load_weights(argv[2]);
	std::cout << feature_index.num_features << " " << weights.size() << std::endl;
	assert(weights.size() == feature_index.num_features);
	test(weights, feature_index, argv[3]);
}

int main(int argc, char *argv[])
{
	std::locale::global(std::locale("en_US.UTF-8"));
	std::cout.setf(std::ios::fixed, std::ios::floatfield);
	std::cout.precision(5);

	std::cout << argv[1] << " " << argv[2] << std::endl;

	if (argc == 4) {
		test(argv);
	} else if (argc == 3) {
		train(argv);
	} else {
		std::cerr << "2 or 3 arguments" << std::endl;
	}

	return 0;
}
