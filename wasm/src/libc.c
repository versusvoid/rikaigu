#include "libc.h"

#include <stdint.h>
#include <stdarg.h>
#include <assert.h>

#include "imports.h"

void* memcpy(void *dest, const void *src, size_t n)
{
	const size_t full_8_bytes_length = n / 8;
	uint64_t* to = (uint64_t*)dest;
	uint64_t* const end = to + full_8_bytes_length;
	const uint64_t* from = (const uint64_t*)src;
	while (to != end)
	{
		*to = *from;
		to += 1;
		from += 1;
	}
	const size_t additional_bytes = n - full_8_bytes_length * 8;
	uint8_t* to_bytes = (uint8_t*)to;
	const uint8_t* from_bytes = (const uint8_t*)from;
	uint8_t* const end_bytes = (uint8_t*)end + additional_bytes;
	while (to_bytes != end_bytes)
	{
		*to_bytes = *from_bytes;
		to_bytes += 1;
		from_bytes += 1;
	}

	return dest;
}

void* memcpy_backward(void *dest, const void *src, size_t n)
{
	const size_t full_8_bytes_length = n / 8;
	uint64_t* to = (uint64_t*)(dest + n) - 1;
	uint64_t* const begin = dest;
	const uint64_t* from = (const uint64_t*)(src + n) - 1;
	while (to >= begin)
	{
		*to = *from;
		to -= 1;
		from -= 1;
	}

	const size_t additional_bytes = n - full_8_bytes_length * 8;
	uint8_t* to_bytes = (uint8_t*)dest + additional_bytes - 1;
	uint8_t* const begin_bytes = (uint8_t*)dest;
	const uint8_t* from_bytes = (const uint8_t*)src + additional_bytes - 1;
	while (to_bytes >= begin_bytes)
	{
		*to_bytes = *from_bytes;
		to_bytes -= 1;
		from_bytes -= 1;
	}

	return dest;
}

void* memmove(void* dest, const void* src, size_t n)
{
	if (dest < src)
	{
		return memcpy(dest, src, n);
	}
	else
	{
		return memcpy_backward(dest, src, n);
	}
}

void memzero(void* dest, size_t n)
{
	const size_t full_8_bytes_length = n / 8;
	uint64_t* cur = dest;
	uint64_t* const end = (uint64_t*)dest + full_8_bytes_length;
	while (cur < end)
	{
		*cur = 0;
		cur += 1;
	}

	const size_t additional_bytes = n - full_8_bytes_length * 8;
	uint8_t* cur_bytes = dest + n - additional_bytes;
	uint8_t* const end_bytes = dest + n;
	while (cur_bytes < end_bytes)
	{
		*cur_bytes = 0;
		cur_bytes += 1;
	}
}

void* binary_locate(
	const void *key, const void *array,
	size_t num_elements, size_t element_size,
	int (*compar)(const void*, const void*), bool* found
	)
{
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wcast-qual"

	assert(found != NULL);
	*found = false;

	size_t low = 0;
	size_t high = num_elements;
	while (low < high)
	{
		const size_t mid = (low + high) / 2;
		int order = compar(key, array + mid * element_size);
		if (order > 0)
		{
			low = mid + 1;
		}
		else if (order < 0)
		{
			high = mid;
		}
		else
		{
			*found = true;
			return (void*)(array + mid * element_size);
		}
	}
	return (void*)(array + low * element_size);
#pragma clang diagnostic pop
}

bool binary_locate_bounds(
	const void *key, const void *array,
	size_t num_elements, size_t element_size,
	int (*compar)(const void*, const void*),
	size_t* lower, size_t* upper
	)
{
	size_t low = 0;
	size_t high = num_elements;
	size_t match = -1;
	while (low < high)
	{
		const size_t mid = (low + high) / 2;
		int order = compar(key, array + mid * element_size);
		if (order > 0)
		{
			low = mid + 1;
		}
		else if (order < 0)
		{
			high = mid;
		}
		else
		{
			match = mid;
			break;
		}
	}
	if (low == high)
	{
		*lower = low;
		*upper = high;
		return false;
	}

	const size_t match_high = high;
	high = match;
	while (low < high)
	{
		const size_t mid = (low + high) / 2;
		int order = compar(key, array + mid * element_size);
		if (order > 0)
		{
			low = mid + 1;
		}
		else
		{
			high = mid;
		}
	}
	*lower = low;

	high = match_high;
	low = match;
	while (low < high)
	{
		const size_t mid = (low + high) / 2;
		int order = compar(key, array + mid * element_size);
		if (order < 0)
		{
			high = mid;
		}
		else
		{
			low = mid + 1;
		}
	}
	*upper = high;

	return true;
}

int consolef(const char* format, ...)
{
	char buf[128];

	va_list args;
	va_start(args, format);

	const char* in = format;
	char* out = buf;
	while (*in != 0 && out < buf + sizeof(buf) - 1)
	{
		if (*in != '%')
		{
			*out = *in;
			in += 1;
			out += 1;
			continue;
		}

		char spec = *(in + 1);
		if (spec != 'u')
		{
			take_a_trip("unknown consolef specifier");
		}

		in += 2;

		uint32_t v = va_arg(args, uint32_t);
		int digits = 1;
		for (uint32_t v2 = v / 10; v2 != 0; v2 /= 10)
		{
			digits += 1;
		}
		if (out + digits >= buf + sizeof(buf))
		{
			take_a_trip("small buffer");
		}

		for (int i = digits; i > 0; --i)
		{
			*(out + i - 1) = '0' + (v % 10);
			v /= 10;
		}
		out += digits;
	}
	va_end(args);

	*out = '\0';
	print(buf);

	return (int)(out - buf);
}
