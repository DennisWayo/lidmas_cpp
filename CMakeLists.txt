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
        include/qec/CSSCode.h
        include/qec/CSSSyndrome.h
        include/qec/LogicalOperators.h
        src/qec/CSSDecoder.cpp
        src/qec/CSSCode.cpp
        src/qec/LogicalOperators.cpp
        src/utils/CSVWriter.cpp
        include/utils/CSVWriter.h
)

target_include_directories(lidmas PRIVATE include)

add_executable(lidmas_surface
        src/surface_main.cpp
        src/core/BinaryMatrix.cpp
        src/decoders/BeliefPropagation.cpp
        src/graph/TannerGraph.cpp
        src/qec/LogicalOperators.cpp
        src/surface/SurfaceLattice.cpp
        src/surface/SurfaceCode.cpp
        src/surface/SurfaceSyndrome.cpp
        src/surface/SurfaceDecoder.cpp
        include/decoders/BeliefPropagation.h
        include/graph/TannerGraph.h
        include/qec/LogicalOperators.h
        include/surface/SurfaceLattice.h
        include/surface/SurfaceCode.h
        include/surface/SurfaceSyndrome.h
        include/surface/SurfaceDecoder.h
)

target_include_directories(lidmas_surface PRIVATE include)

if(OpenMP_CXX_FOUND)
    target_link_libraries(lidmas PRIVATE OpenMP::OpenMP_CXX)
    target_link_libraries(lidmas_surface PRIVATE OpenMP::OpenMP_CXX)
endif()
