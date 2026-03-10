#include "decoder_io/SurfaceDecoderConfigIO.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <sstream>

namespace decoder_io {
namespace {

std::string trim(const std::string& s) {
    size_t start = 0;
    while (start < s.size() && std::isspace(static_cast<unsigned char>(s[start]))) start++;
    size_t end = s.size();
    while (end > start && std::isspace(static_cast<unsigned char>(s[end - 1]))) end--;
    return s.substr(start, end - start);
}

std::string stripQuotes(const std::string& s) {
    if (s.size() < 2) return s;
    if ((s.front() == '"' && s.back() == '"') || (s.front() == '\'' && s.back() == '\'')) {
        return s.substr(1, s.size() - 2);
    }
    return s;
}

bool parseBool(const std::string& token, bool* out) {
    if (out == nullptr) return false;
    std::string lowered = token;
    std::transform(lowered.begin(), lowered.end(), lowered.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (lowered == "true" || lowered == "1" || lowered == "yes") {
        *out = true;
        return true;
    }
    if (lowered == "false" || lowered == "0" || lowered == "no") {
        *out = false;
        return true;
    }
    return false;
}

bool extractJsonToken(const std::string& content,
                      const std::string& key,
                      std::string* out,
                      std::string* error) {
    if (out == nullptr || error == nullptr) return false;
    const std::string needle = "\"" + key + "\"";
    size_t pos = content.find(needle);
    if (pos == std::string::npos) return false;
    pos = content.find(':', pos + needle.size());
    if (pos == std::string::npos) {
        *error = "malformed JSON (missing ':' for key " + key + ")";
        return false;
    }
    pos++;
    while (pos < content.size() && std::isspace(static_cast<unsigned char>(content[pos]))) pos++;
    if (pos >= content.size()) {
        *error = "malformed JSON (missing value for key " + key + ")";
        return false;
    }

    if (content[pos] == '"') {
        pos++;
        std::string value;
        while (pos < content.size()) {
            char ch = content[pos++];
            if (ch == '\\') {
                if (pos < content.size()) value.push_back(content[pos++]);
                continue;
            }
            if (ch == '"') break;
            value.push_back(ch);
        }
        *out = value;
        return true;
    }

    size_t end = pos;
    while (end < content.size()) {
        const char ch = content[end];
        if (ch == ',' || ch == '}' || ch == '\n' || std::isspace(static_cast<unsigned char>(ch))) break;
        end++;
    }
    *out = content.substr(pos, end - pos);
    return true;
}

bool applyConfigField(const std::string& key,
                      const std::string& value,
                      SurfaceDecoderAdapterConfig* cfg,
                      std::string* error) {
    if (cfg == nullptr || error == nullptr) return false;
    if (key == "distance") {
        cfg->distance = std::stoi(value);
    } else if (key == "decoder_name" || key == "decoder") {
        cfg->decoder_name = stripQuotes(value);
    } else if (key == "weight_mode") {
        cfg->weight_mode = stripQuotes(value);
    } else if (key == "mwpm_graph") {
        cfg->mwpm_graph = stripQuotes(value);
    } else if (key == "uf_weighted") {
        bool val = false;
        if (!parseBool(value, &val)) {
            *error = "invalid boolean for uf_weighted";
            return false;
        }
        cfg->uf_weighted = val;
    } else if (key == "llr_p_data") {
        cfg->llr_p_data = std::stod(value);
    } else if (key == "llr_p_meas") {
        cfg->llr_p_meas = std::stod(value);
    } else if (key == "llr_p_idle") {
        cfg->llr_p_idle = std::stod(value);
    } else if (key == "llr_clamp_min") {
        cfg->llr_clamp_min = std::stod(value);
    } else if (key == "llr_clamp_max") {
        cfg->llr_clamp_max = std::stod(value);
    } else if (key == "mwpm_weight_scale") {
        cfg->mwpm_weight_scale = std::stod(value);
    } else if (key == "neural_weights_path") {
        cfg->neural_weights_path = stripQuotes(value);
    } else if (key == "neural_model_path") {
        cfg->neural_model_path = stripQuotes(value);
    } else if (key == "default_p") {
        cfg->default_p = std::stod(value);
    } else if (key == "seed") {
        cfg->seed = static_cast<uint64_t>(std::stoull(value));
    }
    return true;
}

} // namespace

bool loadSurfaceDecoderAdapterConfig(const std::string& path,
                                     SurfaceDecoderAdapterConfig* cfg,
                                     std::string* error) {
    if (cfg == nullptr || error == nullptr) return false;
    std::ifstream in(path);
    if (!in.is_open()) {
        *error = "cannot open config: " + path;
        return false;
    }

    const std::filesystem::path cfg_path(path);
    const std::string ext = cfg_path.extension().string();

    if (ext == ".json") {
        std::stringstream buffer;
        buffer << in.rdbuf();
        const std::string content = buffer.str();
        std::string parse_error;
        const std::vector<std::string> keys = {
            "distance",
            "decoder_name",
            "decoder",
            "weight_mode",
            "mwpm_graph",
            "uf_weighted",
            "llr_p_data",
            "llr_p_meas",
            "llr_p_idle",
            "llr_clamp_min",
            "llr_clamp_max",
            "mwpm_weight_scale",
            "neural_weights_path",
            "neural_model_path",
            "default_p",
            "seed"
        };
        for (const auto& key : keys) {
            std::string token;
            if (!extractJsonToken(content, key, &token, &parse_error)) {
                if (!parse_error.empty()) {
                    *error = parse_error;
                    return false;
                }
                continue;
            }
            if (!applyConfigField(key, token, cfg, error)) {
                return false;
            }
        }
        return true;
    }

    std::string line;
    while (std::getline(in, line)) {
        std::string stripped = line;
        const size_t hash_pos = stripped.find('#');
        const size_t slash_pos = stripped.find("//");
        size_t cut = std::string::npos;
        if (hash_pos != std::string::npos) cut = hash_pos;
        if (slash_pos != std::string::npos) cut = (cut == std::string::npos) ? slash_pos : std::min(cut, slash_pos);
        if (cut != std::string::npos) stripped = stripped.substr(0, cut);
        stripped = trim(stripped);
        if (stripped.empty()) continue;
        const size_t colon = stripped.find(':');
        if (colon == std::string::npos) continue;
        std::string key = trim(stripped.substr(0, colon));
        std::string value = trim(stripped.substr(colon + 1));
        value = stripQuotes(value);
        if (!applyConfigField(key, value, cfg, error)) {
            return false;
        }
    }

    return true;
}

} // namespace decoder_io
