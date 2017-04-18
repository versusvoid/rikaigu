cmake_minimum_required(VERSION 2.8)

project(crfxx)
add_executable(${PROJECT_NAME} main.cpp lbfgs.cpp)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread -mavx -Wall -Werror")
set(CMAKE_CXX_FLAGS_DEBUG "-ggdb -Og")
#TARGET_LINK_LIBRARIES ( ${PROJECT_NAME} pthread )
