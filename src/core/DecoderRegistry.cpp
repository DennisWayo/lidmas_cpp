#include "core/DecoderRegistry.h"

#include <algorithm>
#include <stdexcept>

void DecoderRegistry::registerDecoder(const std::string& name, CreateFn fn) {
    if (name.empty()) {
        throw std::invalid_argument("DecoderRegistry::registerDecoder requires non-empty name");
    }
    if (!fn) {
        throw std::invalid_argument("DecoderRegistry::registerDecoder requires valid factory");
    }
    if (factories_.find(name) != factories_.end()) {
        throw std::invalid_argument("DecoderRegistry::registerDecoder duplicate name: " + name);
    }
    factories_[name] = std::move(fn);
}

std::unique_ptr<IDecoder> DecoderRegistry::create(const std::string& name,
                                                  const DecoderConfig& cfg) const {
    const auto it = factories_.find(name);
    if (it == factories_.end()) {
        throw std::invalid_argument("DecoderRegistry::create unknown decoder: " + name);
    }
    return it->second(cfg);
}

std::vector<std::string> DecoderRegistry::list() const {
    std::vector<std::string> out;
    out.reserve(factories_.size());
    for (const auto& kv : factories_) out.push_back(kv.first);
    std::sort(out.begin(), out.end());
    return out;
}
