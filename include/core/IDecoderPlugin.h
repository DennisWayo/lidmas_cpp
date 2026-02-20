#pragma once

#include <string>
#include "core/DecoderConfig.h"

class IDecoderPlugin {
public:
    virtual ~IDecoderPlugin() = default;

    virtual std::string name() const = 0;
    virtual std::string family() const = 0;
    virtual void configure(const DecoderConfig& cfg) = 0;
};
