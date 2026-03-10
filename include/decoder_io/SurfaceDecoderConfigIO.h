#pragma once

#include <string>
#include "decoder_io/SurfaceDecoderAdapter.h"

namespace decoder_io {

bool loadSurfaceDecoderAdapterConfig(const std::string& path,
                                     SurfaceDecoderAdapterConfig* cfg,
                                     std::string* error);

} // namespace decoder_io
