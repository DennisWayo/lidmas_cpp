#include "plugins/stub/StubSurfacePlugin.h"

#include <memory>

#include "surface/MWPMStubDecoder.h"

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

std::string StubSurfacePlugin::name() const {
    return "stub";
}

std::string StubSurfacePlugin::family() const {
    return "surface";
}

void StubSurfacePlugin::configure(const DecoderConfig& cfg) {
    cfg_ = cfg;
}

SurfaceCorrection StubSurfacePlugin::decode(const SurfaceSyndrome& syn, const SurfaceCode& code) {
    (void)cfg_;
    thread_local const SurfaceCode* cached_code = nullptr;
    thread_local std::unique_ptr<MWPMStubDecoder> cached_decoder;
    if (cached_decoder == nullptr || cached_code != &code) {
        cached_decoder = std::make_unique<MWPMStubDecoder>(code);
        cached_code = &code;
    }
    return bitmaskToCorrection(cached_decoder->decode(syn));
}
