#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <uchar.h>
#ifndef NDEBUG
#include <stdio.h>
#endif

#include "dentry.h"

typedef enum {
	WORDS = 0x1,
	NAMES = 0x2,
} Dictionary;

#define export __attribute__((visibility("default")))

typedef struct {
	char16_t data[32];
	uint8_t length_mapping[32];
	uint8_t length;
} input_t;

typedef struct {
	size_t capacity; // === 0 mod 8
	size_t size;
	void* data;
} buffer_t;

input_t* state_get_input(void);

void* buffer_allocate(buffer_t* buffer, size_t num_bytes);

void state_clear(void);

buffer_t* state_get_candidate_buffer(void);
buffer_t* state_get_index_entry_buffer(void);
buffer_t* state_get_word_result_buffer(void);
buffer_t* state_get_raw_dentry_buffer(void);
buffer_t* state_get_dentry_buffer(void);
buffer_t* state_get_html_buffer(void);
