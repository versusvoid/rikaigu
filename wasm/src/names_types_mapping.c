#include "names_types_mapping.h"

#include <stddef.h>

#include "libc.h"

static name_type_mapping_t map[] = {
	{ .type = "place", .length = 5, .key = 'a' },
	{ .type = "company", .length = 7, .key = 'c' },
	{ .type = "product", .length = 7, .key = 'd' },
	{ .type = "female given name or forename", .length = 29, .key = 'f' },
	{ .type = "given name or forename, gender not specified", .length = 44, .key = 'g' },
	{ .type = "male given name or forename", .length = 27, .key = 'm' },
	{ .type = "family or surname", .length = 17, .key = 'n' },
	{ .type = "organization", .length = 12, .key = 'o' },
	{ .type = "full name of a particular person", .length = 32, .key = 'p' },
	{ .type = "railway station", .length = 15, .key = 's' },
	{ .type = "unclassified name", .length = 17, .key = 'u' },
	{ .type = "work of art, literature, music, etc. name", .length = 31, .key = 'w' },
};

int name_type_comparator(const void* key, const void* object)
{
	int key_char = (int)(size_t)key;
	const name_type_mapping_t* mapping = object;

	return key_char - (int)mapping->key;
}

name_type_mapping_t* get_mapped_type(char key)
{
	bool found = false;
	name_type_mapping_t* it = binary_locate(
		(void*)(size_t)key, map,
		sizeof(map) / sizeof(name_type_mapping_t), sizeof(name_type_mapping_t),
		name_type_comparator, &found
	);
	assert(found || key == ';');
	return found ? it : NULL;
}
