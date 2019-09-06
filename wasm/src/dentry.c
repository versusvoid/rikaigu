#include "dentry.h"

#include <stdbool.h>
#include <assert.h>

#include "state.h"
#include "libc.h"
#include "utf.h"
#include "../generated/config.h"

dentry_t* dentry_new()
{
	buffer_t* dentry_buffer = state_get_dentry_buffer();
	dentry_t* ptr = (dentry_t*)buffer_allocate(dentry_buffer, sizeof(dentry_t));
	memzero(ptr, sizeof(dentry_t));
	return ptr;
}

uint32_t parse_base62_uint(const char* s, const char* const end)
{
	uint32_t res = 0;
	for (; s < end; ++s)
	{
		char c = *s;
		res *= 62;
		if (c >= '0' && c <= '9')
		{
			res += c - '0';
		}
		else if (c >= 'a' && c <= 'z')
		{
			res += c - 'a';
		}
		else
		{
			res += c - 'A';
		}
	}
	return res;
}

dentry_t* dentry_make(const char* raw, size_t length, bool is_name)
{
	const char* parts_start[] = {raw, NULL, NULL, NULL};
	size_t num_parts = 1;
	while (num_parts < 4)
	{
		const char* next = find_char(parts_start[num_parts - 1], raw + length, '\t');
		if (next == raw + length)
		{
			break;
		}
		parts_start[num_parts] = next + 1;
		num_parts += 1;
	}

	dentry_t* res = dentry_new();
	if (!is_name)
	{
		assert(num_parts >= 3);
		res->entry_id = MIN_ENTRY_ID + parse_base62_uint(parts_start[num_parts - 1], raw + length);
		res->definition_end = parts_start[num_parts - 1] - 1;
		num_parts -= 1;
	}
	else
	{
		res->definition_end = raw + length;
	}

	assert(num_parts == 2 || num_parts == 3);
	if (num_parts == 3)
	{
		res->kanjis_start = parts_start[0];
		res->readings_start = parts_start[1];
		res->definition_start = parts_start[2];
	}
	else if (num_parts == 2)
	{
		res->readings_start = parts_start[0];
		res->definition_start = parts_start[1];
	}

	return res;
}

size_t count_parts(const char* start, const char* const end, const char sep)
{
	size_t num_parts = 1;
	while (start < end)
	{
		if (*start == sep)
		{
			num_parts += 1;
		}
		start += 1;
	}
	return num_parts;
}

void kanji_group_parse_reading_indicies(kanji_group_t* kanji_group, const char* start, const char* end, buffer_t* dentry_buffer)
{
	kanji_group->num_reading_indices = count_parts(start, end, ',');
	static_assert(MAX_READING_INDEX <= 255, "uint8_t not enough for reading indices");
	kanji_group->reading_indices = (uint8_t*)buffer_allocate(dentry_buffer, sizeof(uint8_t)*kanji_group->num_reading_indices);

	size_t reading_index_index = 0;
	uint8_t reading_index = 0;
	while (start != end)
	{
		if (*start == ',')
		{
			kanji_group->reading_indices[reading_index_index] = reading_index;
			reading_index_index += 1;
			reading_index = 0;
		}
		else
		{
			reading_index = reading_index * 10 + (*start - '0');
		}
		start += 1;
	}
	kanji_group->reading_indices[reading_index_index] = reading_index;
}

void parse_surfaces(surface_t* surfaces, const char* start, const char* end, const char sep)
{
	size_t surface_index = 0;
	while (start < end)
	{
		surfaces[surface_index].text = start;
		const char* surface_end = find_char(start, end, sep);
		if (*(surface_end - 1) == 'U')
		{
			surfaces[surface_index].common = false;
			surfaces[surface_index].length = (surface_end - start) - 1;
		}
		else
		{
			surfaces[surface_index].common = true;
			surfaces[surface_index].length = (surface_end - start);
		}
		start = surface_end + 1;
		surface_index += 1;
	}
}

void kanji_group_parse_kanjis(kanji_group_t* kanji_group, const char* start, const char* end, buffer_t* dentry_buffer)
{
	kanji_group->num_kanjis = count_parts(start, end, ',');
	kanji_group->kanjis = (kanji_t*)buffer_allocate(dentry_buffer, sizeof(kanji_t)*kanji_group->num_kanjis);

	parse_surfaces(kanji_group->kanjis, start, end, ',');
}


void kanji_group_parse(kanji_group_t* kanji_group, const char* start, const char* end, buffer_t* dentry_buffer)
{
	const char* specification = find_char(start, end, '#');
	if (specification != end)
	{
		kanji_group_parse_reading_indicies(kanji_group, specification + 1, end, dentry_buffer);
		end = specification;
	}
	else
	{
		kanji_group->num_reading_indices = 0;
	}

	kanji_group_parse_kanjis(kanji_group, start, end, dentry_buffer);
}

void dentry_parse_kanjis(dentry_t* dentry, buffer_t* dentry_buffer)
{
	dentry->num_kanji_groups = count_parts(dentry->kanjis_start, dentry->readings_start - 1, ';');
	dentry->kanji_groups = (kanji_group_t*)buffer_allocate(dentry_buffer, sizeof(kanji_group_t) * dentry->num_kanji_groups);
	size_t group_index = 0;
	const char* cur = dentry->kanjis_start;
	while (group_index != dentry->num_kanji_groups)
	{
		const char* end = find_char(cur, dentry->readings_start - 1, ';');
		kanji_group_parse(dentry->kanji_groups + group_index, cur, end, dentry_buffer);
		group_index += 1;
		cur = end + 1;
	}
}

void dentry_parse_readings(dentry_t* dentry, buffer_t* dentry_buffer)
{
	const char* start = dentry->readings_start;
	const char* end = dentry->definition_start - 1;
	dentry->num_readings = count_parts(dentry->readings_start, end, ';');
	dentry->readings = (reading_t*)buffer_allocate(dentry_buffer, sizeof(reading_t)*dentry->num_readings);

	parse_surfaces(dentry->readings, start, end, ';');
}

void parse_i_promise_i_wont_overwrite_it_strings(
	size_t* num, i_promise_i_wont_overwrite_it_string_t** arr,
	const char* start, const char* end, char sep,
	buffer_t* dentry_buffer)
{
	*num = count_parts(start, end, sep);
	*arr = (i_promise_i_wont_overwrite_it_string_t*)buffer_allocate(
		dentry_buffer,
		sizeof(i_promise_i_wont_overwrite_it_string_t)*(*num)
	);

	size_t str_index = 0;
	do
	{
		(*arr)[str_index].text = start;
		const char* str_end = find_char(start, end, sep);
		(*arr)[str_index].length = (str_end - start);
		start = str_end + 1;
		str_index += 1;
	}
	while (start < end);
}

void sense_group_parse(sense_group_t* sense_group, const char* start, const char* end, buffer_t* dentry_buffer)
{
	const char* sep = find_char(start, end, ';');

	parse_i_promise_i_wont_overwrite_it_strings(&sense_group->num_types, &sense_group->types, start, sep, ',', dentry_buffer);

	if (sep + 1 < end)
	{
		parse_i_promise_i_wont_overwrite_it_strings(&sense_group->num_senses, &sense_group->senses, sep + 1, end, '`', dentry_buffer);
	}
	else
	{
		sense_group->num_senses = 0;
	}
}

void dentry_parse_definition(dentry_t* dentry, buffer_t* dentry_buffer)
{
	dentry->num_sense_groups = count_parts(dentry->definition_start, dentry->definition_end, '\\');
	dentry->sense_groups = (sense_group_t*)buffer_allocate(dentry_buffer, sizeof(sense_group_t)*dentry->num_sense_groups);

	size_t group_index = 0;
	const char* cur = dentry->definition_start;
	while (group_index != dentry->num_sense_groups)
	{
		const char* end = find_char(cur, dentry->definition_end, '\\');
		sense_group_parse(dentry->sense_groups + group_index, cur, end, dentry_buffer);
		group_index += 1;
		cur = end + 1;
	}
}

void dentry_parse(dentry_t* dentry)
{
	buffer_t* dentry_buffer = state_get_dentry_buffer();
	if (dentry->kanjis_start != NULL)
	{
		dentry_parse_kanjis(dentry, dentry_buffer);
	}
	dentry_parse_readings(dentry, dentry_buffer);
	dentry_parse_definition(dentry, dentry_buffer);
}

void dentry_drop_kanji_groups(dentry_t* dentry)
{
	dentry->kanjis_start = NULL;
}

bool filter_surfaces(surface_t* current, const surface_t* const end, const char16_t* key, const size_t key_length)
{
	bool matched = false;
	for (; current != end; ++current)
	{
		if (utf16_utf8_kata_to_hira_eq(key, key_length, current->text, current->length))
		{
			matched = true;
		}
		else
		{
			current->length = 0;
		}
	}
	return matched;
}

void dentry_filter_readings(dentry_t* dentry, const char16_t* key, const size_t key_length)
{
	reading_t* current = dentry->readings;
	const reading_t* const end = current + dentry->num_readings;
	filter_surfaces(current, end, key, key_length);
}

bool has_surface(surface_t* current, const surface_t* const end, const char16_t* key, const size_t key_length)
{
	for (; current != end; ++current)
	{
		if (utf16_utf8_kata_to_hira_eq(key, key_length, current->text, current->length))
		{
			return true;
		}
	}
	return false;
}

void dentry_filter_kanji_groups(dentry_t* dentry, const char16_t* key, const size_t key_length)
{
	kanji_group_t* current = dentry->kanji_groups;
	const kanji_group_t* const end = current + dentry->num_kanji_groups;
	bool has_matching_kanji = false;
	for (; !has_matching_kanji && current != end; ++current)
	{
		kanji_t* kanjis_start = current->kanjis;
		const kanji_t* const kanjis_end = kanjis_start + current->num_kanjis;
		has_matching_kanji = has_surface(kanjis_start, kanjis_end, key, key_length);

	}
	if (!has_matching_kanji)
	{
		return;
	}

	current = dentry->kanji_groups;
	for (; current != end; ++current)
	{
		kanji_t* kanjis_start = current->kanjis;
		const kanji_t* const kanjis_end = kanjis_start + current->num_kanjis;
		if (!filter_surfaces(kanjis_start, kanjis_end, key, key_length))
		{
			current->num_kanjis = 0;
		}
	}
}
