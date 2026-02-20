#include "plugins/uf/UnionFindPlugin.h"

#include <memory>

#include "surface/UnionFindDecoder.h"

namespace {

SurfaceCorrection bitmaskToCorrection(const std::vector<int>& bitmask) {
    SurfaceCorrection corr;
    corr.qubit_flips.reserve(bitmask.size());
    for (int i = 0; i < static_cast<int>(bitmask.size()); ++i) {
        if ((bitmask[i] & 1) != 0) corr.qubit_flips.push_back(i);
    }
    corr.weight = static_cast<int>(corr.qubit_flips.size());
    return corr;
}

} // namespace

std::string UnionFindPlugin::name() const {
    return "uf";
}

std::string UnionFindPlugin::family() const {
    return "surface";
}

void UnionFindPlugin::configure(const DecoderConfig& cfg) {
    cfg_ = cfg;
}

SurfaceCorrection UnionFindPlugin::decode(const SurfaceSyndrome& syn, const SurfaceCode& code) {
    (void)cfg_;
    thread_local const SurfaceCode* cached_code = nullptr;
    thread_local std::unique_ptr<UnionFindDecoder> cached_decoder;
    if (cached_decoder == nullptr || cached_code != &code) {
        cached_decoder = std::make_unique<UnionFindDecoder>(code);
        cached_code = &code;
    }
    return bitmaskToCorrection(cached_decoder->decode(syn));
}
