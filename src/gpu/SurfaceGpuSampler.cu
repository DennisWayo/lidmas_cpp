#include "gpu/SurfaceGpuSampler.h"

#include <algorithm>
#include <cstdio>
#include <sstream>

#include <cuda_runtime.h>
#include <curand_kernel.h>

namespace gpu {

namespace {

__host__ __device__ inline uint64_t mix64(uint64_t x) {
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return x;
}

__host__ __device__ inline uint64_t thresholdTrialSeedDevice(uint64_t base_seed,
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

__global__ void generate_ex_kernel(unsigned char* ex,
                                   int n,
                                   int batch,
                                   double p,
                                   uint64_t seed_base,
                                   int d,
                                   int p_key,
                                   long long start_trial) {
    const int idx = blockIdx.x * blockDim.x + threadIdx.x;
    const int total = batch * n;
    if (idx >= total) return;
    const int trial = idx / n;
    const int q = idx - trial * n;
    const long long trial_index = start_trial + static_cast<long long>(trial);
    const uint64_t seed = thresholdTrialSeedDevice(seed_base, d, p_key, trial_index, 0);
    curandStatePhilox4_32_10_t state;
    curand_init(seed, static_cast<uint64_t>(idx), 0ULL, &state);
    const float u = curand_uniform(&state);
    ex[idx] = (u < p) ? 1u : 0u;
}

__global__ void compute_sz_kernel(const unsigned char* ex,
                                  unsigned char* sz,
                                  const int* row_ptr,
                                  const int* col_idx,
                                  int n,
                                  int m,
                                  int batch) {
    const int idx = blockIdx.x * blockDim.x + threadIdx.x;
    const int total = batch * m;
    if (idx >= total) return;
    const int trial = idx / m;
    const int row = idx - trial * m;
    const int start = row_ptr[row];
    const int end = row_ptr[row + 1];
    int parity = 0;
    const unsigned char* ex_row = ex + static_cast<size_t>(trial) * static_cast<size_t>(n);
    for (int j = start; j < end; ++j) {
        parity ^= static_cast<int>(ex_row[col_idx[j]] & 1u);
    }
    sz[idx] = static_cast<unsigned char>(parity & 1);
}

bool checkCuda(cudaError_t err, std::string* error, const char* context) {
    if (err == cudaSuccess) return true;
    if (error != nullptr) {
        std::ostringstream oss;
        oss << context << ": " << cudaGetErrorString(err);
        *error = oss.str();
    }
    return false;
}

} // namespace

struct SurfaceGpuSampler::Impl {
    int n = 0;
    int m = 0;
    int nnz = 0;
    int* d_row_ptr = nullptr;
    int* d_col_idx = nullptr;
    bool ok = false;
};

SurfaceGpuSampler::SurfaceGpuSampler(int n, const std::vector<std::vector<int>>& hz_rows, std::string* error) {
    impl_ = new Impl();
    impl_->n = n;
    impl_->m = static_cast<int>(hz_rows.size());

    std::vector<int> row_ptr(static_cast<size_t>(impl_->m) + 1, 0);
    int nnz = 0;
    for (int r = 0; r < impl_->m; ++r) {
        row_ptr[static_cast<size_t>(r)] = nnz;
        nnz += static_cast<int>(hz_rows[static_cast<size_t>(r)].size());
    }
    row_ptr[static_cast<size_t>(impl_->m)] = nnz;
    impl_->nnz = nnz;

    std::vector<int> col_idx(static_cast<size_t>(nnz));
    int cursor = 0;
    for (int r = 0; r < impl_->m; ++r) {
        for (int c : hz_rows[static_cast<size_t>(r)]) {
            col_idx[static_cast<size_t>(cursor++)] = c;
        }
    }

    if (!checkCuda(cudaMalloc(reinterpret_cast<void**>(&impl_->d_row_ptr),
                              sizeof(int) * row_ptr.size()), error, "cudaMalloc row_ptr")) {
        return;
    }
    if (!checkCuda(cudaMalloc(reinterpret_cast<void**>(&impl_->d_col_idx),
                              sizeof(int) * col_idx.size()), error, "cudaMalloc col_idx")) {
        return;
    }

    if (!checkCuda(cudaMemcpy(impl_->d_row_ptr, row_ptr.data(),
                              sizeof(int) * row_ptr.size(), cudaMemcpyHostToDevice),
                   error, "cudaMemcpy row_ptr")) {
        return;
    }
    if (!checkCuda(cudaMemcpy(impl_->d_col_idx, col_idx.data(),
                              sizeof(int) * col_idx.size(), cudaMemcpyHostToDevice),
                   error, "cudaMemcpy col_idx")) {
        return;
    }

    impl_->ok = true;
}

SurfaceGpuSampler::~SurfaceGpuSampler() {
    if (impl_ != nullptr) {
        if (impl_->d_row_ptr != nullptr) cudaFree(impl_->d_row_ptr);
        if (impl_->d_col_idx != nullptr) cudaFree(impl_->d_col_idx);
        delete impl_;
    }
}

bool SurfaceGpuSampler::ok() const {
    return impl_ != nullptr && impl_->ok;
}

int SurfaceGpuSampler::n() const {
    return impl_ ? impl_->n : 0;
}

int SurfaceGpuSampler::m() const {
    return impl_ ? impl_->m : 0;
}

bool SurfaceGpuSampler::sample_pauli_batch(double p,
                                           uint64_t seed_base,
                                           int d,
                                           int p_key,
                                           long long start_trial,
                                           int batch_trials,
                                           std::vector<unsigned char>& ex_out,
                                           std::vector<unsigned char>& sz_out,
                                           std::string* error) {
    if (!ok()) {
        if (error != nullptr) *error = "CUDA sampler not initialized";
        return false;
    }
    if (batch_trials <= 0 || impl_->n <= 0 || impl_->m <= 0) {
        ex_out.clear();
        sz_out.clear();
        return true;
    }

    const double p_clamped = std::max(0.0, std::min(1.0, p));
    const size_t ex_count = static_cast<size_t>(batch_trials) * static_cast<size_t>(impl_->n);
    const size_t sz_count = static_cast<size_t>(batch_trials) * static_cast<size_t>(impl_->m);
    const size_t ex_bytes = ex_count * sizeof(unsigned char);
    const size_t sz_bytes = sz_count * sizeof(unsigned char);

    unsigned char* d_ex = nullptr;
    unsigned char* d_sz = nullptr;
    if (!checkCuda(cudaMalloc(reinterpret_cast<void**>(&d_ex), ex_bytes), error, "cudaMalloc ex")) {
        return false;
    }
    if (!checkCuda(cudaMalloc(reinterpret_cast<void**>(&d_sz), sz_bytes), error, "cudaMalloc sz")) {
        cudaFree(d_ex);
        return false;
    }

    const int threads = 256;
    const int ex_blocks = static_cast<int>((ex_count + threads - 1) / threads);
    generate_ex_kernel<<<ex_blocks, threads>>>(d_ex, impl_->n, batch_trials, p_clamped,
                                               seed_base, d, p_key, start_trial);
    if (!checkCuda(cudaGetLastError(), error, "generate_ex_kernel")) {
        cudaFree(d_ex);
        cudaFree(d_sz);
        return false;
    }

    const int sz_blocks = static_cast<int>((sz_count + threads - 1) / threads);
    compute_sz_kernel<<<sz_blocks, threads>>>(d_ex, d_sz, impl_->d_row_ptr, impl_->d_col_idx,
                                              impl_->n, impl_->m, batch_trials);
    if (!checkCuda(cudaGetLastError(), error, "compute_sz_kernel")) {
        cudaFree(d_ex);
        cudaFree(d_sz);
        return false;
    }
    if (!checkCuda(cudaDeviceSynchronize(), error, "cudaDeviceSynchronize")) {
        cudaFree(d_ex);
        cudaFree(d_sz);
        return false;
    }

    ex_out.resize(ex_count);
    sz_out.resize(sz_count);
    if (!checkCuda(cudaMemcpy(ex_out.data(), d_ex, ex_bytes, cudaMemcpyDeviceToHost),
                   error, "cudaMemcpy ex")) {
        cudaFree(d_ex);
        cudaFree(d_sz);
        return false;
    }
    if (!checkCuda(cudaMemcpy(sz_out.data(), d_sz, sz_bytes, cudaMemcpyDeviceToHost),
                   error, "cudaMemcpy sz")) {
        cudaFree(d_ex);
        cudaFree(d_sz);
        return false;
    }

    cudaFree(d_ex);
    cudaFree(d_sz);
    return true;
}

bool is_available() {
    int device_count = 0;
    const cudaError_t err = cudaGetDeviceCount(&device_count);
    return (err == cudaSuccess && device_count > 0);
}

const char* backend_name() {
    return "cuda";
}

const char* device_name() {
    static char name[256] = "unknown";
    DeviceInfo info;
    std::string error;
    if (!get_device_info(&info, &error)) {
        return name;
    }
    std::snprintf(name, sizeof(name), "%s", info.name.c_str());
    return name;
}

bool get_device_info(DeviceInfo* out, std::string* error) {
    if (out == nullptr) {
        if (error) *error = "null DeviceInfo";
        return false;
    }
    int device = 0;
    if (cudaGetDevice(&device) != cudaSuccess) {
        if (error) *error = "cudaGetDevice failed";
        return false;
    }
    cudaDeviceProp prop;
    if (cudaGetDeviceProperties(&prop, device) != cudaSuccess) {
        if (error) *error = "cudaGetDeviceProperties failed";
        return false;
    }
    out->name = prop.name;
    out->major = prop.major;
    out->minor = prop.minor;
    out->multiprocessor_count = prop.multiProcessorCount;
    out->global_mem_bytes = static_cast<size_t>(prop.totalGlobalMem);
    return true;
}

} // namespace gpu
