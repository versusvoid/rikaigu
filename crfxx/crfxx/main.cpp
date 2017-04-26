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

namespace po = boost::program_options;

struct symbol_t
{
	char16_t symbol;
	char symbol_class;
	bool start;
};

typedef std::vector<symbol_t> sample_t;
typedef std::vector<std::vector<uint32_t>> sample_features_t;
typedef std::vector<sample_t> samples_t;
struct feature_index_t : std::unordered_map<std::u16string, uint32_t>
{
	uint32_t num_features;
	feature_index_t()
		: num_features(0)
	{}
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
		out << mb << '\t' << s.symbol_class << '\t' << (s.start ? "S(1)" : "M(0)") << '\t';
		for (auto feature_id : sample.second[i])
		{
			out << feature_id << " ";
		}
		out << std::endl;
	}
	return out;
}


#define NUM_LABELS 2
#define MIN_FEATURE_COUNT 1000

sample_t read_sample(const std::u16string& line)
{
	std::vector<symbol_t> result;

	for (auto& character : line)
	{
		if (character == char16_t(' '))
		{
			result.back().start = true;
			continue;
		}

		result.push_back({character, 'm', false});
		symbol_t& symbol = result.back();

		if (character >= 0x4e00 && character <= 0x9fa5) {
			symbol.symbol_class = 'K';
		} else if (character >= 0x3040 && character <= 0x309f) {
			symbol.symbol_class = 'h';
		} else if (character >= 0x30a1 && character <= 0x30fe) {
			symbol.symbol_class = 'k';
		}
	}

	result.shrink_to_fit();

	return result;
}

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

std::vector<std::vector<uint32_t>> make_features(const sample_t& sample,
	const std::function<int(const std::u16string&)>& get_feature_id)
{
	std::vector<std::vector<uint32_t>> result;
	for (auto i = 0; size_t(i) < sample.size(); ++i)
	{
		std::vector<uint32_t> features;

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
					/* * /
					if (index > 0)
					{
						number = '+' + number;
					}
					symbol_feature.append(u"_B");
					symbol_feature.append(number.begin(), number.end());

					symbol_class_feature.append(u"_B");
					symbol_class_feature.append(number.begin(), number.end());
					/ * */
					symbol_feature.append(u"S[");
					symbol_feature.append(number.begin(), number.end());
					symbol_feature.append(u"]");

					symbol_class_feature.append(u"C[");
					symbol_class_feature.append(number.begin(), number.end());
					symbol_class_feature.append(u"]");
					/* */
				}
				else
				{
					symbol_feature += sample[index].symbol;
					symbol_class_feature += char16_t(sample[index].symbol_class);
				}

				for (const std::u16string* f : {&symbol_feature, &symbol_class_feature})
				{
					int feature_id = get_feature_id(std::u16string(u"U") + key + *f);
					if (feature_id >= 0)
					{
						features.push_back(uint32_t(feature_id));
					}
					++key;
				}
			}
		}
		result.emplace_back(features);
	}
	return result;
}

sample_t read_sample_and_extract_features(const std::u16string& line, feature_index_t& feature_index)
{
	std::vector<symbol_t> symbols = read_sample(line);

	make_features(symbols, std::bind(record_feature, std::ref(feature_index), std::placeholders::_1));

	return symbols;
}

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
			new_feature_id += NUM_LABELS;
			++it;
		}
	}
	feature_index[u"B"] = new_feature_id;
	new_feature_id += NUM_LABELS*NUM_LABELS;
	feature_index.num_features = new_feature_id;
}

void dump_feature_index(feature_index_t& feature_index, const char* features_index_filename)
{
	std::ofstream out(features_index_filename, std::ios::binary);
	std::set<std::u16string> keys;
	for (auto& kv : feature_index)
	{
		out << kv.first << '\t' << kv.second << std::endl;
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

std::tuple<feature_index_t, samples_t> read_features_and_samples(const char* corpus_filename)
{
	feature_index_t feature_index;
	samples_t samples;

	std::ifstream corpus(corpus_filename, std::ios::binary);

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
	filter_features(feature_index);
	std::cout << feature_index.num_features << " filtered and tagged features" << std::endl;
	dump_feature_index(feature_index, "features.bin");

	return std::make_tuple(feature_index, samples);
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

struct Path;

struct Node {
//	unsigned int         x;
//	unsigned short int   y;
	double               alpha;
	double               beta;
	double               cost;
	double               bestCost;
	ssize_t prev;
	std::vector<std::shared_ptr<Path>>  lpath;
	std::vector<std::shared_ptr<Path>>  rpath;

	void calcAlpha();
	void calcBeta();
	void calcExpectation(double *expected, double, size_t) const;

	Node()
		: alpha(0.0)
		, beta(0.0)
		, cost(0.0)
		, bestCost(0.0)
		, prev(-1)
	{}
};

struct Path {
  Node      *lnode;
  Node      *rnode;
  double     cost;

  Path(Node *lnode, Node *rnode)
	: lnode(lnode)
	, rnode(rnode)
	, cost(0.0)
  {

  }

  // for CRF
  void calcExpectation(double *expected, double, size_t) const;
  void add(Node *_lnode, Node *_rnode);
};

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

void Node::calcAlpha() {
	alpha = 0.0;
	for (auto it = lpath.begin(); it != lpath.end(); ++it) {
		alpha = logsumexp(alpha,
						  (*it)->cost +(*it)->lnode->alpha,
						  (it == lpath.begin()));
	}
	alpha += cost;
}

void Node::calcBeta() {
	beta = 0.0;
	for (auto it = rpath.begin(); it != rpath.end(); ++it) {
		beta = logsumexp(beta,
						 (*it)->cost +(*it)->rnode->beta,
						 (it == rpath.begin()));
	}
	beta += cost;
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
				<< ", lpath={";
			for (auto i = 0U; i < node.lpath.size(); ++i)
			{
				if (i > 0)
				{
					out << ',';
				}
				out << node.lpath[i]->cost;
			}
			out << "}, rpath={";
			for (auto i = 0U; i < node.rpath.size(); ++i)
			{
				if (i > 0)
				{
					out << ',';
				}
				out << node.rpath[i]->cost;
			}
			out << "} }\t";
		}
		std::cout << std::endl;
	}
	return out;
}

#define COST_FACTOR 1.0

struct Predictor
{
	std::function<int(const std::u16string&)> get_feature_id;
	const double* weights;

	std::vector<std::vector<uint32_t>> features;
	std::vector<std::vector<Node>> nodes;
	double Z_;
	std::vector<uint32_t> result_;
	uint32_t b_feature_id;

	Predictor(const std::function<int(const std::u16string&)>& get_feature_id, const double* weights)
		: get_feature_id(get_feature_id)
		, weights(weights)
		, b_feature_id(uint32_t(get_feature_id(u"B")))
	{}

	void calcCost(size_t x, size_t y)
	{
		for (auto feature_id : features[x])
		{
			nodes[x][y].cost += COST_FACTOR*weights[feature_id + y];
		}

		if (x > 0)
		{
			for (auto i = 0U; i < NUM_LABELS; ++i)
			{
				nodes[x][y].lpath[i]->cost += COST_FACTOR*weights[b_feature_id + i*NUM_LABELS + y];
			}
		}
	}

	void buildLattice(const sample_t& sample)
	{
		if (nodes.size() < sample.size())
		{
			nodes.resize(sample.size());
		}

		for (size_t cur = 0; cur < sample.size(); ++cur)
		{
			nodes[cur].clear();
			for (size_t i = 0; i < NUM_LABELS; ++i)
			{
				nodes[cur].emplace_back();
			}
		}

		for (size_t cur = 1; cur < sample.size(); ++cur)
		{
			for (size_t j = 0; j < NUM_LABELS; ++j)
			{
				for (size_t i = 0; i < NUM_LABELS; ++i)
				{
					auto p = std::make_shared<Path>(&nodes[cur-1][j], &nodes[cur][i]);
					nodes[cur-1][j].rpath.push_back(p);
					nodes[cur][i].lpath.push_back(p);
				}
			}
		}

		for (size_t i = 0; i < sample.size(); ++i)
		{
			for (size_t j = 0; j < NUM_LABELS; ++j)
			{
				calcCost(i, j);
			}
		}
	}

	void forwardBackward(const sample_t& sample)
	{
		for (size_t i = 0; i < sample.size(); ++i) {
			for (size_t j = 0; j < NUM_LABELS; ++j) {
				nodes[i][j].calcAlpha();
			}
		}

		for (int i = static_cast<int>(sample.size() - 1); i >= 0;  --i) {
			for (size_t j = 0; j < NUM_LABELS; ++j) {
				nodes[i][j].calcBeta();
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
		for (auto feature_id : features[x])
		{
			expected[feature_id + y] += c;
		}

		if (x == 0) return;

		for (auto i = 0U; i < NUM_LABELS; ++i)
		{
			auto& p = node.lpath[i];
			const double c = std::exp(p->lnode->alpha + p->cost + p->rnode->beta - Z_);
			expected[b_feature_id + i*NUM_LABELS + y] += c;
		}
	}

	void viterbi(const sample_t& sample)
	{
		for (size_t i = 0;   i < sample.size(); ++i)
		{
			for (size_t j = 0; j < NUM_LABELS; ++j) {
				double bestc = -1e37;
				ssize_t best = -1;
				auto& lpath = nodes[i][j].lpath;
				for (auto k = 0U; k < lpath.size(); ++k)
				{
					auto& p = lpath[k];
					double cost = p->lnode->bestCost + p->cost +
							nodes[i][j].cost;
					if (cost > bestc) {
						bestc = cost;
						best  = ssize_t(k);
					}
				}
				nodes[i][j].prev     = best;
				nodes[i][j].bestCost = (best != -1) ? bestc : nodes[i][j].cost;
			}
		}

		double bestc = -1e37;
		ssize_t y = -1;
		size_t s = sample.size() - 1;
		for (size_t j = 0; j < NUM_LABELS; ++j)
		{
			if (bestc < nodes[s][j].bestCost)
			{
				y  = ssize_t(j);
				bestc = nodes[s][j].bestCost;
			}
		}

		result_.resize(sample.size(), 0);
		for (ssize_t i = ssize_t(result_.size() - 1); i >= 0; --i)
		{
			result_[i] = uint32_t(y);
			y = nodes[i][y].prev;
		}
	}

	double gradient(const sample_t& sample, std::vector<double>& expected)
	{
		if (sample.empty()) return 0.0;

		features = make_features(sample, get_feature_id);

//		std::cout << "sample:\n" << std::make_pair(sample, features) << std::endl;

		buildLattice(sample);

//		std::cout << "lattice:\n" << nodes;

		forwardBackward(sample);

//		std::cout << "forwardBackward:\n" << nodes;
//		std::cout << "Z_ = " << Z_ << std::endl;

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
			auto y = uint32_t(sample[i].start);
			for (auto feature_id : features[i])
			{
				--expected[feature_id + y];
			}
			s += nodes[i][y].cost;  // UNIGRAM cost

			if (i == 0) continue;

			auto prev_y = uint32_t(sample[i - 1].start);
			--expected[b_feature_id + prev_y * NUM_LABELS + y];
			s += nodes[i][y].lpath[prev_y]->cost;
		}

/*
		std::cout << "s = " << s << std::endl;
		for (auto e : expected)
		{
			std::cout << e << " ";
		}
		std::cout << std::endl;
*/

		viterbi(sample);

/*
		std::cout << "viterbi:\n" << nodes;
		for (auto y : result_)
		{
			std::cout << y << " ";
		}
		std::cout << std::endl;
*/

		return Z_ - s ;
	}

	std::vector<uint32_t> predict(const sample_t& sample)
	{
		features = make_features(sample, get_feature_id);
		buildLattice(sample);
		viterbi(sample);
		return result_;
	}

	int eval(const sample_t& sample, bool& error_first)
	{
		assert(sample.size() == result_.size());
		int err = 0;
		bool first = true;
		for (size_t i = 0; i < sample.size(); ++i)
		{
			if (uint32_t(sample[i].start) != result_[i])
			{
				if (first)
				{
					error_first = true;
				}
				++err;
			}
			if (sample[i].start || result_[i] == 1)
			{
				first = false;
			}
		}
		return err;
	}
};

#define NUM_FAKE_FEATURES 20
std::array<std::u16string, NUM_FAKE_FEATURES> fake_features = {
	u"Utc", u"Utc",
	u"Us掏", u"Us掏",
	u"Uc矏漐", u"Uc矏漐",
	u"Uq矏漐翈", u"Uq矏漐翈",

	u"B", u"B", u"B", u"B",

	u"Uo漐翈", u"Uo漐翈",
	u"UfC[-1]ab", u"UfC[-1]ab",
	u"Uo劽泮", u"Uo劽泮",
	u"Uvca", u"Uvca",
};
int get_test_features(const std::u16string& key)
{
	auto it = std::find(fake_features.begin(), fake_features.end(), key);
	if (it == fake_features.end())
	{
		return -1;
	}
	else
	{
		return it - fake_features.begin();
	}
}

int main_test(int, char*[])
{
	std::locale::global(std::locale("en_US.UTF-8"));
	std::array<double, NUM_FAKE_FEATURES> weights = {
		0.9468,  0.8978, -0.3843, -0.0098, 0.7339, -0.2137, -0.0205, -0.2711, -0.0954,  0.5965,
		-0.001, -0.6337, -0.9543, -0.3915, 0.7780,  0.2471,  0.1481, -0.0541,  0.6157, -0.4334
	};
	Predictor p(get_test_features, weights.data());
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
	std::vector<double> expected(NUM_FAKE_FEATURES, 0.0);
	p.gradient(sample, expected);

	return 0;
}

struct CRFEncoderTask
{
	const samples_t* samples;
	size_t start_i;
	size_t thread_num;
	int zeroone;
	int err;
	int error_first;
	double obj;
	std::vector<double> expected;

	Predictor predictor;

	CRFEncoderTask(size_t start_i, size_t thread_num, const samples_t* samples, size_t num_weights, Predictor&& predictor)
		: samples(samples)
		, start_i(start_i)
		, thread_num(thread_num)
		, expected(num_weights)
		, predictor(std::move(predictor))
	{}

	void run() {
		obj = 0.0;
		err = zeroone = error_first = 0;
		std::fill(expected.begin(), expected.end(), 0.0);
		for (size_t i = start_i; i < samples->size(); i += thread_num)
		{
			obj += predictor.gradient((*samples)[i], expected);
			bool error_first = false;
			int error_num = predictor.eval((*samples)[i], error_first);
			if (error_first)
			{
				this->error_first += 1;
			}
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
	const feature_index_t& feature_index,
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
		tasks.emplace_back(i, thread_num, &samples, weights.size(),
			Predictor(std::bind(get_feature_id, std::ref(feature_index), std::placeholders::_1), &weights[0]));
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
				  << " sentence with first start error=" << double(tasks[0].error_first) / samples.size()
				  << " per-sentence error=" << double(tasks[0].zeroone) / samples.size()
				  << " nonzero weights=" << num_nonzero
				  << " obj=" << tasks[0].obj
				  << " diff="  << diff << std::endl;
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

weights_t train(const samples_t& samples, const feature_index_t& feature_index)
{
	weights_t weights(feature_index.num_features);
	std::fill(weights.begin(), weights.end(), 0.0);
	runCRF(samples, feature_index, weights, 100000, 1.0, 0.0001, 8, true);

	return weights;
}

void test(const weights_t& weights, const feature_index_t& feature_index, const char* filename)
{
	auto input = utf16_file(filename);
	double tp = 0.0, tn = 0.0, fp = 0.0, fn = 0.0, true_first = 0.0, num_samples = 0.0;
	Predictor predictor(std::bind(::get_feature_id, std::ref(feature_index), std::placeholders::_1), weights.data());
	std::u16string line;
	uint32_t line_no = 0;
	while(input.getline(line))
	{
		if (line.empty()) continue;

		const auto sample = read_sample(line);
		const std::vector<uint32_t> prediction = predictor.predict(sample);
		assert(prediction.size() == sample.size());
		bool first_start = true;
		for (auto i = 0U; i < prediction.size(); ++i)
		{
			const uint32_t gold = uint32_t(sample[i].start);
			if (gold == 0 and prediction[i] == 0)
			{
				tn += 1;
			}
			else if (gold == 1 and prediction[i] == 1)
			{
				tp += 1;
				true_first += (first_start ? 1 : 0);
				first_start = false;
			}
			else if (gold == 0 and prediction[i] == 1)
			{
				fp += 1;
				first_start = false;
			}
			else
			{
				fn += 1;
				first_start = false;
			}
		}

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
	double f1 = 2 * precision * recall / (precision + recall);
	std::cout << filename << ":" << std::endl;
	std::cout << tp << "\t\t" << fp << std::endl;
	std::cout << fn << "\t\t" << tn << std::endl;
	std::cout
		<< "tfirst = " << true_first_ratio
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
}

int main(int argc, char *argv[])
{
	assert(argc == 3);
	std::locale::global(std::locale("en_US.UTF-8"));
	std::cout.setf(std::ios::fixed, std::ios::floatfield);
	std::cout.precision(5);

	std::cout << argv[1] << " " << argv[2] << std::endl;

	feature_index_t feature_index;
	samples_t samples;
	std::tie(feature_index, samples) = read_features_and_samples(argv[1]);
	auto weights = train(samples, feature_index);
	test(weights, feature_index, argv[1]);
	test(weights, feature_index, argv[2]);
	dump_weights(weights, "model.bin");

	return 0;
}
