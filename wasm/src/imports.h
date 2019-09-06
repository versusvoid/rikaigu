#pragma once
#include <stddef.h>
#include <stdint.h>
#include <uchar.h>
#include <stdnoreturn.h>

#include "dentry.h"

extern noreturn void take_a_trip(const char* message);

extern void print(const char* message);
