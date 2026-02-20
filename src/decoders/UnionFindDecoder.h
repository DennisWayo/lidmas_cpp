#pragma once

#include <atomic>
#include <string>
#include <vector>

#include "decoders/IDecoder.h"
#include "UniformWeightField.h"
#include "WeightField.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfaceSyndrome.h"

namespace lidmas_v07 {

class UnionFindDecoder : public IDecoder {
public:
    using Syndrome = std::vector<int>;

    struct Options {
        bool uf_weighted = false;
        double p_error = 0.0;
    };

    explicit UnionFindDecoder(const SurfaceCode& code);
    UnionFindDecoder(const SurfaceCode& code, const WeightField* weight_field);
    UnionFindDecoder(const SurfaceCode& code, Options options);
    UnionFindDecoder(const SurfaceCode& code, Options options, const WeightField* weight_field);

    DecodeResult decode(const DecodeRequest& req) override;
    DecodeResult decode(const Syndrome& s);

    std::vector<int> decodeSurface(const SurfaceSyndrome& syn);

    void setWeighted(bool enabled) { options_.uf_weighted = enabled; }
    void setChannelErrorRate(double p) { options_.p_error = p; }

    bool lastLogicalFailure() const { return last_logical_failure_.load(std::memory_order_relaxed); }

private:
    struct Defect {
        int id = -1;
        int x = 0;
        int y = 0;
        int vertex = -1;
        bool boundary_flag = false;
    };

    const SurfaceCode& code_;
    int d_ = 0;
    Options options_;
    UniformWeightField uniform_weight_field_;
    const WeightField* weight_field_ = nullptr;
    std::atomic<bool> last_logical_failure_{false};

    int hIndex(int x, int y) const;
    int vIndex(int x, int y) const;
    void toggleH(int x, int y, std::vector<int>& corr) const;
    void toggleV(int x, int y, std::vector<int>& corr) const;

    std::vector<int> decodeSyndromeUFWeighted(const Syndrome& syndrome, bool plaquette_mode) const;
    bool syndromeMatches(const BinaryMatrix& H,
                         const std::vector<int>& corr,
                         const std::vector<int>& target) const;
    bool computeLogicalFailure(const std::vector<int>& corr) const;
};

} // namespace lidmas_v07
