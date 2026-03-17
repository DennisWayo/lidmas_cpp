#pragma once

#include <string>

class PluginRegistry;

namespace decoder_io {

struct DecoderIOReplayConfig {
    std::string input_ndjson;
    std::string output_ndjson;
    std::string adapter_config_path = "schemas/surface_decoder_adapter_config.json";
    bool continue_on_error = false;
};

bool runDecoderIOReplay(const DecoderIOReplayConfig& cfg,
                        const PluginRegistry& registry,
                        std::string* message_or_error);

} // namespace decoder_io
