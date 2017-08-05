#include "encode.h"

#include <iostream>
#include <cassert>
#include <cstring>

train_feature_index_t load_feature_index(std::istream& in)
{
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
