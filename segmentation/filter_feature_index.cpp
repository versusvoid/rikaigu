#pragma once

#include "filter_feature_index.h"
#include "feature_extractor.hpp"

filter_feature_index::filter_feature_index()
{

	for (auto label1 : {0U, 1U})
	{
		for(auto label2 : {0U, 1U})
		{
			for (auto class1 : {'K', 'k', 'h', 'm'})
			{
				for (auto class2 : {'K', 'k', 'h', 'm'})
				{
					auto key = bigram(label1, class1, label2, class2);
					features[(uint64_t(key.first) << 32) | key.second] = MIN_FEATURE_COUNT;
				}
			}
		}
	}
}

unsigned long filter_feature_index::get(const std::pair<uint32_t, uint32_t>& key) const
{
	features[(uint64_t(key.first) << 32) | key.second] += 1;
	return 0;
}
