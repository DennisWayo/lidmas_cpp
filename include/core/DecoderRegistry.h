#pragma once

#include <functional>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>
#include "core/DecoderConfig.h"
#include "decoders/IDecoder.h"

class DecoderRegistry {
public:
    using CreateFn = std::function<std::unique_ptr<IDecoder>(const DecoderConfig&)>;

    void registerDecoder(const std::string& name, CreateFn fn);
    std::unique_ptr<IDecoder> create(const std::string& name, const DecoderConfig& cfg) const;
    std::vector<std::string> list() const;

private:
    std::unordered_map<std::string, CreateFn> factories_;
};
