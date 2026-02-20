#include "core/PluginRegistry.h"

#include <algorithm>
#include <stdexcept>

void PluginRegistry::registerPlugin(const std::string& name, CreateFn fn) {
    if (name.empty()) {
        throw std::invalid_argument("PluginRegistry::registerPlugin requires non-empty name");
    }
    if (!fn) {
        throw std::invalid_argument("PluginRegistry::registerPlugin requires valid factory");
    }
    if (factories_.find(name) != factories_.end()) {
        throw std::invalid_argument("PluginRegistry::registerPlugin duplicate name: " + name);
    }
    factories_[name] = std::move(fn);
}

std::unique_ptr<IDecoderPlugin> PluginRegistry::create(const std::string& name) const {
    const auto it = factories_.find(name);
    if (it == factories_.end()) {
        throw std::invalid_argument("PluginRegistry::create unknown plugin: " + name);
    }
    return it->second();
}

std::vector<std::string> PluginRegistry::list() const {
    std::vector<std::string> out;
    out.reserve(factories_.size());
    for (const auto& kv : factories_) out.push_back(kv.first);
    std::sort(out.begin(), out.end());
    return out;
}
