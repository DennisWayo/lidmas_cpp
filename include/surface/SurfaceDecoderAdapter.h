#pragma once

#include <memory>
#include "decoders/IDecoder.h"
#include "surface/ISurfaceDecoder.h"

class SurfaceDecoderAdapter : public IDecoder {
public:
    SurfaceDecoderAdapter(std::unique_ptr<ISurfaceDecoder> surface_decoder, int n_data);
    DecodeResult decode(const DecodeRequest& req) override;

private:
    std::unique_ptr<ISurfaceDecoder> surface_decoder_;
    int n_data_ = 0;
};
