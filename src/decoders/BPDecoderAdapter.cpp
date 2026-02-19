#include "decoders/BPDecoderAdapter.h"
#include <stdexcept>

BPDecoderAdapter::BPDecoderAdapter(const TannerGraph& graph, BeliefPropagation::Params params)
    : graph_(graph),
      bp_(graph_, params) {}

DecodeResult BPDecoderAdapter::decode(const DecodeRequest& req) {
    if (req.syndrome == nullptr) {
        throw std::invalid_argument("BPDecoderAdapter requires a non-null syndrome");
    }

    const int n = graph_.nVars();
    std::vector<int> erasures_local;
    const std::vector<int>* erasures = req.erasures;
    if (erasures == nullptr) {
        erasures_local.assign(n, 0);
        erasures = &erasures_local;
    }

    std::vector<int> correction;
    if (req.received_bits != nullptr) {
        correction = bp_.decode(*req.syndrome, *req.received_bits, *erasures, req.p_error);
    } else {
        correction = bp_.decode(*req.syndrome, *erasures, req.p_error);
    }

    DecodeResult out;
    out.correction = std::move(correction);
    out.iters = bp_.lastIterations();
    out.hit_max_iters = bp_.lastHitMaxIters();
    return out;
}
