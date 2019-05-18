#include <stdint.h>

typedef struct {
	char type[45];
	uint8_t length;
	char key;
} name_type_mapping_t;

name_type_mapping_t* get_mapped_type(char key);
