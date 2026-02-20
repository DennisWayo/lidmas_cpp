#include "core/RegisterPlugins.h"

#include "core/PluginRegistry.h"
#include "plugins/neural/NeuralMWPMPlugin.h"
#include "plugins/mwpm/MWPMPlugin.h"
#include "plugins/stub/StubSurfacePlugin.h"
#include "plugins/uf/UnionFindPlugin.h"

void RegisterAllPlugins(PluginRegistry& reg) {
    reg.registerPlugin("stub", []() -> std::unique_ptr<IDecoderPlugin> {
        return std::make_unique<StubSurfacePlugin>();
    });
    reg.registerPlugin("mwpm", []() -> std::unique_ptr<IDecoderPlugin> {
        return std::make_unique<MWPMPlugin>();
    });
    reg.registerPlugin("uf", []() -> std::unique_ptr<IDecoderPlugin> {
        return std::make_unique<UnionFindPlugin>();
    });
    reg.registerPlugin("neural_mwpm", []() -> std::unique_ptr<IDecoderPlugin> {
        return std::make_unique<NeuralMWPMPlugin>();
    });
}
