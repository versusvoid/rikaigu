#ifndef CRF_H
#define CRF_H
#include <string>

std::string crf_extend(const char* utf8_text, const char* utf8_prefix, int32_t* prefix_length);

bool crf_init(const char* model_file_content, uint32_t length);

#endif // CRF_H
