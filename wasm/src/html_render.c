#include "html_render.h"

#include <stdbool.h>
#include <assert.h>

#include "state.h"
#include "libc.h"
#include "word_results.h"
#include "names_types_mapping.h"
#include "review_list.h"

void append(buffer_t* b, const char* str, size_t length)
{
	memcpy(buffer_allocate(b, length), str, length);
}
void append_char(buffer_t* b, char c)
{
	*(char*)buffer_allocate(b, 1) = c;
}

void append_uint(buffer_t* b, uint32_t v)
{
	if (v == 0)
	{
		append_char(b, '0');
		return;
	}

	char buf[10];
	size_t digits = 0;
	while (v != 0)
	{
		digits += 1;
		buf[sizeof(buf) - digits] = (v % 10) + '0';
		v /= 10;
	}
	append(b, buf + sizeof(buf) - digits, digits);
}


#define append_static(literal) do { \
		const char str[] = literal; \
		append(b, str, sizeof(str) - 1); \
	} while(0)
#define conditionally_append(cond, literal) if (cond) append_static(literal)
#define MOAR_CUT 2

void try_render_inflection_info(buffer_t* b, word_result_t* wr)
{
	if (word_result_get_inflection_name_length(wr) > 0)
	{
		append_static(" <span class=\"w-conj\">(");
		append(b, word_result_get_inflection_name(wr), word_result_get_inflection_name_length(wr));
		append_static(")</span>");
	}
}

bool render_reading(buffer_t* b, const reading_t* reading, bool second_and_further)
{
	if (reading->length == 0) // filtered out by search key
	{
		return false;
	}

	conditionally_append(second_and_further, u8"、");
	append_static("<span class=\"w-kana");
	conditionally_append(!reading->common, " uncommon");
	append_static("\">");
	append(b, reading->text, reading->length);
	append_static("</span>");

	return true;
}

void render_all_readings(buffer_t* b, dentry_t* dentry, bool add_review_listed, bool add_hidden)
{
	append_static("<span class=\"w-kana-container");
	conditionally_append(add_review_listed, " rikaigu-review-listed");
	conditionally_append(add_hidden, " rikaigu-hidden");
	append_static("\">");

	bool rendered_some = false;
	const reading_t* current = dentry->readings;
	const reading_t* const end = current + dentry->num_readings;
	for (; current < end; ++current)
	{
		rendered_some |= render_reading(b, current, rendered_some);
	}

	append_static("</span>");
}

void render_some_readings(buffer_t* b, dentry_t* dentry, uint8_t* indices, size_t num_indices, bool add_hidden)
{
	append_static("<span class=\"w-kana-container rikaigu-review-listed");
	conditionally_append(add_hidden, " rikaigu-hidden");
	append_static("\">");

	bool rendered_some = false;
	const uint8_t* current = indices;
	const uint8_t* const end = current + num_indices;
	for (; current < end; ++current)
	{
		reading_t* r = dentry->readings + (*current);
		rendered_some |= render_reading(b, r, rendered_some);
	}

	append_static("</span>");
}

bool render_kanji(buffer_t* b, const kanji_t* kanji, bool second_and_further)
{
	if (kanji->length == 0) // filtered out by search key
	{
		return false;
	}

	conditionally_append(second_and_further, u8"、");
	append_static("<span class=\"w-kanji");
	conditionally_append(!kanji->common, " uncommon");
	append_static("\">");
	append(b, kanji->text, kanji->length);
	append_static("</span>");

	return true;
}

void render_all_kanjis(buffer_t* b, const kanji_group_t* group)
{
	bool rendered_some = false;
	const kanji_t* current = group->kanjis;
	const kanji_t* const end = current + group->num_kanjis;
	for (; current < end; ++current)
	{
		rendered_some |= render_kanji(b, current, rendered_some);
	}
}

void render_kanji_group(buffer_t* b, word_result_t* wr, dentry_t* dentry, kanji_group_t* group, bool first, bool from_review_list)
{
	if (group->num_kanjis == 0) // filtered out by search key
	{
		return;
	}

	render_all_kanjis(b, group);
	append_static("<span class=\"spacer\"></span>&#32;");

	if (group->num_reading_indices > 0)
	{
		render_some_readings(b, dentry, group->reading_indices, group->num_reading_indices, from_review_list);
	}
	else
	{
		render_all_readings(b, dentry, true, from_review_list);
	}

	if (first)
	{
		try_render_inflection_info(b, wr);
	}
	append_static("<br />");
}

void render_readings_only_dentry_readings(buffer_t* b, word_result_t* wr, dentry_t* dentry)
{
	render_all_readings(b, dentry, false, false);
	try_render_inflection_info(b, wr);
	append_static("<br />");
}

void render_type(buffer_t* b, const char* text, const size_t length, bool is_name)
{
	if (is_name)
	{
		name_type_mapping_t* mapping = get_mapped_type(*text);
		if (mapping)
		{
			append(b, mapping->type, mapping->length);
		}
	}
	else
	{
		append(b, text, length);
	}
}

void render_sense_group(buffer_t* b, sense_group_t* sense_group, bool is_name, bool from_review_list)
{
	append_static("<span class=\"w-pos\">");

	for (size_t i = 0; i < sense_group->num_types; ++i)
	{
		conditionally_append(i > 0, ", ");
		render_type(b, sense_group->types[i].text, sense_group->types[i].length, is_name);
	}
	append_static("</span>");
	if (sense_group->num_senses == 0)
	{
		return;
	}
	append_static("<span class=\"rikaigu-review-listed");
	conditionally_append(!from_review_list, " rikaigu-hidden");
	append_static("\">; </span>");

	if (sense_group->num_senses > 1)
	{
		append_static("<ul class=\"w-def rikaigu-review-listed");
		conditionally_append(from_review_list, " rikaigu-hidden");
		append_static("\"><li>");
		for (size_t i = 0; i < sense_group->num_senses; ++i)
		{
			conditionally_append(i > 0, "</li><li>");
			append(b, sense_group->senses[i].text, sense_group->senses[i].length);
		}
		append_static("</li></ul>");
	}
	else
	{
		append_static(" <span class=\"w-def rikaigu-review-listed");
		conditionally_append(from_review_list, " rikaigu-hidden");
		append_static("\">");
		append(b, sense_group->senses[0].text, sense_group->senses[0].length);
		append_static("</span><br />");
	}
}

void render_dentry(buffer_t* b, word_result_t* wr, dentry_t* dentry, const bool from_review_list)
{
	if (dentry->num_kanji_groups > 0)
	{
		for (size_t i = 0; i < dentry->num_kanji_groups; ++i)
		{
			render_kanji_group(b, wr, dentry, dentry->kanji_groups + i, (i == 0), from_review_list);
		}
	}
	else
	{
		render_readings_only_dentry_readings(b, wr, dentry);
	}

	if (!word_result_is_name(wr))
	{
		append_static("<p class=\"w-review-context rikaigu-review-listed");
		conditionally_append(!from_review_list, " rikaigu-hidden");
		append_static("\">");
		if (from_review_list)
		{
			//append(b, review_list_entry->text, review_list_entry->length);
		}
		append_static("</p>");
	}

	append_static("<div class=\"rikaigu-pos-and-def\">");

	for (size_t i = 0; i < dentry->num_sense_groups; ++i)
	{
		render_sense_group(b, dentry->sense_groups + i, word_result_is_name(wr), from_review_list);
	}

	append_static("</div>");
}

void render_entry(buffer_t* b, word_result_t* wr, bool moar_cut)
{
	append_static("<tr class=\"");
	conditionally_append(moar_cut, "rikaigu-second-and-further rikaigu-hidden");
	append_static("\">");

	dentry_t* dentry = word_result_get_dentry(wr);
	/*
	const auto& review_list_entry = config.review_list.find(result.data[i].dentry.id());
	std::string* review_list_context = (
		review_list_entry == config.review_list.end() ? nullptr : &review_list_entry->second
	);
	review_list_entry_t* review_list_entry = NULL;
	*/
	bool from_review_list = false;

	append_static("<td class=\"word");
	if (word_result_is_name(wr))
	{
		append_static(" rikaigu-name");
	}
	else
	{
		from_review_list = in_review_list(dentry->entry_id);
		conditionally_append(from_review_list, " reviewed");
		append_static(" reviewable\" jmdict-id=\"");
		append_uint(b, dentry->entry_id);
	}
	append_static("\">");

	render_dentry(b, wr, dentry, from_review_list);

	append_static("</td></tr>");
}

void render_entries(buffer_t* b)
{
	//append_static("<span class=\"note rikaigu-pos-and-def\">`D` - show definitions</span><div class=\"clearfix\"></div>");

	append_static("<table>");
	word_result_iterator_t it = state_get_word_result_iterator();
	size_t i = 0;
	for (; it.current < it.end; word_result_iterator_next(&it), i += 1)
	{
		render_entry(b, it.current, i >= MOAR_CUT);
	}
	append_static("</table>");
	conditionally_append(i > MOAR_CUT, u8"<div class=\"rikaigu-lurk-moar\">▼</div>");
}

void make_html()
{
	buffer_t* buffer = state_get_html_buffer();
	render_entries(buffer);
}
