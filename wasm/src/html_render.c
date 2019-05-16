#include "html_render.h"

#include <stdbool.h>
#include <assert.h>

#include "state.h"
#include "libc.h"
#include "word_results.h"

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

void render_reading(buffer_t* b, reading_t* reading, bool second_and_further, bool add_hidden)
{
	conditionally_append(second_and_further, u8"、");
	append_static("<span class=\"w-kana rikaigu-review-listed");
	conditionally_append(!reading->common, " uncommon");
	conditionally_append(add_hidden, "rikaigu-hidden");
	append_static("\">");
	append(b, reading->text, reading->length);
	append_static("</span>");
}

void render_all_readings(buffer_t* b, dentry_t* dentry, bool add_hidden)
{
	for (size_t i = 0; i < dentry->num_readings; ++i)
	{
		reading_t* r = dentry->readings + i;
		render_reading(b, r, i > 0, add_hidden);
	}
}

void render_kanji_group(buffer_t* b, word_result_t* wr, dentry_t* dentry, kanji_group_t* group, bool first, bool from_review_list)
{
	for (size_t i = 0; i < group->num_kanjis; ++i)
	{
		kanji_t* k = group->kanjis + i;
		conditionally_append(i > 0, u8"、");
		append_static("<span class=\"w-kanji");
		conditionally_append(!k->common, " uncommon");
		append_static("\">");
		append(b, k->text, k->length);
		append_static("</span>");
	}
	append_static("<span class=\"spacer\"></span>&#32;");

	if (group->num_reading_indices > 0)
	{
		for (size_t i = 0; i < group->num_reading_indices; ++i)
		{
			reading_t* r = dentry->readings + group->reading_indices[i];
			render_reading(b, r, i > 0, from_review_list);
		}
	}
	else
	{
		render_all_readings(b, dentry, from_review_list);
	}

	if (first)
	{
		try_render_inflection_info(b, wr);
	}
	append_static("<br />");
}

void render_readings_only_dentry_readings(buffer_t* b, word_result_t* wr, dentry_t* dentry)
{
	render_all_readings(b, dentry, false);
	try_render_inflection_info(b, wr);
	append_static("<br />");
}

void render_sense_group(buffer_t* b, sense_group_t* sense_group, bool from_review_list)
{
	append_static("<span class=\"w-pos\">");

	for (size_t i = 0; i < sense_group->num_types; ++i)
	{
		conditionally_append(i > 0, ", ");
		append(b, sense_group->types[i].text, sense_group->types[i].length);
	}
	append_static("</span><span class=\"rikaigu-review-listed");
	conditionally_append(!from_review_list, "rikaigu-hidden");
	append_static("\">; </span>");

	if (sense_group->num_senses > 1)
	{
		append_static("<ul class=\"w-def rikaigu-review-listed");
		conditionally_append(from_review_list, "rikaigu-hidden");
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
		// TODO? generate readings for names
		assert(sense_group->num_senses == 1);
		append_static(" <span class=\"w-def rikaigu-review-listed");
		conditionally_append(from_review_list, "rikaigu-hidden");
		append_static("\">");
		append(b, sense_group->senses[0].text, sense_group->senses[0].length);
		append_static("</span><br />");
	}
}

void render_dentry(buffer_t* b, word_result_t* wr)
{
	const bool from_review_list = false; //review_list_entry != NULL;
	dentry_t* dentry = word_result_get_dentry(wr);
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
		conditionally_append(!from_review_list, "rikaigu-hidden");
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
		render_sense_group(b, dentry->sense_groups + i, from_review_list);
	}

	append_static("</div>");
}

void render_entry(buffer_t* b, word_result_t* wr, bool moar_cut)
{
	append_static("<tr class=\"");
	conditionally_append(moar_cut, " rikaigu-second-and-further rikaigu-hidden");
	append_static("\">");

	/*
	const auto& review_list_entry = config.review_list.find(result.data[i].dentry.id());
	std::string* review_list_context = (
		review_list_entry == config.review_list.end() ? nullptr : &review_list_entry->second
	);
	review_list_entry_t* review_list_entry = NULL;
	*/

	append_static("<td class=\"word");
	conditionally_append(word_result_is_name(wr), " rikaigu-name");
	/*
	conditionally_append(review_list_entry != NULL, "reviewed");
	conditionally_append(!word_result_is_name(wr), "reviewable");
	append_static("\" jmdict-id=");
	append_uint(b, word_result_get_dentry(wr)->id);
	*/
	append_static("\">");

	/*
	buffer += std::to_string(word.dentry.freq());
	buffer += ' ';
	buffer += std::to_string(word.score());
	buffer += "<br />";
	*/

	render_dentry(b, wr);
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
