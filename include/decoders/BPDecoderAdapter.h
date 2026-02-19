#pragma once

#include "decoders/BeliefPropagation.h"
#include "decoders/IDecoder.h"
#include "graph/TannerGraph.h"

class BPDecoderAdapter : public IDecoder {
public:
    BPDecoderAdapter(const TannerGraph& graph, BeliefPropagation::Params params);
    DecodeResult decode(const DecodeRequest& req) override;

private:
    const TannerGraph& graph_;
    BeliefPropagation bp_;
};
