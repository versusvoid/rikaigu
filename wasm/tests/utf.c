
#include "../src/utf.c"

void test_decode_utf16_wchar()
{
	const char16_t single[] = { 0x20AC };
	assert(decode_utf16_wchar(single) == 0x20AC);

	const char16_t surrogate[] = { 0xD852, 0xDF62 };
	assert(decode_utf16_wchar(surrogate) == 0x24B62);

	const char16_t le_check[] = u"你";
	assert(decode_utf16_wchar(le_check) == 0x2F804);
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

int main()
{
	test_decode_utf16_wchar();
	test_utf16_compare();
	test_utf16_drop_code_point();

	return 0;
}
