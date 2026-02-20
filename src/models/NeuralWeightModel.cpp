#include "models/NeuralWeightModel.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <string>

namespace lidmas_v07 {
namespace {

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
    const size_t comma = text.find(',', pos);
    if (comma == std::string::npos) return false;
    pos = comma + 1;
    if (!parseDoubleAt(text, pos, b)) return false;
    return true;
}

bool parseWeightsObject(const std::string& text,
                        double& w_qubit,
                        double& w_distance,
                        double& w_p) {
    w_qubit = 0.0;
    w_distance = 0.0;
    w_p = 0.0;

    size_t pos = 0;
    if (!findKey(text, "weights", pos)) return false;
    skipWs(text, pos);
    if (pos >= text.size() || text[pos] != '{') return false;

    const size_t end = text.find('}', pos + 1);
    if (end == std::string::npos) return false;
    const std::string obj = text.substr(pos + 1, end - (pos + 1));

    double v = 0.0;
    if (parseDoubleField(obj, "qubit", v) || parseDoubleField(obj, "qubit_index", v)) w_qubit = v;
    if (parseDoubleField(obj, "distance", v)) w_distance = v;
    if (parseDoubleField(obj, "p", v)) w_p = v;

    return true;
}

} // namespace

bool NeuralWeightModel::load(const std::string& path) {
    enabled_ = false;
    bias_ = 0.0;
    w_qubit_ = 0.0;
    w_distance_ = 0.0;
    w_p_ = 0.0;
    clamp_lo_ = -5.0;
    clamp_hi_ = 5.0;

    if (path.empty()) return false;

    std::string text;
    if (!readTextFile(path, text)) return false;

    double bias = 0.0;
    (void)parseDoubleField(text, "bias", bias);

    double w_qubit = 0.0;
    double w_distance = 0.0;
    double w_p = 0.0;
    if (!parseWeightsObject(text, w_qubit, w_distance, w_p)) {
        (void)parseDoubleField(text, "w_qubit", w_qubit);
        (void)parseDoubleField(text, "w_distance", w_distance);
        (void)parseDoubleField(text, "w_p", w_p);
    }

    double clamp_lo = -5.0;
    double clamp_hi = 5.0;
    (void)parseArray2Field(text, "clamp", clamp_lo, clamp_hi);

    if (!std::isfinite(bias) || !std::isfinite(w_qubit) || !std::isfinite(w_distance) || !std::isfinite(w_p)
        || !std::isfinite(clamp_lo) || !std::isfinite(clamp_hi)) {
        return false;
    }

    if (clamp_lo > clamp_hi) std::swap(clamp_lo, clamp_hi);

    bias_ = bias;
    w_qubit_ = w_qubit;
    w_distance_ = w_distance;
    w_p_ = w_p;
    clamp_lo_ = clamp_lo;
    clamp_hi_ = clamp_hi;
    enabled_ = true;
    return true;
}

double NeuralWeightModel::edge_weight(int qubit_index, int distance, double p) const {
    if (!enabled_) return 0.0;

    const double q = static_cast<double>(qubit_index);
    const double d = static_cast<double>(distance);
    const double raw = bias_ + w_qubit_ * q + w_distance_ * d + w_p_ * p;
    if (!std::isfinite(raw)) return 0.0;

    return std::clamp(raw, clamp_lo_, clamp_hi_);
}

} // namespace lidmas_v07
