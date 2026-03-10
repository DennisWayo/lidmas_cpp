#pragma once

#include "decoder_io/DecoderTypes.h"

namespace decoder_io {

class DecoderAdapter {
public:
    virtual ~DecoderAdapter() = default;
    virtual DecodeResponse decode(const DecodeRequest& request) = 0;
};

} // namespace decoder_io
