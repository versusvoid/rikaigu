#pragma once

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <uchar.h>

typedef struct {
	const char* text;
	size_t length;
	bool common;
} surface_t;

typedef surface_t kanji_t;
typedef surface_t reading_t;

typedef struct {
	size_t num_reading_indices;
	uint8_t* reading_indices;

	size_t num_kanjis;
	kanji_t* kanjis;
} kanji_group_t;

typedef struct i_promise_i_wont_overwrite_it_string {
	const char* text;
	size_t length;
} i_promise_i_wont_overwrite_it_string_t;

typedef struct {
	size_t num_types;
	i_promise_i_wont_overwrite_it_string_t* types;

	size_t num_senses;
	i_promise_i_wont_overwrite_it_string_t* senses;
} sense_group_t;

typedef struct {
	const char* kanjis_start;
	const char* readings_start;
	const char* definition_start;
	const char* definition_end;
	int32_t freq;

	size_t num_kanji_groups;
	kanji_group_t* kanji_groups;

	size_t num_readings;
	reading_t* readings;

	size_t num_sense_groups;
	sense_group_t* sense_groups;
} dentry_t;

dentry_t* dentry_make(const char* raw, size_t length);

void dentry_drop_kanji_groups(dentry_t* dentry);

void dentry_parse(dentry_t* dentry);

void dentry_filter_readings(dentry_t* dentry, const char16_t* key, const size_t key_length);
void dentry_filter_kanji_groups(dentry_t* dentry, const char16_t* key, const size_t key_length);
