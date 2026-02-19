#include "core/RegisterDecoders.h"

#include <stdexcept>

#include "core/DecoderRegistry.h"
#include "surface/MWPMDecoder.h"
#include "surface/MWPMStubDecoder.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfaceDecoderAdapter.h"

void registerBuiltInDecoders(DecoderRegistry& registry) {
    registry.registerDecoder("mwpm_stub", [](const DecoderConfig& cfg) -> std::unique_ptr<IDecoder> {
        const auto it = cfg.ptr_params.find("surface_code");
        if (it == cfg.ptr_params.end() || it->second == nullptr) {
            throw std::invalid_argument("mwpm_stub requires ptr_params['surface_code']");
        }

        const auto* code = static_cast<const SurfaceCode*>(it->second);
        auto surface_decoder = std::make_unique<MWPMStubDecoder>(*code);
        return std::make_unique<SurfaceDecoderAdapter>(std::move(surface_decoder), code->n());
    });

    registry.registerDecoder("mwpm", [](const DecoderConfig& cfg) -> std::unique_ptr<IDecoder> {
        const auto it = cfg.ptr_params.find("surface_code");
        if (it == cfg.ptr_params.end() || it->second == nullptr) {
            throw std::invalid_argument("mwpm requires ptr_params['surface_code']");
        }

        const auto* code = static_cast<const SurfaceCode*>(it->second);
        auto surface_decoder = std::make_unique<MWPMDecoder>(*code);
        return std::make_unique<SurfaceDecoderAdapter>(std::move(surface_decoder), code->n());
    });
}
