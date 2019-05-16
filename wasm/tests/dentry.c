#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include "fake-memory.h"

#include "../src/state.c"
#include "../src/libc.c"
#include "../src/utf.c"
#include "../src/dentry.c"

void test_to_number_unchecked()
{
	const char number[] = "12398174";
	assert(to_number_unchecked(number, strlen(number)) == 12398174);
}

void test_is_number()
{
	const char number[] = "12398174";
	assert(is_number(number, strlen(number)));

	const char not_a_number[] = u8"1１2２3３4４5５6６7７8８9９";
	assert(!is_number(not_a_number, strlen(not_a_number)));

	const char not_a_number2[] = u8"1oo5oo";
	assert(!is_number(not_a_number2, strlen(not_a_number2)));
}

void test_find()
{
	const char s1[] = "some string";
	assert(find(s1, s1 + strlen(s1), ' ') == s1 + 4);
	assert(find(s1, s1 + strlen(s1), 'g') == s1 + 10);
	assert(find(s1, s1 + strlen(s1), 's') == s1);
	assert(find(s1, s1 + strlen(s1), '1') == s1 + strlen(s1));
}

void test_dentry_make()
{
	setup_memory();
	init((size_t)wasm_memory, wasm_memory_size_pages * (1<<16));

	const char case1[] = "kanji\tkana\tdefinition\t123";
	const dentry_t* d = dentry_make(case1, strlen(case1));
	assert(state->buffers[DENTRY_BUFFER].size == sizeof(dentry_t));
	assert(state->buffers[DENTRY_BUFFER].data == d);
	assert(d->kanjis_start == case1);
	assert(d->readings_start == case1 + 6);
	assert(d->definition_start == case1 + 6 + 5);
	assert(d->definition_end == case1 + 6 + 5 + 10);
	assert(d->freq == 123);

	state->buffers[DENTRY_BUFFER].size = 0;
	const char case2[] = "kana\tdefinition";
	d = dentry_make(case2, strlen(case2));
	assert(state->buffers[DENTRY_BUFFER].size == sizeof(dentry_t));
	assert(state->buffers[DENTRY_BUFFER].data == d);
	assert(d->kanjis_start == NULL);
	assert(d->readings_start == case2);
	assert(d->definition_start == case2 + 5);
	assert(d->definition_end == case2 + strlen(case2));
	assert(d->freq == UNKNOWN_WORD_FREQ_ORDER);

	state->buffers[DENTRY_BUFFER].size = 0;
	const char case3[] = "kana\tdefinition\t456";
	d = dentry_make(case3, strlen(case3));
	assert(state->buffers[DENTRY_BUFFER].size == sizeof(dentry_t));
	assert(state->buffers[DENTRY_BUFFER].data == d);
	assert(d->kanjis_start == NULL);
	assert(d->readings_start == case3);
	assert(d->definition_start == case3 + 5);
	assert(d->definition_end == case3 + 5 + 10);
	assert(d->freq == 456);

	state->buffers[DENTRY_BUFFER].size = 0;
	const char case4[] = "kanji\tkana\tdefinition";
	d = dentry_make(case4, strlen(case4));
	assert(state->buffers[DENTRY_BUFFER].size == sizeof(dentry_t));
	assert(state->buffers[DENTRY_BUFFER].data == d);
	assert(d->kanjis_start == case4);
	assert(d->readings_start == case4 + 6);
	assert(d->definition_start == case4 + 6 + 5);
	assert(d->definition_end == case4 + 6 + 5 + 10);
	assert(d->freq == UNKNOWN_WORD_FREQ_ORDER);

	clear_memory();
}

void test_count_parts()
{
	const char s1[] = "ab;d\tefa;asdad\tjkh0;12ej18y9v\tskakhdkqhda;#sdf";
	assert(count_parts(s1, s1 + strlen(s1), '\t') == 4);

	const char s2[] = "ab;d\tefa;asdad\tjkh0;12ej18y9v\tskakhdkqhda;#sdf";
	assert(count_parts(s2, s2 + strlen(s1), ';') == 5);
}

void test_kanji_group_parse_reading_indicies()
{
	setup_memory();
	init((size_t)wasm_memory, wasm_memory_size_pages * (1<<16));

	kanji_group_t kg;
	memset(&kg, 0, sizeof(kg));

	const char str_indices[] = "5,71,127,82,35";
	kanji_group_parse_reading_indicies(&kg, str_indices, str_indices + strlen(str_indices), state->buffers + DENTRY_BUFFER);
	assert(kg.num_reading_indices == 5);
	assert(kg.reading_indices == state->buffers[DENTRY_BUFFER].data);
	assert(state->buffers[DENTRY_BUFFER].size == 5);
	const uint8_t num_indices[] = {5, 71, 127, 82, 35};
	assert(memcmp(num_indices, kg.reading_indices, sizeof(num_indices)) == 0);

	clear_memory();
}

void test_parse_surfaces()
{
	surface_t kanjis[5];
	const char s1[] = "abU,bcd,cdefU,d1,esadad";
	parse_surfaces(kanjis, s1, s1 + strlen(s1), ',');
	assert(!kanjis[0].common);
	assert(kanjis[0].text == s1);
	assert(kanjis[0].length == 2);

	assert(kanjis[1].common);
	assert(kanjis[1].text == s1 + 4);
	assert(kanjis[1].length == 3);

	assert(!kanjis[2].common);
	assert(kanjis[2].text == s1 + 4 + 4);
	assert(kanjis[2].length == 4);

	assert(kanjis[3].common);
	assert(kanjis[3].text == s1 + 4 + 4 + 6);
	assert(kanjis[3].length == 2);

	assert(kanjis[4].common);
	assert(kanjis[4].text == s1 + 4 + 4 + 6 + 3);
	assert(kanjis[4].length == 6);

	surface_t kanas[3];
	const char s2[] = "k89U;a901U;1hrohgi";
	parse_surfaces(kanas, s2, s2 + strlen(s2), ';');
	assert(!kanas[0].common);
	assert(kanas[0].text == s2);
	assert(kanas[0].length == 3);

	assert(!kanas[1].common);
	assert(kanas[1].text == s2 + 5);
	assert(kanas[1].length == 4);

	assert(kanas[2].common);
	assert(kanas[2].text == s2 + 5 + 6);
	assert(kanas[2].length == 7);
}

void test_kanji_group_parse()
{
	setup_memory();
	init((size_t)wasm_memory, wasm_memory_size_pages * (1<<16));

	kanji_group_t kg;
	const char case1[] = "a,bU,c#3,2,5,6";
	kanji_group_parse(&kg, case1, case1 + strlen(case1), state->buffers + DENTRY_BUFFER);
	assert(kg.num_kanjis == 3);
	assert(kg.kanjis[0].text == case1);
	assert(kg.kanjis[1].text == case1 + 2);
	assert(kg.kanjis[2].text == case1 + 2 + 3);
	assert(kg.num_reading_indices == 4);
	assert(kg.reading_indices[0] == 3);
	assert(kg.reading_indices[3] == 6);
	assert(state->buffers[DENTRY_BUFFER].size == 3*sizeof(kanji_t) + 4 * sizeof(uint8_t));

	state->buffers[DENTRY_BUFFER].size = 0;
	memset(&kg, 0, sizeof(kg));

	const char case2[] = "abcU,def,cef";
	kanji_group_parse(&kg, case2, case2 + strlen(case2), state->buffers + DENTRY_BUFFER);
	assert(kg.num_kanjis == 3);
	assert(kg.kanjis[0].text == case2);
	assert(kg.kanjis[1].text == case2 + 5);
	assert(kg.kanjis[2].text == case2 + 5 + 4);
	assert(kg.num_reading_indices == 0);
	assert(state->buffers[DENTRY_BUFFER].size == 3*sizeof(kanji_t));

	clear_memory();
}

void test_dentry_parse_kanjis()
{
	setup_memory();
	init((size_t)wasm_memory, wasm_memory_size_pages * (1<<16));

	const char test[] = u8"いっその事#0;一層のことU,一層の事U;いっそうの事U#1";
	dentry_t d;
	d.kanjis_start = test;
	d.readings_start = test + sizeof(test);
	dentry_parse_kanjis(&d, state->buffers + DENTRY_BUFFER);
	assert(state->buffers[DENTRY_BUFFER].size == 3*sizeof(kanji_group_t) + 4*sizeof(kanji_t) + 2*sizeof(uint8_t));
	assert(d.num_kanji_groups == 3);

	assert(d.kanji_groups[0].num_kanjis == 1);
	assert(d.kanji_groups[0].kanjis[0].text == test);
	assert(d.kanji_groups[0].kanjis[0].length == 15);
	assert(d.kanji_groups[0].kanjis[0].common);
	assert(d.kanji_groups[0].num_reading_indices == 1);
	assert(d.kanji_groups[0].reading_indices[0] == 0);

	assert(d.kanji_groups[1].num_kanjis == 2);
	assert(d.kanji_groups[1].kanjis[0].text == test + 15 + 3);
	assert(d.kanji_groups[1].kanjis[0].length == 15);
	assert(!d.kanji_groups[1].kanjis[0].common);
	assert(d.kanji_groups[1].kanjis[1].text == test + 15 + 3 + 15 + 2);
	assert(d.kanji_groups[1].kanjis[1].length == 12);
	assert(!d.kanji_groups[1].kanjis[1].common);
	assert(d.kanji_groups[1].num_reading_indices == 0);

	assert(d.kanji_groups[2].num_kanjis == 1);
	assert(d.kanji_groups[2].kanjis[0].text == test + 15 + 3 + 15 + 2 + 12 + 2);
	assert(d.kanji_groups[2].kanjis[0].length == 18);
	assert(!d.kanji_groups[2].kanjis[0].common);
	assert(d.kanji_groups[2].num_reading_indices == 1);
	assert(d.kanji_groups[2].reading_indices[0] == 1);

	clear_memory();
}

void test_dentry_parse_readings()
{
	setup_memory();
	init((size_t)wasm_memory, wasm_memory_size_pages * (1<<16));

	const char test[] = u8"うとうと;ウトウトU;うとっとU;ウトッとU;ウトっとU";
	dentry_t d;
	d.readings_start = test;
	d.definition_start = test + sizeof(test);
	dentry_parse_readings(&d, state->buffers + DENTRY_BUFFER);
	assert(state->buffers[DENTRY_BUFFER].size == 5*sizeof(reading_t));
	assert(d.num_readings == 5);

	assert(d.readings[0].text == test);
	assert(d.readings[0].length == 12);
	assert(d.readings[0].common);

	assert(d.readings[1].text == test + 12 + 1);
	assert(d.readings[1].length == 12);
	assert(!d.readings[1].common);

	assert(d.readings[2].text == test + 12 + 1 + 12 + 2);
	assert(d.readings[2].length == 12);
	assert(!d.readings[2].common);

	assert(d.readings[3].text == test + 12 + 1 + 12 + 2 + 12 + 2);
	assert(d.readings[3].length == 12);
	assert(!d.readings[3].common);

	assert(d.readings[4].text == test + 12 + 1 + 12 + 2 + 12 + 2 + 12 + 2);
	assert(d.readings[4].length == 12);
	assert(!d.readings[4].common);

	clear_memory();
}

void test_parse_i_promise_i_wont_overwrite_it_strings()
{
	setup_memory();
	init((size_t)wasm_memory, wasm_memory_size_pages * (1<<16));

	size_t num;
	i_promise_i_wont_overwrite_it_string_t* arr;
	const char s[] = "a`b`dcdsf`dsfs;sdf:Jjksf`sflk1 01h`asd n";
	parse_i_promise_i_wont_overwrite_it_strings(&num, &arr, s, s + strlen(s), '`', state->buffers + DENTRY_BUFFER);
	assert(state->buffers[DENTRY_BUFFER].size == 6 * sizeof(i_promise_i_wont_overwrite_it_string_t));
	assert(num == 6);
	assert(arr == state->buffers[DENTRY_BUFFER].data);
	assert(arr[0].text == s);
	assert(arr[0].length == 1);
	assert(arr[1].text == s + 1 + 1);
	assert(arr[1].length == 1);
	assert(arr[2].text == s + 1 + 1 + 1 + 1);
	assert(arr[2].length == 5);
	assert(arr[3].text == s + 1 + 1 + 1 + 1 + 5 + 1);
	assert(arr[3].length == 14);
	assert(arr[4].text == s + 1 + 1 + 1 + 1 + 5 + 1 + 14 + 1);
	assert(arr[4].length == 9);
	assert(arr[5].text == s + 1 + 1 + 1 + 1 + 5 + 1 + 14 + 1 + 9 + 1);
	assert(arr[5].length == 5);

	clear_memory();
}

void test_sense_group_parse()
{
	setup_memory();
	init((size_t)wasm_memory, wasm_memory_size_pages * (1<<16));

	const char s[] = "n;pitch (i.e. pace, speed, angle, space, field, sound, etc.)`pitch (from distilling petroleum, tar, etc.)`pitch (football, rugby); playing field`PHS portable phone";
	sense_group_t sg;
	sense_group_parse(&sg, s, s + strlen(s), state->buffers + DENTRY_BUFFER);
	assert(state->buffers[DENTRY_BUFFER].size == (1 + 4) * sizeof(i_promise_i_wont_overwrite_it_string_t));

	assert(sg.num_types == 1);
	assert(sg.types[0].text == s);
	assert(sg.types[0].length == 1);

	assert(sg.num_senses == 4);
	assert(sg.senses[0].text == s + 1 + 1);
	assert(sg.senses[0].length == 58);
	assert(sg.senses[1].text == s + 1 + 1 + 58 + 1);
	assert(sg.senses[1].length == 44);
	assert(sg.senses[2].text == s + 1 + 1 + 58 + 1 + 44 + 1);
	assert(sg.senses[2].length == 38);
	assert(sg.senses[3].text == s + 1 + 1 + 58 + 1 + 44 + 1 + 38 + 1);
	assert(sg.senses[3].length == 18);

	clear_memory();
}

void test_dentry_parse_definition()
{
	setup_memory();
	init((size_t)wasm_memory, wasm_memory_size_pages * (1<<16));

	const char s[] = "n-suf;depending on`as soon as; immediately`in accordance with\\n;order; program`circumstances; reason";
	dentry_t d;
	d.definition_start = s;
	d.definition_end = s + strlen(s);
	dentry_parse_definition(&d, state->buffers + DENTRY_BUFFER);
	assert(state->buffers[DENTRY_BUFFER].size == (
		2*sizeof(sense_group_t)
		+ (1 + 3)*sizeof(i_promise_i_wont_overwrite_it_string_t)
		+ (1 + 2)*sizeof(i_promise_i_wont_overwrite_it_string_t)
	));
	assert(d.num_sense_groups == 2);
	assert(d.sense_groups[0].num_types == 1);
	assert(d.sense_groups[0].num_senses == 3);
	assert(d.sense_groups[1].num_types == 1);
	assert(d.sense_groups[1].types[0].text == s + 62);
	assert(d.sense_groups[1].num_senses == 2);
	assert(d.sense_groups[1].senses[0].text == s + 62 + 2);

	clear_memory();
}

void test_dentry_parse_whole()
{
	setup_memory();
	init((size_t)wasm_memory, wasm_memory_size_pages * (1<<16));

	const char s[] = u8"我;吾U#0,1,2,3,4;吾れU,我れU#0,2	われ;わU;あれU;あU;わぬU;わろU	pn;I; me`(only われ,わ) oneself`(only われ,わ) you\\pref;(only わ) (also 和) prefix indicating familiarity or contempt	2677";
	dentry_t* d = dentry_make(s, strlen(s));
	dentry_parse(d);

	assert(d->freq == 2677);
	assert(d->num_readings == 6);
	assert(!d->readings[5].common);
	assert(d->num_kanji_groups == 3);
	assert(d->kanji_groups[2].num_kanjis == 2);
	assert(d->kanji_groups[2].num_reading_indices == 2);
	assert(!d->kanji_groups[2].kanjis[1].common);
	assert(d->num_sense_groups == 2);
	assert(d->sense_groups[0].num_types == 1);
	assert(d->sense_groups[0].num_senses == 3);

	clear_memory();
}

int main()
{
	test_to_number_unchecked();
	test_is_number();
	test_find();
	test_dentry_make();
	test_count_parts();
	test_kanji_group_parse_reading_indicies();
	test_parse_surfaces();
	test_kanji_group_parse();
	test_dentry_parse_kanjis();
	test_dentry_parse_readings();
	test_parse_i_promise_i_wont_overwrite_it_strings();
	test_sense_group_parse();
	test_dentry_parse_definition();
	test_dentry_parse_whole();

	return 0;
}
