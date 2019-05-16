
#include "../src/utf.c"

void test_decode_utf16_wchar()
{
	const char16_t single[] = { 0x20AC };
	const char16_t* p = single;
	assert(decode_utf16_wchar(&p) == 0x20AC);
	assert(p == single + 1);

	const char16_t surrogate[] = { 0xD852, 0xDF62 };
	p = surrogate;
	assert(decode_utf16_wchar(&p) == 0x24B62);
	assert(p == surrogate + 2);

	const char16_t le_check[] = u"你";
	p = le_check;
	assert(decode_utf16_wchar(&p) == 0x2F804);
	assert(p == le_check + 2);
}

void test_utf16_compare()
{
	const char16_t a1[] = u"ｵｶｷｸｹｺ"; // 0xFF**
	const char16_t b1[] = u"櫛桒你"; // surrogates
	assert(utf16_compare(a1, sizeof(a1) / sizeof(char16_t) - 1, b1, sizeof(b1) / sizeof(char16_t) - 1) < 0);

	const char16_t a2[] = u"ｵｶｷｸｹｺ";
	const char16_t b2[] = u"ｵｶｷ櫛";
	assert(utf16_compare(a2, sizeof(a2) / sizeof(char16_t) - 1, b2, sizeof(b2) / sizeof(char16_t) - 1) < 0);

	const char16_t a3[] = u"ｵｶｷｸｹｺ";
	const char16_t b3[] = u"ｵｶｷ";
	assert(utf16_compare(a3, sizeof(a3) / sizeof(char16_t) - 1, b3, sizeof(b3) / sizeof(char16_t) - 1) > 0);

	const char16_t a4[] = u"櫛了ｵ";
	const char16_t b4[] = u"櫛了ｵ";
	assert(utf16_compare(a4, sizeof(a4) / sizeof(char16_t) - 1, b4, sizeof(b4) / sizeof(char16_t) - 1) == 0);
}

void test_utf16_drop_code_point()
{
	const char16_t s1[] = u"ｵｶｷｸｹｺ";
	assert(utf16_drop_code_point(s1, 4) == 3);

	const char16_t s2[] = u"櫛桒你"; // surrogates
	assert(utf16_drop_code_point(s2, 4) == 2);
}

void test_decode_utf8_wchar()
{
	const char single[] = u8"a";
	const char* p = single;
	assert(decode_utf8_wchar(&p) == 'a');
	assert(p == single + 1);

	const char pair[] = u8"¢";
	p = pair;
	assert(decode_utf8_wchar(&p) == L'¢');
	assert(p == pair + 2);

	const char triple[] = u8"€";
	p = triple;
	assert(decode_utf8_wchar(&p) == L'€');
	assert(p == triple + 3);

	const char quadriple[] = u8"𐍈";
	p = quadriple;
	assert(decode_utf8_wchar(&p) == L'𐍈');
	assert(p == quadriple + 4);
}

void test_utf16_utf8_kata_to_hira_eq()
{
	const char16_t key[] = u"すぴいか";
	const char utf8[] = u8"スピーカ";
	assert(utf16_utf8_kata_to_hira_eq(key, 4, utf8, sizeof(utf8) - 1));

	const char16_t key2[] = u"すぴいか𐍈";
	assert(!utf16_utf8_kata_to_hira_eq(key, sizeof(key2) - 1, utf8, sizeof(utf8) - 1));

	const char utf8_2[] = u8"ｽﾋﾟｰｶ";
	// This function does not handle replaces in utf8
	// but there is none in dictionary
	assert(!utf16_utf8_kata_to_hira_eq(key, 4, utf8_2, sizeof(utf8_2) - 1));
}

int main()
{
	test_decode_utf16_wchar();
	test_utf16_compare();
	test_utf16_drop_code_point();
	test_decode_utf8_wchar();
	test_utf16_utf8_kata_to_hira_eq();

	return 0;
}
