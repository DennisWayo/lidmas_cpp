cmake_minimum_required(VERSION 3.16)
project(lidmas_cpp)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(lidmas
        src/main.cpp
        src/core/BinaryMatrix.cpp
        src/decoders/BeliefPropagation.cpp
        src/utils/Channel.cpp
        include/sim/MonteCarlo.h
        src/sim/MonteCarlo.cpp
)

target_include_directories(lidmas PRIVATE include)