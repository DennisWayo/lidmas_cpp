#pragma once

#include <vector>

struct DecodeRequest {
    const std::vector<int>* syndrome = nullptr;       // required
    const std::vector<int>* received_bits = nullptr;  // optional
    const std::vector<int>* erasures = nullptr;       // optional (nullptr => all-zero)
    double p_error = 0.0;
};

struct DecodeResult {
    std::vector<int> correction;
    int iters = 0;
    bool hit_max_iters = false;
};

class IDecoder {
public:
    virtual ~IDecoder() = default;
    virtual DecodeResult decode(const DecodeRequest& req) = 0;
};
