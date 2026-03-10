#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "core/DecoderConfig.h"
#include "core/IDecoderPlugin.h"
#include "decoder_io/DecoderAdapter.h"
#include "surface/ISurfaceDecoderPlugin.h"
#include "surface/SurfaceCode.h"

class PluginRegistry;

namespace decoder_io {

struct SurfaceDecoderAdapterConfig {
    int distance = 3;
    std::string decoder_name = "mwpm";
    std::string weight_mode = "uniform";
    std::string mwpm_graph = "full";
    bool uf_weighted = false;
    double llr_p_data = -1.0;
    double llr_p_meas = -1.0;
    double llr_p_idle = -1.0;
    double llr_clamp_min = 1e-12;
    double llr_clamp_max = 1.0 - 1e-12;
    double mwpm_weight_scale = 1000.0;
    std::string neural_weights_path;
    std::string neural_model_path;
    double default_p = 0.0;
    uint64_t seed = 0;
};

class SurfaceDecoderAdapter : public DecoderAdapter {
public:
    SurfaceDecoderAdapter(const SurfaceDecoderAdapterConfig& cfg, const PluginRegistry& reg);
    DecodeResponse decode(const DecodeRequest& request) override;

private:
    SurfaceDecoderAdapterConfig cfg_;
    SurfaceCode code_;
    std::unique_ptr<IDecoderPlugin> plugin_base_;
    ISurfaceDecoderPlugin* surf_plugin_ = nullptr;

    DecoderConfig buildDecoderConfig(const DecodeRequest& request) const;
    static void appendUnique(const std::vector<int>& src, std::vector<int>& dst);
    static int countOnes(const std::vector<int>& v);
    static void applyDense(const SyndromeDense& dense, std::vector<int>& dest);
};

} // namespace decoder_io
