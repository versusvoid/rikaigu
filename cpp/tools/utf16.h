#pragma once

#include <vector>
#include <fstream>
#include <cstdint>

struct utf16_file
{
	std::ifstream input;
	std::vector<char> buffer;
	const char16_t* utf16_buffer;
	uint32_t read_offset;
	uint32_t write_offset;

	utf16_file(const char* filename);

	bool getline(std::u16string& line);
};
