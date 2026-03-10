#include "sim/GpuBench.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <random>
#include <string>
#include <vector>

#include "gpu/SurfaceGpuSampler.h"
#include "surface/SurfaceCode.h"

namespace {

uint64_t mix64(uint64_t x) {
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return x;
}

uint64_t thresholdTrialSeed(uint64_t base_seed,
                            int d,
                            int p_key,
                            long long trial_index,
                            int thread_id) {
    uint64_t s = base_seed;
    s ^= mix64(static_cast<uint64_t>(d) + 0x9e3779b97f4a7c15ULL);
    s ^= mix64(static_cast<uint64_t>(p_key) + 0x94d049bb133111ebULL);
    s ^= mix64(static_cast<uint64_t>(trial_index) + 0xbf58476d1ce4e5b9ULL);
    s ^= mix64(static_cast<uint64_t>(thread_id) + 0x27d4eb2f165667c5ULL);
    return mix64(s);
}

std::vector<std::vector<int>> buildSparseRows(const BinaryMatrix& H) {
    std::vector<std::vector<int>> rows(static_cast<size_t>(H.rows()));
    for (int r = 0; r < H.rows(); ++r) {
        auto& row = rows[static_cast<size_t>(r)];
        row.reserve(static_cast<size_t>(H.cols() / 8 + 1));
        for (int c = 0; c < H.cols(); ++c) {
            if ((H.get(r, c) & 1) != 0) row.push_back(c);
        }
    }
    return rows;
}

long long cpu_sample_batch(const SurfaceCode& code,
                           const std::vector<std::vector<int>>& hz_rows,
                           double p,
                           uint64_t seed_base,
                           int d,
                           int p_key,
                           long long start_trial,
                           int batch_trials) {
    const int n = code.n();
    std::vector<int> ex(static_cast<size_t>(n), 0);
    const double pc = std::clamp(p, 0.0, 1.0);

    long long defect_sum = 0;
    for (int i = 0; i < batch_trials; ++i) {
        const long long t = start_trial + i;
        const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, t, 0);
        std::mt19937_64 rng(seed);
        std::bernoulli_distribution x_flip(pc);
        std::bernoulli_distribution z_flip(pc);

        for (int q = 0; q < n; ++q) {
            ex[static_cast<size_t>(q)] = x_flip(rng) ? 1 : 0;
            (void)z_flip(rng);
        }

        for (const auto& row : hz_rows) {
            int parity = 0;
            for (int c : row) parity ^= (ex[static_cast<size_t>(c)] & 1);
            defect_sum += (parity & 1);
        }
    }

    return defect_sum;
}

} // namespace

int run_gpu_bench(int d, int trials, int batch_trials, double p, uint64_t seed) {
    if (trials <= 0 || batch_trials <= 0) {
        std::cerr << "gpu_bench: trials and batch_trials must be > 0\n";
        return 1;
    }

    SurfaceCode code(d);
    const auto hz_rows = buildSparseRows(code.Hz());
    const int p_key = static_cast<int>(std::llround(p * 1e6));

    std::cout << "gpu_bench: d=" << d
              << " p=" << p
              << " trials=" << trials
              << " batch=" << batch_trials
              << "\n";

    const auto cpu_start = std::chrono::high_resolution_clock::now();
    long long cpu_defects = 0;
    for (int start = 0; start < trials; start += batch_trials) {
        const int batch = std::min(batch_trials, trials - start);
        cpu_defects += cpu_sample_batch(code, hz_rows, p, seed, d, p_key, start, batch);
    }
    const auto cpu_end = std::chrono::high_resolution_clock::now();
    const double cpu_ms = std::chrono::duration<double, std::milli>(cpu_end - cpu_start).count();

    if (!gpu::is_available()) {
        std::cerr << "gpu_bench: no CUDA device detected\n";
        std::cout << "cpu_sampling_ms=" << cpu_ms << " defects=" << cpu_defects << "\n";
        return 1;
    }

    gpu::DeviceInfo info;
    std::string info_error;
    if (gpu::get_device_info(&info, &info_error)) {
        const double mem_gb = static_cast<double>(info.global_mem_bytes) / (1024.0 * 1024.0 * 1024.0);
        std::cout << "gpu_device=" << info.name
                  << " cc=" << info.major << "." << info.minor
                  << " sm=" << info.multiprocessor_count
                  << " vram_gb=" << mem_gb << "\n";
    } else {
        std::cout << "gpu_device=" << gpu::device_name() << " info_error=" << info_error << "\n";
    }

    std::string gpu_error;
    gpu::SurfaceGpuSampler sampler(code.n(), hz_rows, &gpu_error);
    if (!sampler.ok()) {
        std::cerr << "gpu_bench: CUDA sampler init failed: " << gpu_error << "\n";
        std::cout << "cpu_sampling_ms=" << cpu_ms << " defects=" << cpu_defects << "\n";
        return 1;
    }

    const auto gpu_start = std::chrono::high_resolution_clock::now();
    long long gpu_defects = 0;
    std::vector<unsigned char> ex_batch;
    std::vector<unsigned char> sz_batch;
    for (int start = 0; start < trials; start += batch_trials) {
        const int batch = std::min(batch_trials, trials - start);
        if (!sampler.sample_pauli_batch(p, seed, d, p_key, start, batch, ex_batch, sz_batch, &gpu_error)) {
            std::cerr << "gpu_bench: CUDA sampling failed: " << gpu_error << "\n";
            return 1;
        }
        for (unsigned char v : sz_batch) gpu_defects += static_cast<long long>(v & 1u);
    }
    const auto gpu_end = std::chrono::high_resolution_clock::now();
    const double gpu_ms = std::chrono::duration<double, std::milli>(gpu_end - gpu_start).count();

    const double speedup = (gpu_ms > 0.0) ? (cpu_ms / gpu_ms) : 0.0;
    std::cout << "cpu_sampling_ms=" << cpu_ms << " defects=" << cpu_defects << "\n";
    std::cout << "gpu_sampling_ms=" << gpu_ms << " defects=" << gpu_defects
              << " speedup=" << speedup << "x\n";
    return 0;
}
