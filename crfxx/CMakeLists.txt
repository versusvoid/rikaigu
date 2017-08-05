cmake_minimum_required(VERSION 2.8)
project(crfxx)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --std=c++14 -Wall -Werror")
set(CMAKE_CXX_FLAGS_DEBUG "-ggdb -Og")
set(CMAKE_CXX_FLAGS_RELEASE "-O3")

if ("${CMAKE_SYSTEM_NAME}" STREQUAL Emscripten)
	message("Compiler is ${CMAKE_CXX_COMPILER}")
	add_library(crfxx include/api.h src/api.cpp src/encode.cpp src/encode.h)
else()
	set(CMAKE_THREAD_PREFER_PTHREAD TRUE)
	set(THREADS_PREFER_PTHREAD_FLAG TRUE)
	find_package(Threads REQUIRED)

	add_executable(train-crf src/common.hpp src/train.cpp
		src/encode.cpp src/encode.h
		src/utf16.h src/utf16.cpp
		src/lbfgs.h src/lbfgs.cpp)
	target_link_libraries(train-crf Threads::Threads)

	add_executable(test-crf src/common.hpp src/test.cpp
		src/encode.cpp src/encode.h
		src/utf16.h src/utf16.cpp)

	#SET(DLIB_NO_GUI_SUPPORT ON CACHE BOOL "No gui" FORCE)
	#SET(USE_AVX_INSTRUCTIONS ON CACHE BOOL "Use avx" FORCE)
	#set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mavx")
	#include(/usr/include/dlib/cmake)
	#add_executable(neural neural.cpp utf16.cpp)
	#target_link_libraries(neural dlib::dlib)

	#add_executable(xgb-extract extract-xgboost.cpp utf16.cpp)
	#target_link_libraries(xgb-extract -lxgboost)

	#add_executable(xgb-test test-xgboost.cpp utf16.cpp)
	#target_link_libraries(xgb-test -lxgboost)
endif()
