#pragma once

#include <unordered_map>

#define MIN_FEATURE_COUNT 1000

struct filter_feature_index
{
	filter_feature_index();

	unsigned long get(const std::pair<uint32_t, uint32_t>& key) const;

	mutable std::unordered_map<uint64_t, size_t> features;
};

#ifdef NO_MAKEFILE
#include "filter_feature_index.cpp"
#endif

