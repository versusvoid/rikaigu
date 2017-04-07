#ifndef TRAIN_FEATURE_INDEX_H
#define TRAIN_FEATURE_INDEX_H

#include "filter_feature_index.h"

struct train_feature_index
{
	train_feature_index(std::unordered_map<uint64_t, size_t>& features,
		const std::string& filename);

	unsigned long num_features() const;

	unsigned long get(const std::pair<uint32_t, uint32_t>& key) const;

	std::unordered_map<uint64_t, unsigned long> features;

	void dump(const std::string& filename);
};

#ifdef NO_MAKEFILE
#include "train_feature_index.cpp"
#endif

#endif // TRAIN_FEATURE_INDEX_H
