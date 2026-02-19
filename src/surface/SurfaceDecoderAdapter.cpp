#include "surface/SurfaceDecoderAdapter.h"

#include <stdexcept>

SurfaceDecoderAdapter::SurfaceDecoderAdapter(std::unique_ptr<ISurfaceDecoder> surface_decoder,
                                             int n_data)
    : surface_decoder_(std::move(surface_decoder)),
      n_data_(n_data) {
    if (!surface_decoder_) {
        throw std::invalid_argument("SurfaceDecoderAdapter requires a non-null surface decoder");
    }
}

DecodeResult SurfaceDecoderAdapter::decode(const DecodeRequest& req) {
    if (req.syndrome == nullptr) {
        throw std::invalid_argument("SurfaceDecoderAdapter requires a non-null syndrome");
    }

    SurfaceSyndrome syn;
    syn.sz = *req.syndrome;
    if (req.received_bits != nullptr) {
        syn.ex = *req.received_bits;
    }

    std::vector<int> correction = surface_decoder_->decode(syn);
    if (n_data_ > 0 && static_cast<int>(correction.size()) != n_data_) {
        correction.resize(n_data_, 0);
    }

    DecodeResult out;
    out.correction = std::move(correction);
    out.iters = 1;
    out.hit_max_iters = false;
    return out;
}
