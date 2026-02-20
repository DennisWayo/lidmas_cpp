#pragma once

#include <functional>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>
#include "core/IDecoderPlugin.h"

class PluginRegistry {
public:
    using CreateFn = std::function<std::unique_ptr<IDecoderPlugin>()>;

    void registerPlugin(const std::string& name, CreateFn fn);
    std::unique_ptr<IDecoderPlugin> create(const std::string& name) const;
    std::vector<std::string> list() const;

private:
    std::unordered_map<std::string, CreateFn> factories_;
};
