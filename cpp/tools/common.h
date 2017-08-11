#pragma once
#include <crfxx/encode.h>

sample_t read_sample(const std::u16string& line);

void test(const weights_t& weights, const train_feature_index_t& feature_index, const char* filename);

void main_init();
