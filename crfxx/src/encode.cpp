#include "encode.h"

sample_t read_sample(const std::u16string& line)
{
	std::vector<symbol_t> result;

	uint8_t tag = 1; // S
	for (auto& character : line)
	{
		if (character == char16_t(' '))
		{
			tag = 1;
			continue;
		}

		result.push_back({character, 'm', tag});
		tag = 0;
		symbol_t& symbol = result.back();

		if (character >= 0x4e00 && character <= 0x9fa5) {
			symbol.symbol_class = 'K';
		} else if (character >= 0x3040 && character <= 0x309f) {
			symbol.symbol_class = 'h';
		} else if (character >= 0x30a1 && character <= 0x30fe) {
			symbol.symbol_class = 'k';
		}
	}

	for (auto i = 0U; i < result.size(); ++i)
	{
		result[i].tag <<= 2;
		result[i].tag |= (i + 1 < result.size() ? result[i + 1].tag << 1 : 0);
		result[i].tag |= (i + 2 < result.size() ? result[i + 2].tag : 0);
	}

	result.shrink_to_fit();

	return result;
}
