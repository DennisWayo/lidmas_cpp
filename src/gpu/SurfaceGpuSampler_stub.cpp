#include "gpu/SurfaceGpuSampler.h"

namespace gpu {

struct SurfaceGpuSampler::Impl {
    bool ok = false;
    int n = 0;
    int m = 0;
};

SurfaceGpuSampler::SurfaceGpuSampler(int n, const std::vector<std::vector<int>>&, std::string* error) {
    impl_ = new Impl();
    impl_->n = n;
    impl_->m = 0;
    impl_->ok = false;
    if (error) {
        *error = "CUDA backend not enabled";
    }
}

SurfaceGpuSampler::~SurfaceGpuSampler() {
    delete impl_;
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

bool SurfaceGpuSampler::sample_pauli_batch(double,
                                           uint64_t,
                                           int,
                                           int,
                                           long long,
                                           int,
                                           std::vector<unsigned char>&,
                                           std::vector<unsigned char>&,
                                           std::string* error) {
    if (error) {
        *error = "CUDA backend not enabled";
    }
    return false;
}

bool is_available() {
    return false;
}

const char* backend_name() {
    return "none";
}

const char* device_name() {
    return "none";
}

bool get_device_info(DeviceInfo* out, std::string* error) {
    if (out) *out = DeviceInfo{};
    if (error) *error = "CUDA backend not enabled";
    return false;
}

} // namespace gpu
