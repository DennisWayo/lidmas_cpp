#include "plugins/neural/NeuralWeightModel.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <sstream>
#include <string>

namespace {

void disableModel(NeuralWeightModel& model) {
    model = NeuralWeightModel();
}

bool readTextFile(const std::string& path, std::string& out) {
    std::ifstream in(path);
    if (!in.is_open()) return false;
    out.assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
    return true;
}

bool findKey(const std::string& text, const std::string& key, size_t& value_pos) {
    const std::string token = "\"" + key + "\"";
    size_t pos = text.find(token);
    if (pos == std::string::npos) return false;
    pos = text.find(':', pos + token.size());
    if (pos == std::string::npos) return false;
    value_pos = pos + 1;
    return true;
}

void skipWs(const std::string& text, size_t& pos) {
    while (pos < text.size() && std::isspace(static_cast<unsigned char>(text[pos]))) ++pos;
}

bool parseStringField(const std::string& text, const std::string& key, std::string& out) {
    size_t pos = 0;
    if (!findKey(text, key, pos)) return false;
    skipWs(text, pos);
    if (pos >= text.size() || text[pos] != '"') return false;
    size_t end = text.find('"', pos + 1);
    if (end == std::string::npos) return false;
    out = text.substr(pos + 1, end - (pos + 1));
    return true;
}

bool parseDoubleAt(const std::string& text, size_t pos, double& out) {
    skipWs(text, pos);
    if (pos >= text.size()) return false;
    char* end = nullptr;
    out = std::strtod(text.c_str() + pos, &end);
    return (end != text.c_str() + pos) && std::isfinite(out);
}

bool parseDoubleField(const std::string& text, const std::string& key, double& out) {
    size_t pos = 0;
    if (!findKey(text, key, pos)) return false;
    return parseDoubleAt(text, pos, out);
}

bool parseArray2Field(const std::string& text, const std::string& key, double& a, double& b) {
    size_t pos = 0;
    if (!findKey(text, key, pos)) return false;
    skipWs(text, pos);
    if (pos >= text.size() || text[pos] != '[') return false;
    ++pos;
    if (!parseDoubleAt(text, pos, a)) return false;
    size_t comma = text.find(',', pos);
    if (comma == std::string::npos) return false;
    pos = comma + 1;
    if (!parseDoubleAt(text, pos, b)) return false;
    return true;
}

bool parseWeightsObject(const std::string& text,
                        double& w_manhattan,
                        double& w_dx,
                        double& w_dy,
                        double& w_near_boundary) {
    w_manhattan = 0.0;
    w_dx = 0.0;
    w_dy = 0.0;
    w_near_boundary = 0.0;

    size_t pos = 0;
    if (!findKey(text, "weights", pos)) return false;
    skipWs(text, pos);
    if (pos >= text.size() || text[pos] != '{') return false;
    size_t end = text.find('}', pos + 1);
    if (end == std::string::npos) return false;
    const std::string obj = text.substr(pos + 1, end - (pos + 1));

    double v = 0.0;
    if (parseDoubleField(obj, "manhattan", v)) w_manhattan = v;
    if (parseDoubleField(obj, "dx", v)) w_dx = v;
    if (parseDoubleField(obj, "dy", v)) w_dy = v;
    if (parseDoubleField(obj, "near_boundary", v)) w_near_boundary = v;
    return true;
}

} // namespace

bool NeuralWeightModel::loadFromJson(const std::string& path) {
    disableModel(*this);
    if (path.empty()) return false;

    std::string text;
    if (!readTextFile(path, text)) return false;

    std::string type = "linear";
    (void)parseStringField(text, "type", type);
    if (type != "linear") return false;

    double bias = 1.0;
    (void)parseDoubleField(text, "bias", bias);

    double w_manhattan = 0.0;
    double w_dx = 0.0;
    double w_dy = 0.0;
    double w_near_boundary = 0.0;
    if (!parseWeightsObject(text, w_manhattan, w_dx, w_dy, w_near_boundary)) return false;

    double clamp_lo = 0.5;
    double clamp_hi = 2.0;
    (void)parseArray2Field(text, "clamp", clamp_lo, clamp_hi);
    if (!std::isfinite(clamp_lo) || !std::isfinite(clamp_hi)) return false;
    if (clamp_lo > clamp_hi) std::swap(clamp_lo, clamp_hi);

    type_ = type;
    bias_ = bias;
    w_manhattan_ = w_manhattan;
    w_dx_ = w_dx;
    w_dy_ = w_dy;
    w_near_boundary_ = w_near_boundary;
    clamp_lo_ = clamp_lo;
    clamp_hi_ = clamp_hi;
    enabled_ = true;
    return true;
}

double NeuralWeightModel::predictScale(double manhattan,
                                       double dx,
                                       double dy,
                                       double near_boundary) const {
    if (!enabled_) return 1.0;

    double raw = bias_
        + w_manhattan_ * manhattan
        + w_dx_ * dx
        + w_dy_ * dy
        + w_near_boundary_ * near_boundary;

    if (!std::isfinite(raw)) return 1.0;
    return std::clamp(raw, clamp_lo_, clamp_hi_);
}
