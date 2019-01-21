#include "word_types.h"

#include <algorithm>
#include <iostream>

std::map<std::string, uint32_t> INFLECTION_TYPES;
uint32_t ANY_TYPE = 0;
static uint32_t NEXT_TYPE = 1;
uint32_t inflection_type_to_int(const char* start, const char* end)
{
	uint32_t int_type = 0;
	while (start < end)
	{
		const char* p = std::find(start, end, '|');
		std::string type(start, p);
		auto it = INFLECTION_TYPES.find(type);
		if (it == INFLECTION_TYPES.end()) {
			it = INFLECTION_TYPES.insert(std::make_pair(type, NEXT_TYPE)).first;
			ANY_TYPE |= NEXT_TYPE;
			NEXT_TYPE <<= 1;
		}
		int_type |= it->second;
		start = p + 1;
	}
	return int_type;
}

uint32_t inflection_type_to_int(const std::vector<std::string>& types)
{
	uint32_t type = 0;
	for (auto& type_str : types)
	{
		auto it = INFLECTION_TYPES.find(type_str);
		if (it != INFLECTION_TYPES.end())
		{
			type |= it->second;
		}
	}
	return type;
}
