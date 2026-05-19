#include "decoder_io/DecoderIOReplay.h"

#include <algorithm>
#include <cctype>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "core/PluginRegistry.h"
#include "decoder_io/DecoderTypes.h"
#include "decoder_io/SurfaceDecoderAdapter.h"
#include "decoder_io/SurfaceDecoderConfigIO.h"

namespace decoder_io {
namespace {

struct JsonValue {
    enum class Type {
        Null,
        Bool,
        Number,
        String,
        Array,
        Object
    };

    Type type = Type::Null;
    bool boolean = false;
    double number = 0.0;
    std::string str;
    std::vector<JsonValue> array;
    std::map<std::string, JsonValue> object;
};

class JsonParser {
public:
    explicit JsonParser(std::string text) : text_(std::move(text)) {}

    JsonValue parse() {
        skipWs();
        JsonValue v = parseValue();
        skipWs();
        if (!eof()) {
            fail("unexpected trailing characters");
        }
        return v;
    }

private:
    std::string text_;
    size_t pos_ = 0;

    bool eof() const { return pos_ >= text_.size(); }

    char peek() const {
        if (eof()) return '\0';
        return text_[pos_];
    }

    char consume() {
        if (eof()) fail("unexpected end of JSON");
        return text_[pos_++];
    }

    void skipWs() {
        while (!eof()) {
            const unsigned char c = static_cast<unsigned char>(text_[pos_]);
            if (!std::isspace(c)) break;
            pos_++;
        }
    }

    [[noreturn]] void fail(const std::string& message) const {
        std::ostringstream oss;
        oss << message << " at offset " << pos_;
        throw std::runtime_error(oss.str());
    }

    JsonValue parseValue() {
        if (eof()) fail("unexpected end of JSON");
        const char c = peek();
        if (c == '{') return parseObject();
        if (c == '[') return parseArray();
        if (c == '"') return parseStringValue();
        if (c == '-' || (c >= '0' && c <= '9')) return parseNumberValue();
        if (c == 't') return parseTrue();
        if (c == 'f') return parseFalse();
        if (c == 'n') return parseNull();
        fail("invalid JSON token");
    }

    JsonValue parseObject() {
        JsonValue v;
        v.type = JsonValue::Type::Object;
        consume(); // {
        skipWs();
        if (peek() == '}') {
            consume();
            return v;
        }
        while (true) {
            skipWs();
            if (peek() != '"') fail("expected object key string");
            const JsonValue key = parseStringValue();
            skipWs();
            if (consume() != ':') fail("expected ':' after object key");
            skipWs();
            JsonValue value = parseValue();
            v.object[key.str] = std::move(value);
            skipWs();
            const char next = consume();
            if (next == '}') break;
            if (next != ',') fail("expected ',' or '}' in object");
            skipWs();
        }
        return v;
    }

    JsonValue parseArray() {
        JsonValue v;
        v.type = JsonValue::Type::Array;
        consume(); // [
        skipWs();
        if (peek() == ']') {
            consume();
            return v;
        }
        while (true) {
            skipWs();
            v.array.push_back(parseValue());
            skipWs();
            const char next = consume();
            if (next == ']') break;
            if (next != ',') fail("expected ',' or ']' in array");
            skipWs();
        }
        return v;
    }

    static int hexDigit(char c) {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return 10 + (c - 'a');
        if (c >= 'A' && c <= 'F') return 10 + (c - 'A');
        return -1;
    }

    JsonValue parseStringValue() {
        JsonValue v;
        v.type = JsonValue::Type::String;
        if (consume() != '"') fail("expected '\"' to start string");
        std::string out;
        while (!eof()) {
            char c = consume();
            if (c == '"') {
                v.str = std::move(out);
                return v;
            }
            if (c != '\\') {
                out.push_back(c);
                continue;
            }
            if (eof()) fail("invalid escape sequence");
            const char esc = consume();
            switch (esc) {
                case '"': out.push_back('"'); break;
                case '\\': out.push_back('\\'); break;
                case '/': out.push_back('/'); break;
                case 'b': out.push_back('\b'); break;
                case 'f': out.push_back('\f'); break;
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                case 'u': {
                    if (pos_ + 4 > text_.size()) fail("short unicode escape");
                    int code = 0;
                    for (int i = 0; i < 4; ++i) {
                        const int h = hexDigit(text_[pos_ + static_cast<size_t>(i)]);
                        if (h < 0) fail("invalid unicode escape");
                        code = (code << 4) | h;
                    }
                    pos_ += 4;
                    // Keep output ASCII-safe for this CLI.
                    out.push_back((code >= 0x20 && code <= 0x7e) ? static_cast<char>(code) : '?');
                    break;
                }
                default:
                    fail("unsupported escape sequence");
            }
        }
        fail("unterminated string");
    }

    JsonValue parseNumberValue() {
        JsonValue v;
        v.type = JsonValue::Type::Number;
        const size_t start = pos_;
        if (peek() == '-') pos_++;
        if (eof()) fail("invalid number");
        if (peek() == '0') {
            pos_++;
        } else {
            if (!std::isdigit(static_cast<unsigned char>(peek()))) fail("invalid number");
            while (!eof() && std::isdigit(static_cast<unsigned char>(peek()))) pos_++;
        }
        if (!eof() && peek() == '.') {
            pos_++;
            if (eof() || !std::isdigit(static_cast<unsigned char>(peek()))) fail("invalid fractional number");
            while (!eof() && std::isdigit(static_cast<unsigned char>(peek()))) pos_++;
        }
        if (!eof() && (peek() == 'e' || peek() == 'E')) {
            pos_++;
            if (!eof() && (peek() == '+' || peek() == '-')) pos_++;
            if (eof() || !std::isdigit(static_cast<unsigned char>(peek()))) fail("invalid exponent");
            while (!eof() && std::isdigit(static_cast<unsigned char>(peek()))) pos_++;
        }
        const std::string token = text_.substr(start, pos_ - start);
        char* end = nullptr;
        const double value = std::strtod(token.c_str(), &end);
        if (end == nullptr || *end != '\0') fail("invalid numeric token");
        v.number = value;
        return v;
    }

    JsonValue parseTrue() {
        if (text_.compare(pos_, 4, "true") != 0) fail("invalid token");
        pos_ += 4;
        JsonValue v;
        v.type = JsonValue::Type::Bool;
        v.boolean = true;
        return v;
    }

    JsonValue parseFalse() {
        if (text_.compare(pos_, 5, "false") != 0) fail("invalid token");
        pos_ += 5;
        JsonValue v;
        v.type = JsonValue::Type::Bool;
        v.boolean = false;
        return v;
    }

    JsonValue parseNull() {
        if (text_.compare(pos_, 4, "null") != 0) fail("invalid token");
        pos_ += 4;
        JsonValue v;
        v.type = JsonValue::Type::Null;
        return v;
    }
};

std::string trim(const std::string& s) {
    size_t start = 0;
    while (start < s.size() && std::isspace(static_cast<unsigned char>(s[start]))) start++;
    size_t end = s.size();
    while (end > start && std::isspace(static_cast<unsigned char>(s[end - 1]))) end--;
    return s.substr(start, end - start);
}

std::string jsonEscape(const std::string& s) {
    std::ostringstream oss;
    for (char c : s) {
        switch (c) {
            case '"': oss << "\\\""; break;
            case '\\': oss << "\\\\"; break;
            case '\b': oss << "\\b"; break;
            case '\f': oss << "\\f"; break;
            case '\n': oss << "\\n"; break;
            case '\r': oss << "\\r"; break;
            case '\t': oss << "\\t"; break;
            default: {
                const unsigned char u = static_cast<unsigned char>(c);
                if (u < 0x20) {
                    oss << "\\u";
                    const char* hex = "0123456789abcdef";
                    oss << "00" << hex[(u >> 4) & 0x0f] << hex[u & 0x0f];
                } else {
                    oss << c;
                }
                break;
            }
        }
    }
    return oss.str();
}

std::string jsonNumberString(double value) {
    std::ostringstream oss;
    oss.setf(std::ios::fmtflags(0), std::ios::floatfield);
    oss.precision(16);
    oss << value;
    return oss.str();
}

std::string jsonCompact(const JsonValue& v);

std::string jsonArrayCompact(const std::vector<JsonValue>& arr) {
    std::ostringstream oss;
    oss << "[";
    for (size_t i = 0; i < arr.size(); ++i) {
        if (i > 0) oss << ",";
        oss << jsonCompact(arr[i]);
    }
    oss << "]";
    return oss.str();
}

std::string jsonObjectCompact(const std::map<std::string, JsonValue>& obj) {
    std::ostringstream oss;
    oss << "{";
    size_t i = 0;
    for (const auto& kv : obj) {
        if (i++ > 0) oss << ",";
        oss << "\"" << jsonEscape(kv.first) << "\":" << jsonCompact(kv.second);
    }
    oss << "}";
    return oss.str();
}

std::string jsonCompact(const JsonValue& v) {
    switch (v.type) {
        case JsonValue::Type::Null: return "null";
        case JsonValue::Type::Bool: return v.boolean ? "true" : "false";
        case JsonValue::Type::Number: return jsonNumberString(v.number);
        case JsonValue::Type::String: return "\"" + jsonEscape(v.str) + "\"";
        case JsonValue::Type::Array: return jsonArrayCompact(v.array);
        case JsonValue::Type::Object: return jsonObjectCompact(v.object);
    }
    return "null";
}

const JsonValue* getField(const JsonValue& obj, const std::string& key) {
    if (obj.type != JsonValue::Type::Object) return nullptr;
    const auto it = obj.object.find(key);
    if (it == obj.object.end()) return nullptr;
    return &it->second;
}

int toInt(const JsonValue& v, const std::string& what) {
    if (v.type != JsonValue::Type::Number) {
        throw std::runtime_error(what + " must be numeric");
    }
    const double rounded = std::round(v.number);
    if (std::fabs(rounded - v.number) > 1e-9) {
        throw std::runtime_error(what + " must be an integer");
    }
    if (rounded < static_cast<double>(INT32_MIN) || rounded > static_cast<double>(INT32_MAX)) {
        throw std::runtime_error(what + " is out of int32 range");
    }
    return static_cast<int>(rounded);
}

uint64_t toUInt64(const JsonValue& v, const std::string& what) {
    if (v.type != JsonValue::Type::Number) {
        throw std::runtime_error(what + " must be numeric");
    }
    const double rounded = std::round(v.number);
    if (std::fabs(rounded - v.number) > 1e-9 || rounded < 0.0) {
        throw std::runtime_error(what + " must be a non-negative integer");
    }
    if (rounded > static_cast<double>(UINT64_MAX)) {
        throw std::runtime_error(what + " is out of uint64 range");
    }
    return static_cast<uint64_t>(rounded);
}

double toDouble(const JsonValue& v, const std::string& what) {
    if (v.type != JsonValue::Type::Number) {
        throw std::runtime_error(what + " must be numeric");
    }
    return v.number;
}

std::string toStringValue(const JsonValue& v, const std::string& what) {
    if (v.type != JsonValue::Type::String) {
        throw std::runtime_error(what + " must be a string");
    }
    return v.str;
}

std::string toLowerAscii(const std::string& s) {
    std::string out = s;
    std::transform(out.begin(), out.end(), out.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return out;
}

SyndromeType parseSyndromeType(const JsonValue* v) {
    if (v == nullptr) return SyndromeType::Unknown;
    if (v->type == JsonValue::Type::Number) {
        const int n = toInt(*v, "syndrome type");
        if (n == 1) return SyndromeType::X;
        if (n == 2) return SyndromeType::Z;
        return SyndromeType::Unknown;
    }
    if (v->type != JsonValue::Type::String) return SyndromeType::Unknown;
    const std::string t = toLowerAscii(v->str);
    if (t == "x" || t == "syndrome_x") return SyndromeType::X;
    if (t == "z" || t == "syndrome_z") return SyndromeType::Z;
    return SyndromeType::Unknown;
}

std::vector<uint8_t> packBitsFrom01Vector(const std::vector<int>& bits) {
    std::vector<uint8_t> packed((bits.size() + 7) / 8, 0);
    for (size_t i = 0; i < bits.size(); ++i) {
        if ((bits[i] & 1) == 0) continue;
        packed[i / 8] |= static_cast<uint8_t>(1u << static_cast<unsigned>(i % 8));
    }
    return packed;
}

std::vector<uint8_t> parseDenseBits(const JsonValue& bits_val, int n_bits_hint) {
    if (bits_val.type == JsonValue::Type::Array) {
        std::vector<int> bits;
        bits.reserve(bits_val.array.size());
        for (size_t i = 0; i < bits_val.array.size(); ++i) {
            const int bit = toInt(bits_val.array[i], "dense bits[" + std::to_string(i) + "]");
            bits.push_back((bit == 0) ? 0 : 1);
        }
        return packBitsFrom01Vector(bits);
    }
    if (bits_val.type == JsonValue::Type::String) {
        std::vector<int> bits;
        bits.reserve(bits_val.str.size());
        for (char c : bits_val.str) {
            if (c == '0') bits.push_back(0);
            else if (c == '1') bits.push_back(1);
            else if (std::isspace(static_cast<unsigned char>(c))) continue;
            else throw std::runtime_error("dense bits string must contain only 0/1");
        }
        if (n_bits_hint > 0 && static_cast<int>(bits.size()) < n_bits_hint) {
            bits.resize(static_cast<size_t>(n_bits_hint), 0);
        }
        return packBitsFrom01Vector(bits);
    }
    throw std::runtime_error("dense bits must be array<int> or 0/1 string");
}

DecodeRequest decodeRequestFromJson(const JsonValue& root) {
    if (root.type != JsonValue::Type::Object) {
        throw std::runtime_error("DecodeRequest root must be a JSON object");
    }
    DecodeRequest req;

    if (const JsonValue* v = getField(root, "code_id")) req.code_id = toStringValue(*v, "code_id");
    if (const JsonValue* v = getField(root, "round_index")) req.round_index = toInt(*v, "round_index");
    if (const JsonValue* v = getField(root, "n_qubits")) req.n_qubits = toInt(*v, "n_qubits");

    if (const JsonValue* events = getField(root, "events")) {
        if (events->type != JsonValue::Type::Array) {
            throw std::runtime_error("events must be an array");
        }
        req.events.reserve(events->array.size());
        for (size_t i = 0; i < events->array.size(); ++i) {
            const JsonValue& ev = events->array[i];
            if (ev.type != JsonValue::Type::Object) {
                throw std::runtime_error("events[" + std::to_string(i) + "] must be an object");
            }
            SyndromeEvent se;
            const JsonValue* idx = getField(ev, "index");
            if (idx == nullptr) throw std::runtime_error("events[" + std::to_string(i) + "].index is required");
            se.index = toInt(*idx, "events[" + std::to_string(i) + "].index");
            if (const JsonValue* t = getField(ev, "time_ns")) {
                se.time_ns = toUInt64(*t, "events[" + std::to_string(i) + "].time_ns");
            }
            se.type = parseSyndromeType(getField(ev, "type"));
            req.events.push_back(std::move(se));
        }
    }

    if (const JsonValue* dense = getField(root, "dense")) {
        if (dense->type != JsonValue::Type::Array) {
            throw std::runtime_error("dense must be an array");
        }
        req.dense.reserve(dense->array.size());
        for (size_t i = 0; i < dense->array.size(); ++i) {
            const JsonValue& d = dense->array[i];
            if (d.type != JsonValue::Type::Object) {
                throw std::runtime_error("dense[" + std::to_string(i) + "] must be an object");
            }
            SyndromeDense sd;
            if (const JsonValue* n_bits = getField(d, "n_bits")) sd.n_bits = toInt(*n_bits, "dense.n_bits");
            sd.type = parseSyndromeType(getField(d, "type"));
            if (const JsonValue* bits = getField(d, "bits")) {
                sd.bits = parseDenseBits(*bits, sd.n_bits);
            }
            req.dense.push_back(std::move(sd));
        }
    }

    if (const JsonValue* noise = getField(root, "noise")) {
        if (noise->type != JsonValue::Type::Object) {
            throw std::runtime_error("noise must be an object");
        }
        if (const JsonValue* v = getField(*noise, "sigma")) req.noise.sigma = toDouble(*v, "noise.sigma");
        if (const JsonValue* v = getField(*noise, "gate_error_rate")) req.noise.gate_error_rate = toDouble(*v, "noise.gate_error_rate");
        if (const JsonValue* v = getField(*noise, "meas_error_rate")) req.noise.meas_error_rate = toDouble(*v, "noise.meas_error_rate");
        if (const JsonValue* v = getField(*noise, "idle_error_rate")) req.noise.idle_error_rate = toDouble(*v, "noise.idle_error_rate");
        if (const JsonValue* v = getField(*noise, "loss_prob_by_qubit")) {
            if (v->type != JsonValue::Type::Array) {
                throw std::runtime_error("noise.loss_prob_by_qubit must be an array");
            }
            req.noise.loss_prob_by_qubit.reserve(v->array.size());
            for (size_t i = 0; i < v->array.size(); ++i) {
                req.noise.loss_prob_by_qubit.push_back(toDouble(v->array[i], "noise.loss_prob_by_qubit[" + std::to_string(i) + "]"));
            }
        }
    }

    if (const JsonValue* metadata = getField(root, "metadata")) {
        if (metadata->type != JsonValue::Type::Object) {
            throw std::runtime_error("metadata must be an object");
        }
        for (const auto& kv : metadata->object) {
            if (kv.second.type == JsonValue::Type::String) {
                req.metadata[kv.first] = kv.second.str;
            } else {
                req.metadata[kv.first] = jsonCompact(kv.second);
            }
        }
    }

    return req;
}

std::string intArrayJson(const std::vector<int>& values) {
    std::ostringstream oss;
    oss << "[";
    for (size_t i = 0; i < values.size(); ++i) {
        if (i > 0) oss << ",";
        oss << values[i];
    }
    oss << "]";
    return oss.str();
}

std::string stringMapJson(const std::unordered_map<std::string, std::string>& values) {
    std::vector<std::string> keys;
    keys.reserve(values.size());
    for (const auto& kv : values) keys.push_back(kv.first);
    std::sort(keys.begin(), keys.end());
    std::ostringstream oss;
    oss << "{";
    for (size_t i = 0; i < keys.size(); ++i) {
        if (i > 0) oss << ",";
        const auto it = values.find(keys[i]);
        oss << "\"" << jsonEscape(keys[i]) << "\":\"" << jsonEscape(it->second) << "\"";
    }
    oss << "}";
    return oss.str();
}

std::string decodeResponseJson(const DecodeResponse& resp) {
    std::ostringstream oss;
    oss << "{";
    oss << "\"correction\":{";
    oss << "\"qubit_flips\":" << intArrayJson(resp.correction.qubit_flips) << ",";
    oss << "\"confidence\":" << jsonNumberString(resp.correction.confidence) << ",";
    oss << "\"decoder_name\":\"" << jsonEscape(resp.correction.decoder_name) << "\",";
    oss << "\"qubit_flips_x\":" << intArrayJson(resp.correction.qubit_flips_x) << ",";
    oss << "\"qubit_flips_z\":" << intArrayJson(resp.correction.qubit_flips_z);
    oss << "},";
    oss << "\"diagnostics\":" << stringMapJson(resp.diagnostics);
    oss << "}";
    return oss.str();
}

DecodeResponse makeErrorResponse(size_t line_no, const std::string& error) {
    DecodeResponse resp;
    resp.diagnostics["error"] = error;
    resp.diagnostics["line"] = std::to_string(line_no);
    return resp;
}

} // namespace

bool runDecoderIOReplay(const DecoderIOReplayConfig& cfg,
                        const PluginRegistry& registry,
                        std::string* message_or_error) {
    if (message_or_error != nullptr) message_or_error->clear();
    if (cfg.input_ndjson.empty()) {
        if (message_or_error != nullptr) *message_or_error = "missing --decoder_io_in path";
        return false;
    }

    SurfaceDecoderAdapterConfig adapter_cfg;
    std::string cfg_err;
    if (!loadSurfaceDecoderAdapterConfig(cfg.adapter_config_path, &adapter_cfg, &cfg_err)) {
        if (message_or_error != nullptr) {
            *message_or_error = "failed to load decoder_io config '" + cfg.adapter_config_path + "': " + cfg_err;
        }
        return false;
    }

    SurfaceDecoderAdapter adapter(adapter_cfg, registry);

    std::ifstream in(cfg.input_ndjson);
    if (!in.is_open()) {
        if (message_or_error != nullptr) {
            *message_or_error = "cannot open NDJSON input: " + cfg.input_ndjson;
        }
        return false;
    }

    std::ofstream out_file;
    std::ostream* out = &std::cout;
    if (!cfg.output_ndjson.empty()) {
        out_file.open(cfg.output_ndjson);
        if (!out_file.is_open()) {
            if (message_or_error != nullptr) {
                *message_or_error = "cannot open NDJSON output: " + cfg.output_ndjson;
            }
            return false;
        }
        out = &out_file;
    }

    size_t line_no = 0;
    size_t processed = 0;
    size_t errors = 0;
    std::string line;
    while (std::getline(in, line)) {
        line_no++;
        const std::string t = trim(line);
        if (t.empty()) continue;
        try {
            JsonParser parser(t);
            const JsonValue root = parser.parse();
            const DecodeRequest req = decodeRequestFromJson(root);
            const DecodeResponse resp = adapter.decode(req);
            *out << decodeResponseJson(resp) << "\n";
            out->flush();
            processed++;
        } catch (const std::exception& ex) {
            errors++;
            if (!cfg.continue_on_error) {
                if (message_or_error != nullptr) {
                    std::ostringstream oss;
                    oss << "line " << line_no << ": " << ex.what();
                    *message_or_error = oss.str();
                }
                return false;
            }
            *out << decodeResponseJson(makeErrorResponse(line_no, ex.what())) << "\n";
            out->flush();
        }
    }

    if (message_or_error != nullptr) {
        std::ostringstream oss;
        oss << "decoder_io replay complete: processed=" << processed
            << " errors=" << errors
            << " input=" << cfg.input_ndjson;
        if (!cfg.output_ndjson.empty()) {
            oss << " output=" << cfg.output_ndjson;
        } else {
            oss << " output=stdout";
        }
        *message_or_error = oss.str();
    }
    return true;
}

} // namespace decoder_io
