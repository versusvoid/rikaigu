#pragma once
#include "train_feature_index.h"

#include <algorithm>
#include <fstream>
#include <vector>
#include <cassert>

train_feature_index::train_feature_index(std::unordered_map<uint64_t, size_t> &features,
	const std::string& filename)
{
	std::vector<uint64_t> sorted_features;
	for (auto& kv : features)
	{
		if (kv.second >= MIN_FEATURE_COUNT)
		{
			sorted_features.push_back(kv.first);
		}
	}
	features.clear();
	std::sort(sorted_features.begin(), sorted_features.end());

	std::ofstream of(filename);
	for (auto i = 0U; i < sorted_features.size(); ++i)
	{
		uint64_t key = sorted_features[i];
		uint32_t upper_half = uint32_t(key >> 32);
		// Little-endian check
		assert(*(char*)&upper_half == *((char*)&key + 4));
		uint32_t lower_half = uint32_t(key & 0xffffffff);
		of.write(reinterpret_cast<char*>(&upper_half), 4);
		of.write(reinterpret_cast<char*>(&lower_half), 4);
		this->features[key] = i;
	}
}

unsigned long train_feature_index::num_features() const
{
	return  features.size() + 1;
}

unsigned long train_feature_index::get(const std::pair<uint32_t, uint32_t> &key) const
{
	uint64_t full_key = (uint64_t(key.first) << 32) | key.second;
	auto it = this->features.find(full_key);
	if (it == this->features.end())
	{
		return this->features.size();
	}
	else
	{
		return it->second;
	}
}
