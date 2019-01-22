#include "html_render.h"
#include "utils.h"

#include <algorithm>
#include <cstring>
#include <cstdlib>
#include <emscripten.h>
#include <cassert>

static std::vector<std::string> radicals;
static std::string buffer;

bool render_init(const char* radicals_file_content, uint32_t length)
{
	buffer.reserve(2<<16);
	if (buffer.capacity() < (2<<16))
	{
		return false;
	}

	const char* it = radicals_file_content;
	const char* end = radicals_file_content + length;
	while (it < end)
	{
		const char* p = std::find(it, end, '\n');
		radicals.push_back(std::string(it, size_t(p - it)));
		it = p + 1;
	}

	free(const_cast<void*>(reinterpret_cast<const void*>(radicals_file_content)));

	return true;
}

static std::map<std::string, std::string> kanji_numbers = {
	{"H", "Halpern"},
	{"L", "Heisig"},
	{"E", "Henshall"},
	{"DK", "Kanji Learners Dictionary"},
	{"N", "Nelson"},
	{"V", "New Nelson"},
	{"Y", "PinYin"},
	{"P", "Skip Pattern"},
	{"IN", "Tuttle Kanji &amp; Kana"},
	{"I", "Tuttle Kanji Dictionary"},
	{"U", "Unicode"}
};

void render_kanji(const KanjiResult& kanji)
{
	buffer += "<table class=\"k-main-tb\"><tr><td valign=\"top\">";
	buffer += "<table class=\"k-abox-tb\"><tr>";

	buffer += "<td class=\"k-abox-r\">radical<br/>";
	const std::string& bn_str = kanji.misc.at("B");
	const size_t bn = std::stoul(bn_str) - 1;
	const std::string& radical = radicals.at(bn);
	buffer += radical.substr(0, radical.find('\t'));
	buffer += ' ';
	buffer += bn_str;
	buffer += "</td>";

	buffer += "<td class=\"k-abox-g\">";
	auto it = kanji.misc.find("G");
	if (it == kanji.misc.end())
	{
		buffer += '-';
	}
	else
	{
		if (it->second == "8")
		{
			buffer += "general<br/>use";
		}
		else if (it->second == "9")
		{
			buffer += "name<br/>use";
		}
		else
		{
			buffer += "grade<br/>";
			buffer += it->second;
		}
	}
	buffer += "</td></tr>";

	buffer += "<tr><td class=\"k-abox-f\">freq<br/>";
	it = kanji.misc.find("F");
	if (it == kanji.misc.end())
	{
		buffer += '-';
	}
	else
	{
		buffer += it->second;
	}
	buffer += "</td>";

	buffer += "<td class=\"k-abox-s\">strokes<br/>";
	buffer += kanji.misc.at("S");
	buffer += "</td></tr></table>";

	if (config.kanji_components)
	{
		auto parts = split(radical, '\t');
		buffer += "<table class=\"k-bbox-tb\"><tr><td class=\"k-bbox-1a\">";
		buffer += parts.at(0);
		buffer += "</td><td class=\"k-bbox-1b\">";
		buffer += parts.at(2);
		buffer += "</td><td class=\"k-bbox-1b\">";
		buffer += parts.at(3);
		buffer += "</td></tr>";

		char parity = '0';
		for (auto i = 0U; i < radicals.size(); ++i)
		{
			const std::string& radical_i = radicals[i];
			if (i == bn || radical_i.find(kanji.kanji) == std::string::npos)
			{
				continue;
			}
			parts = split(radical_i, '\t');
			buffer += "<tr><td class=\"k-bbox-";
			buffer += parity;
			buffer += "1a\">";
			buffer += parts.at(0);
			buffer += "</td><td class=\"k-bbox-";
			buffer += parity;
			buffer += "1b\">";
			buffer += parts.at(2);
			buffer += "</td><td class=\"k-bbox-";
			buffer += parity;
			buffer += "1b\">";
			buffer += parts.at(3);
			buffer += "</td></tr>";

			parity ^= 0x1;
		}
		buffer += "</table>";
	}

	buffer += "<span class=\"k-kanji\">";
	buffer += kanji.kanji;
	buffer += "</span><br/>";

	buffer += "<div class=\"k-eigo\">";
	buffer += kanji.eigo;
	buffer += "</div>";

	buffer += "<div class=\"k-yomi\">";
	for (auto i = 0U; i < kanji.onkun.size(); ++i)
	{
		if (i > 0)
		{
			buffer += u8"、 ";
		}
		const std::string& onkun = kanji.onkun[i];
		const size_t p = onkun.find('.');
		if (p == std::string::npos)
		{
			buffer += onkun;
		}
		else
		{
			buffer += onkun.substr(0, p);
			buffer += "<span class=\"k-yomi-hi\">";
			buffer += onkun.substr(p + 1);
			buffer += "</span>";
		}
	}
	if (!kanji.nanori.empty())
	{
		buffer += u8"<br/><span class=\"k-yomi-ti\">名乗り</span>";
		buffer += kanji.nanori;
	}
	if (!kanji.bushumei.empty())
	{
		buffer += u8"<br/><span class=\"k-yomi-ti\">部首名</span>";
		buffer += kanji.bushumei;
	}
	buffer += "</div>";

	std::string nums;
	char parity = '1';
	for (auto& kv : kanji_numbers)
	{
		if (config.kanji_info.count(kv.first) == 0)
		{
			continue;
		}

		std::string value = "-";
		auto it = kanji.misc.find(kv.first);
		if (it != kanji.misc.end())
		{
			value = it->second;
		}

		nums += "<tr><td class=\"k-mix-td";
		nums += parity;
		nums += "\">";
		nums += kv.second;
		nums += "</td><td class=\"k-mix-td";
		nums += parity;
		nums += "\">";
		nums += value;
		nums += "</td></tr>";

		parity ^= 0x1;
	}

	buffer += "</td></tr><tr><td>";
	if (!nums.empty())
	{
		buffer += "<table class=\"k-mix-tb\">";
		buffer += nums;
		buffer += "</table>";
	}
	buffer += "</td></tr></table>";
}

inline void conditionaly_add_class(bool add, const std::string_view& class_name)
{
	if (add)
	{
		buffer += ' ';
		buffer += class_name;
	}
}

void entry_to_html(WordResult& word, const std::string& partial = "")
{
	const auto& review_list_entry = config.review_list.find(word.dentry.id());
	bool from_review_list = review_list_entry != config.review_list.end();
	if (!from_review_list && !word.dentry.name())
	{
		buffer += "<div class=\"rikaigu-add-to-review-list\"></div>";
	}

	if (!word.dentry.readings().empty())
	{
		for (auto j = 0U; j < word.dentry.kanji_groups().size(); ++j)
		{
			const KanjiGroup& g = word.dentry.kanji_groups()[j];
			for (auto l = 0U; l < g.kanjis.size(); ++l)
			{
				auto& k = g.kanjis[l];
				if (l > 0)
				{
					buffer += u8"、";
				}
				buffer += "<span class=\"w-kanji";
				conditionaly_add_class(!k.common, "uncommon");
				buffer += "\">";
				buffer += k.text;
				buffer += "</span>";
			}
			buffer += "<span class=\"spacer\"></span>&#32;";

			for (auto l = 0U; l < g.readings.size(); ++l)
			{
				auto& r = word.dentry.readings()[g.readings[l]];
				if (l > 0)
				{
					buffer += u8"、";
				}
				buffer += "<span class=\"w-kana";
				conditionaly_add_class(!r.common, "uncommon");
				conditionaly_add_class(from_review_list, "rikaigu-hidden rikaigu-review-listed");
				buffer += "\">";
				buffer += r.text;
				buffer += "</span>";
			}

			if (j == 0 && !word.reason.empty())
			{
				buffer += " <span class=\"w-conj\">(";
				buffer += word.reason;
				if (!partial.empty())
				{
					buffer += " &lt ";
					buffer += partial;
				}
				buffer += ")</span>";
			}
			buffer += "<br />";
		}
	}
	else
	{
		// TODO can be united (zero kanjiGroups, but some readings)
		for (auto j = 0U; j < word.dentry.kanji_groups().size(); ++j) {
			auto& g = word.dentry.kanji_groups()[j];
			if (j > 0)
			{
				buffer += u8"、";
			}
			buffer += "<span class=\"w-kana";
			assert(g.kanjis.size() > 0);
			conditionaly_add_class(!g.kanjis.at(0).common, "uncommon");
			buffer += "\">";
			buffer += g.kanjis.at(0).text;
			buffer += "</span>";
			if (!word.reason.empty())
			{
				buffer += " <span class=\"w-conj\">(";
				buffer += word.reason;
				if (!partial.empty())
				{
					buffer += " &lt ";
					buffer += partial;
				}
				buffer += ")</span>";
			}
		}
		buffer += "<br />";
	}

	if (from_review_list)
	{
		buffer += "<span class=\"w-review-context rikaigu-review-listed\">";
		buffer += review_list_entry->second;
		buffer += "<br /></span>";
	}

	if (!config.only_reading)
	{
		for (auto sense_group : word.dentry.sense_groups())
		{
			buffer += "<span class=\"w-pos\">";
			for (auto i = 0U; i < sense_group.types.size(); ++i)
			{
				if (i > 0)
				{
					buffer += ", ";
				}
				buffer += sense_group.types[i];
			}
			buffer += "</span>";
			if (sense_group.senses.size() > 1)
			{
				buffer += "<ul class=\"w-def";
				conditionaly_add_class(from_review_list, "rikaigu-hidden rikaigu-review-listed");
				buffer += "\"><li>";
				for (auto i = 0U; i < sense_group.senses.size(); ++i)
				{
					if (i > 0)
					{
						buffer += "</li><li>";
					}
					buffer += sense_group.senses[i];
				}
				buffer += "</li></ul>";
			}
			else
			{
				// TODO? generate readings for names
				assert(sense_group.senses.size() == 1);
				buffer += " <span class=\"w-def";
				conditionaly_add_class(from_review_list, "rikaigu-hidden rikaigu-review-listed");
				buffer += "\">";
				buffer += sense_group.senses.at(0);
				buffer += "</span><br />";
			}
		}
	}
}

void render_entries(SearchResult& result)
{
	if (config.only_reading)
	{
		buffer += "<span class=\"note\">`D` - show definitions</span><div class=\"clearfix\"></div>";
	}

	if (result.names)
	{
		buffer += "<div class=\"w-title\">Names Dictionary</div>";
	}
	buffer += "<table>";

	for (auto i = 0u; i < result.data.size(); ++i)
	{
		buffer += "<tr class=\"";
		if (i > 0)
		{
			buffer += " rikaigu-second-and-further rikaigu-hidden";
		}
		buffer += "\">";

		std::string part;
		if (result.data[i].match_symbols_length < result.max_match_symbols_length)
		{
			part = result.source.substr(0, result.data[i].match_bytes_length);
		}

		buffer += "<td class=\"word";
		if (!result.data[i].expressions.empty())
		{
			buffer += " expression";
		}
		else
		{
			buffer += "\" colspan=\"10";
		}
		buffer += "\" id=";
		buffer += std::to_string(result.data[i].dentry.id());
		buffer += '>';

		entry_to_html(result.data[i], part);
		buffer += "</td>";

		for(auto it = result.data[i].expressions.rbegin(); it != result.data[i].expressions.rend(); ++it)
		{
			buffer += "<td class=\"word expression\" id=";
			buffer += std::to_string(it->dentry.id());
			buffer += ">+";
			WordResult tmp_result(it->dentry, it->reason);
			entry_to_html(tmp_result);
			buffer += "</td>";
		}

		buffer += "</tr>";
	}
	buffer += "</table>";
	if (result.data.size() > 1)
	{
		buffer += u8"<div class=\"rikaigu-lurk-moar\">▼</div>";
	}
}

const char* make_html(SearchResult& result)
{
	PROFILE
	buffer.clear();

	if (!result.kanji.kanji.empty())
	{
		render_kanji(result.kanji);
	}
	else if (!result.data.empty())
	{
		render_entries(result);
	}

	return buffer.c_str();
}
