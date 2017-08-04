cmake_minimum_required(VERSION 2.8)
project(crfxx)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --std=c++14 -Wall -Werror")
set(CMAKE_CXX_FLAGS_DEBUG "-ggdb -Og")
set(CMAKE_CXX_FLAGS_RELEASE "-O3")

if ("${CMAKE_SYSTEM_NAME}" STREQUAL Emscripten)
    message("Compiler is ${CMAKE_CXX_COMPILER}")
    add_library(crfxx utf16.cpp lbfgs.cpp)
else()
    add_executable(train main.cpp utf16.h utf16.cpp lbfgs.h lbfgs.cpp)
    #SET(DLIB_NO_GUI_SUPPORT ON CACHE BOOL "No gui" FORCE)
    #SET(USE_AVX_INSTRUCTIONS ON CACHE BOOL "Use avx" FORCE)
    #include(/usr/include/dlib/cmake)
    #add_executable(neural neural.cpp utf16.cpp)
    #target_link_libraries(neural dlib::dlib)

    add_executable(xgb-extract extract-xgboost.cpp utf16.cpp)
    target_link_libraries(xgb-extract -lxgboost)

    add_executable(xgb-test test-xgboost.cpp utf16.cpp)
    target_link_libraries(xgb-test -lxgboost)

    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread -mavx")
endif()
