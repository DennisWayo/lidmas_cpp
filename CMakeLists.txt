cmake_minimum_required(VERSION 3.16)
project(lidmas_cpp)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(OpenMP)

add_executable(lidmas
        src/main.cpp
        src/core/BinaryMatrix.cpp
        src/core/PluginRegistry.cpp
        src/core/DecoderRegistry.cpp
        src/core/RegisterDecoders.cpp
        src/core/RegisterPlugins.cpp
        src/decoders/BPDecoderAdapter.cpp
        src/decoders/UnionFindDecoder.cpp
        src/decoders/BeliefPropagation.cpp
        src/models/NeuralWeightModel.cpp
        src/UniformWeightField.cpp
        src/NeuralWeightField.cpp
        src/LLRWeightField.cpp
        include/core/DecoderConfig.h
        include/core/IDecoderPlugin.h
        include/core/PluginRegistry.h
        include/core/DecoderRegistry.h
        include/core/RegisterDecoders.h
        include/core/RegisterPlugins.h
        include/decoders/IDecoder.h
        include/decoders/BPDecoderAdapter.h
        src/utils/Channel.cpp
        src/utils/BSCChannel.cpp
        src/utils/SyndromeUtils.cpp
        include/utils/IChannel.h
        include/utils/BSCChannel.h
        include/utils/SyndromeUtils.h
        include/utils/SeedUtils.h
        include/sim/MonteCarlo.h
        src/sim/MonteCarlo.cpp
        include/sim/LDPCSimulation.h
        src/sim/LDPCSimulation.cpp
        include/sim/CSSSimulation.h
        src/sim/CSSSimulation.cpp
        include/sim/SurfaceSimulation.h
        src/sim/SurfaceSimulation.cpp
        include/sim/SurfaceThresholdRunner.h
        src/sim/SurfaceThresholdRunner.cpp
        include/sim/SmokeTests.h
        src/sim/SmokeTests.cpp
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
        include/qec/IQECChannel.h
        include/qec/PauliChannel.h
        include/qec/PauliChannelAdapter.h
        include/qec/LogicalOperators.h
        include/qec/QuantumCSSSimulator.h
        src/qec/CSSDecoder.cpp
        src/qec/CSSCode.cpp
        src/qec/CSSSyndrome.cpp
        src/qec/PauliChannel.cpp
        src/qec/PauliChannelAdapter.cpp
        src/qec/LogicalOperators.cpp
        src/qec/QuantumCSSSimulator.cpp
        include/surface/SurfaceLattice.h
        src/surface/SurfaceLattice.cpp
        include/surface/SurfaceCode.h
        src/surface/SurfaceCode.cpp
        include/surface/SurfaceSyndrome.h
        src/surface/SurfaceSyndrome.cpp
        include/surface/SurfaceCorrection.h
        include/surface/SyndromeGraph.h
        src/surface/SyndromeGraph.cpp
        include/surface/MatchingProblem.h
        src/surface/MatchingProblem.cpp
        include/surface/ISurfaceDecoder.h
        include/surface/ISurfaceDecoderPlugin.h
        include/surface/SurfaceDecoderAdapter.h
        src/surface/SurfaceDecoderAdapter.cpp
        include/surface/SurfacePipeline.h
        src/surface/SurfacePipeline.cpp
        include/surface/MWPMStubDecoder.h
        src/surface/MWPMStubDecoder.cpp
        include/surface/BlossomMWPM.h
        src/surface/BlossomMWPM.cpp
        include/surface/MWPMDecoder.h
        src/surface/MWPMDecoder.cpp
        include/surface/UnionFindDecoder.h
        src/surface/UnionFindDecoder.cpp
        include/plugins/stub/StubSurfacePlugin.h
        src/plugins/stub/StubSurfacePlugin.cpp
        include/plugins/mwpm/MWPMPlugin.h
        src/plugins/mwpm/MWPMPlugin.cpp
        include/plugins/uf/UnionFindPlugin.h
        src/plugins/uf/UnionFindPlugin.cpp
        include/plugins/neural/NeuralWeightModel.h
        src/plugins/neural/NeuralWeightModel.cpp
        include/plugins/neural/NeuralMWPMPlugin.h
        src/plugins/neural/NeuralMWPMPlugin.cpp
        src/utils/CSVWriter.cpp
        include/utils/CSVWriter.h
)

target_include_directories(lidmas PRIVATE include src)

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
    message(STATUS "OpenMP found via find_package")
    target_link_libraries(lidmas PRIVATE OpenMP::OpenMP_CXX)
    target_link_libraries(lidmas_surface PRIVATE OpenMP::OpenMP_CXX)
endif()

if(NOT OpenMP_CXX_FOUND AND APPLE)
    message(STATUS "Attempting macOS Homebrew libomp fallback...")

    set(LIBOMP_PREFIX "/opt/homebrew/opt/libomp")

    if(EXISTS "${LIBOMP_PREFIX}/lib/libomp.dylib")
        message(STATUS "Found Homebrew libomp at ${LIBOMP_PREFIX}")

        target_compile_options(lidmas PRIVATE -Xpreprocessor -fopenmp)
        target_compile_options(lidmas_surface PRIVATE -Xpreprocessor -fopenmp)

        target_include_directories(lidmas PRIVATE ${LIBOMP_PREFIX}/include)
        target_include_directories(lidmas_surface PRIVATE ${LIBOMP_PREFIX}/include)

        target_link_libraries(lidmas PRIVATE ${LIBOMP_PREFIX}/lib/libomp.dylib)
        target_link_libraries(lidmas_surface PRIVATE ${LIBOMP_PREFIX}/lib/libomp.dylib)

        target_compile_definitions(lidmas PRIVATE LIDMAS_OPENMP_ENABLED)
        target_compile_definitions(lidmas_surface PRIVATE LIDMAS_OPENMP_ENABLED)
    else()
        message(WARNING "Homebrew libomp not found. Running single-threaded.")
    endif()
endif()
