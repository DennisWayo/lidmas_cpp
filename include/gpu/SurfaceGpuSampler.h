#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace gpu {

struct DeviceInfo {
    std::string name;
    int major = 0;
    int minor = 0;
    int multiprocessor_count = 0;
    size_t global_mem_bytes = 0;
};

class SurfaceGpuSampler {
public:
    SurfaceGpuSampler(int n, const std::vector<std::vector<int>>& hz_rows, std::string* error);
    ~SurfaceGpuSampler();

    bool ok() const;
    int n() const;
    int m() const;

    bool sample_pauli_batch(double p,
                            uint64_t seed_base,
                            int d,
                            int p_key,
                            long long start_trial,
                            int batch_trials,
                            std::vector<unsigned char>& ex_out,
                            std::vector<unsigned char>& sz_out,
                            std::string* error);

private:
    struct Impl;
    Impl* impl_ = nullptr;
};

bool is_available();
const char* backend_name();
const char* device_name();
bool get_device_info(DeviceInfo* out, std::string* error);

} // namespace gpu
