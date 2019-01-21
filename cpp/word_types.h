#ifndef WORT_TYPES_H
#define WORT_TYPES_H

#include <map>
#include <vector>
#include <string>
#include <cstdint>

extern std::map<std::string, uint32_t> INFLECTION_TYPES;
extern uint32_t ANY_TYPE;
uint32_t inflection_type_to_int(const char* start, const char* end);
uint32_t inflection_type_to_int(const std::vector<std::string>& types);

#endif // WORT_TYPES_H
