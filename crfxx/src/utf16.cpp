#include "utf16.h"

#include <algorithm>
#include <cstring>
#include <cassert>

utf16_file::utf16_file(const char* filename)
	: input(filename, std::ios::binary)
	, buffer(2<<16, 0)
	, utf16_buffer(reinterpret_cast<const char16_t*>(buffer.data()))
	, read_offset(0)
	, write_offset(0)
{
	char c1, c2;
	input.get(c1);
	input.get(c2);
	if (!(c1 == '\xff' && c2 == '\xfe'))
	{
		input.unget();
		input.unget();
	}
}

bool utf16_file::getline(std::u16string& line)
{
	const char16_t* end = std::find(utf16_buffer + read_offset, utf16_buffer + write_offset, char16_t('\n'));
	while (!input.eof() && end == utf16_buffer + write_offset)
	{
		if (read_offset > 0)
		{
			memmove((void*)utf16_buffer, (void*)(utf16_buffer + read_offset), (write_offset - read_offset)*2);
			write_offset -= read_offset;
			read_offset = 0;
		}
		input.read(&buffer[write_offset*2], std::streamsize(buffer.size() - write_offset*2));
		assert(input.gcount() % 2 == 0);
		auto count = uint32_t(input.gcount()) / 2;
		end = std::find(utf16_buffer + write_offset, utf16_buffer + write_offset + count, char16_t('\n'));
		write_offset += count;
	}
	if (utf16_buffer + read_offset > end)
	{
		return false;
	}

	line = std::u16string(utf16_buffer + read_offset, end);

	read_offset += uint32_t(end - (utf16_buffer + read_offset)) + 1;
	return true;
}

