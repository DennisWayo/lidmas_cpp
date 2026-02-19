cmake_minimum_required(VERSION 3.16)
project(lidmas_cpp)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(OpenMP)

add_executable(lidmas
        src/main.cpp
        src/core/BinaryMatrix.cpp
        src/decoders/BeliefPropagation.cpp
        src/utils/Channel.cpp
        include/sim/MonteCarlo.h
        src/sim/MonteCarlo.cpp
        include/graph/TannerGraph.h
        src/graph/TannerGraph.cpp
        include/graph/GraphDiagnostics.h
        src/graph/GraphDiagnostics.cpp
        include/decoders/BeliefPropagation.h
        src/codes/LDPCGenerator.cpp
        include/codes/LDPCGenerator.h
        include/qec/CSSDecoder.h
        src/qec/CSSDecoder.cpp
        src/utils/CSVWriter.cpp
        include/utils/CSVWriter.h
)

target_include_directories(lidmas PRIVATE include)

if(OpenMP_CXX_FOUND)
    target_link_libraries(lidmas PRIVATE OpenMP::OpenMP_CXX)
endif()
