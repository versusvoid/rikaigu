#include "utf.h"

#include <stdint.h>
#include <assert.h>

wchar_t decode_utf16_wchar(const char16_t* text)
{
	if ((*text & 0xFC00) == 0xD800)
	{
		wchar_t res = *text - 0xD800;
		res <<= 10;
		res += *(text + 1) - 0xDC00;
		return res + 0x10000;
	}
	else
	{
		return *text;
	}
}

int utf16_compare(const char16_t* a, const size_t alen, const char16_t* b, const size_t blen)
{
	const char16_t* ait = a;
	const char16_t* const aend = a + alen;
	const char16_t* bit = b;
	const char16_t* const bend = b + blen;
	while (ait != aend && bit != bend)
	{
		const wchar_t achar = decode_utf16_wchar(ait);
		const wchar_t bchar = decode_utf16_wchar(bit);

		if (achar < bchar)
		{
			return -1;
		}
		else if (achar > bchar)
		{
			return 1;
		}
		else
		{
			ait += (achar > 0xFFFF) ? 2 : 1;
			bit += (bchar > 0xFFFF) ? 2 : 1;
		}
	}

	return (int)alen - (int)blen;
}

size_t utf16_drop_code_point(const char16_t* data, size_t pos)
{
	assert(pos > 0);
	if ((data[pos - 1] & 0xFC00) == 0xDC00)
	{
		return pos - 2;
	}
	else
	{
		return pos - 1;
	}
}

// Katakana -> hiragana conversion tables
static const char16_t half_width_katakana_mapping[] = {
	u'を',
	u'ぁ', u'ぃ', u'ぅ', u'ぇ', u'ぉ',
	u'ゃ', u'ゅ', u'ょ',
	u'っ', u'ー',
	u'あ', u'い', u'う', u'え', u'お',
	u'か', u'き', u'く', u'け', u'こ',
	u'さ', u'し', u'す', u'せ', u'そ',
	u'た', u'ち', u'つ', u'て', u'と',
	u'な', u'に', u'ぬ', u'ね', u'の',
	u'は', u'ひ', u'ふ', u'へ', u'ほ',
	u'ま', u'み', u'む', u'め', u'も',
	u'や', u'ゆ', u'よ',
	u'ら', u'り', u'る', u'れ', u'ろ',
	u'わ', u'ん',
};

static const char16_t voiced_mapping_min = u'う';
static const char16_t voiced_mapping_max = u'ほ';
static const char16_t voiced_mapping[] = {
	/*う:*/u'ゔ', /*ぇ:*/u'ぇ', /*え:*/u'え', /*ぉ:*/u'ぉ', /*お:*/u'お',

	/*か:*/u'が', /*が:*/u'が',
	/*き:*/u'ぎ', /*ぎ:*/u'ぎ',
	/*く:*/u'ぐ', /*ぐ:*/u'ぐ',
	/*け:*/u'げ', /*げ:*/u'げ',
	/*こ:*/u'ご', /*ご:*/u'ご',

	/*さ:*/u'ざ', /*ざ:*/u'ざ',
	/*し:*/u'じ', /*じ:*/u'じ',
	/*す:*/u'ず', /*ず:*/u'ず',
	/*せ:*/u'ぜ', /*ぜ:*/u'ぜ',
	/*そ:*/u'ぞ', /*ぞ:*/u'ぞ',

	/*た:*/u'だ', /*だ:*/u'だ',
	/*ち:*/u'ぢ', /*ぢ:*/u'ぢ',
	/*っ:*/u'っ', /*つ:*/u'づ', /*づ:*/u'づ',
	/*て:*/u'で', /*で:*/u'で',
	/*と:*/u'ど', /*ど:*/u'ど',

	/*な:*/u'な', /*に:*/u'に', /*ぬ:*/u'ぬ', /*ね:*/u'ね', /*の:*/u'の',

	/*は:*/u'ば', /*ば:*/u'ば', /*ぱ:*/u'ぱ',
	/*ひ:*/u'び', /*び:*/u'び', /*ぴ:*/u'ぴ',
	/*ふ:*/u'ぶ', /*ぶ:*/u'ぶ', /*ぷ:*/u'ぷ',
	/*へ:*/u'べ', /*べ:*/u'べ', /*ぺ:*/u'ぺ',
	/*ほ:*/u'ぼ',
};

static const char16_t half_voiced_mapping_min = u'は';
static const char16_t half_voiced_mapping_max = u'ほ';
static const char16_t half_voiced_mapping[] = {
	/*は:*/u'ぱ', /*ば:*/u'ば', /*ぱ:*/u'ぱ',
	/*ひ:*/u'ぴ', /*び:*/u'び', /*ぴ:*/u'ぴ',
	/*ふ:*/u'ぷ', /*ぶ:*/u'ぶ', /*ぷ:*/u'ぷ',
	/*へ:*/u'ぺ', /*べ:*/u'べ', /*ぺ:*/u'ぺ',
	/*ほ:*/u'ぽ',
};

static const char16_t long_vowel_mark_mapping_min = u'ぁ';
static const char16_t long_vowel_mark_mapping_max = u'ゔ';
static const char16_t long_vowel_mark_mapping[] = {
	/*ぁ:*/u'ー', /*あ:*/u'あ',
	/*ぃ:*/u'ー', /*い:*/u'い',
	/*ぅ:*/u'ー', /*う:*/u'う',
	/*ぇ:*/u'ー', /*え:*/u'い',
	/*ぉ:*/u'ー', /*お:*/u'う',

	/*か:*/u'あ', /*が:*/u'あ',
	/*き:*/u'い', /*ぎ:*/u'い',
	/*く:*/u'う', /*ぐ:*/u'う',
	/*け:*/u'い', /*げ:*/u'い',
	/*こ:*/u'う', /*ご:*/u'う',

	/*さ:*/u'あ', /*ざ:*/u'あ',
	/*し:*/u'い', /*じ:*/u'い',
	/*す:*/u'う', /*ず:*/u'う',
	/*せ:*/u'い', /*ぜ:*/u'い',
	/*そ:*/u'う', /*ぞ:*/u'う',

	/*た:*/u'あ', /*だ:*/u'あ',
	/*ち:*/u'い', /*ぢ:*/u'い',
	/*っ:*/u'ー', /*つ:*/u'う', /*づ:*/u'う',
	/*て:*/u'い', /*で:*/u'い',
	/*と:*/u'う', /*ど:*/u'う',

	/*な:*/u'あ', /*に:*/u'い', /*ぬ:*/u'う', /*ね:*/u'い', /*の:*/u'う',

	/*は:*/u'あ', /*ば:*/u'あ', /*ぱ:*/u'あ',
	/*ひ:*/u'い', /*び:*/u'い', /*ぴ:*/u'い',
	/*ふ:*/u'う', /*ぶ:*/u'う', /*ぷ:*/u'う',
	/*へ:*/u'い', /*べ:*/u'い', /*ぺ:*/u'い',
	/*ほ:*/u'う', /*ぼ:*/u'う', /*ぽ:*/u'う',

	/*ま:*/u'あ', /*み:*/u'い', /*む:*/u'う', /*め:*/u'い', /*も:*/u'う',

	/*ゃ:*/u'あ', /*や:*/u'あ',
	/*ゅ:*/u'う', /*ゆ:*/u'う',
	/*ょ:*/u'う', /*よ:*/u'う',

	/*ら:*/u'あ', /*り:*/u'い', /*る:*/u'う', /*れ:*/u'い', /*ろ:*/u'う',
	/*ゎ:*/u'ー', /*わ:*/u'あ', /*ゐ:*/u'い', /*ゑ:*/u'い', /*を:*/u'ー',

	/*ん:*/u'ー',
	/*ゔ:*/u'ー',
};

static const uint32_t replace_flag = (1<<16);
uint32_t kata_to_hira_character(const char16_t c, const char16_t previous)
{
	// Full-width katakana to hiragana
	if (c >= u'ァ' && c <= u'ヶ')
	{
		return c - u'ァ' + u'ぁ';
	}
	// Half-width katakana to hiragana
	else if (c >= u'ｦ' && c <= u'ﾝ')
	{
		return half_width_katakana_mapping[c - u'ｦ'];
	}
	// Voiced (used in half-width katakana) to hiragana
	else if (c == u'ﾞ')
	{
		if (previous >= voiced_mapping_min && previous <= voiced_mapping_max)
		{
			return voiced_mapping[previous - voiced_mapping_min] | replace_flag;
		}
	}
	// Half-voiced (used in half-width katakana) to hiragana
	else if (c == u'ﾟ')
	{
		if (previous >= half_voiced_mapping_min && previous <= half_voiced_mapping_max)
		{
			return half_voiced_mapping[previous - half_voiced_mapping_min] | replace_flag;
		}
	}
	else if (c == u'ー' || c == u'ｰ' /* it's actually half-width long vowel mark U+ff70 */)
	{
		if (previous >= long_vowel_mark_mapping_min && previous <= long_vowel_mark_mapping_max)
		{
			return long_vowel_mark_mapping[previous - long_vowel_mark_mapping_min];
		}
	}
	return c;
}

void input_kata_to_hira(input_t* input)
{
	size_t previous = 0;

	size_t out_length = 0;
	for (size_t i = 0; i < input->length; ++i)
	{
		uint32_t converted = kata_to_hira_character(input->data[i], previous);
		if ((converted & replace_flag) != 0)
		{
			assert(out_length > 0);
			input->data[out_length - 1] = (converted & 0xFFFF);
			input->length_mapping[out_length] = i + 1;
		}
		else
		{
			input->data[out_length] = (char16_t)converted;
			input->length_mapping[out_length + 1] = i + 1;
			out_length += 1;
		}
		previous = converted;
	}
	input->length = out_length;
}
