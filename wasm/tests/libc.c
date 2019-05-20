#include <assert.h>
#include <string.h>

#include "fake-memory.h"
#include "../src/libc.c"
#include "../src/utf.c"

void test_memcpy(void* (*f)(void*, const void*, size_t))
{
	const char a[] = {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
	char b[sizeof(a)] = {0};
	assert(sizeof(b) == 16);

	const char expected0[] = {0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0};
	assert(sizeof(b) == sizeof(expected0));
	assert(memcmp(b, expected0, sizeof(b)) == 0);

	f(b, a, 3);
	const char expected1[] = {1,2,3,0, 0,0,0,0, 0,0,0,0, 0,0,0,0};
	assert(sizeof(b) == sizeof(expected1));
	assert(memcmp(b, expected1, sizeof(b)) == 0);

	memset(b, 0, sizeof(b));
	f(b, a, 11);
	const char expected2[] = {1,2,3,4,5,6,7,8,9,10,11,0, 0,0,0,0};
	assert(sizeof(b) == sizeof(expected2));
	assert(memcmp(b, expected2, sizeof(b)) == 0);

	memset(b, 0, sizeof(b));
	f(b, a, 16);
	assert(memcmp(b, a, sizeof(b)) == 0);
}

void test_memmove()
{
	char a[] = {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
	assert(sizeof(a) == 16);
	memmove(a + 3, a, 5);

	const char expected1[] = {1,2,3,1,2,3,4,5,9,10,11,12,13,14,15,16};
	assert(sizeof(a) == sizeof(expected1));
	assert(memcmp(a, expected1, sizeof(a)) == 0);

	memmove(a + 6, a + 1, 9);
	const char expected2[] = {1,2,3,1,2,3,2,3,1,2,3,4,5,9,10,16};
	assert(sizeof(a) == sizeof(expected2));
	assert(memcmp(a, expected2, sizeof(a)) == 0);
}

void test_memzero()
{
	char a[] = {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
	assert(sizeof(a) == 16);

	memzero(a, 3);
	const char expected1[] = {0,0,0,4,5,6,7,8,9,10,11,12,13,14,15,16};
	assert(sizeof(a) == sizeof(expected1));
	assert(memcmp(a, expected1, sizeof(a)) == 0);

	memzero(a, 16);
	const char expected2[] = {0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0};
	assert(sizeof(a) == sizeof(expected2));
	assert(memcmp(a, expected2, sizeof(a)) == 0);
}

int main()
{
	test_memcpy(memcpy);
	test_memcpy(memcpy_backward);
	test_memmove();
	test_memzero();
}
