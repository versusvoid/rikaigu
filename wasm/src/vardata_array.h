#include "state.h"

void vardata_array_make(buffer_t* buf, size_t element_size);

size_t vardata_array_num_elements(buffer_t* b);

size_t vardata_array_capacity(buffer_t* b);

void vardata_array_increment_size(buffer_t* b);

void vardata_array_set_size(buffer_t* b, const size_t new_size);

void* vardata_array_elements_start(buffer_t* b);

void* vardata_array_vardata_start(buffer_t* b);

void* vardata_array_reserve_place_for_element(buffer_t* b, const size_t element_vardata_size);
