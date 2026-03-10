#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace decoder_io {

enum class SyndromeType {
    Unknown = 0,
    X = 1,
    Z = 2
};

struct SyndromeEvent {
    int index = -1;           // stabilizer index
    uint64_t time_ns = 0;     // event timestamp
    SyndromeType type = SyndromeType::Unknown;
};

struct NoiseParams {
    double sigma = 0.0;
    double gate_error_rate = 0.0;
    double meas_error_rate = 0.0;
    double idle_error_rate = 0.0;
    std::vector<double> loss_prob_by_qubit; // length n_qubits
};

struct SyndromeDense {
    std::vector<uint8_t> bits; // packed bitset (LSB-first)
    int n_bits = 0;
    SyndromeType type = SyndromeType::Unknown;
};

struct DecodeRequest {
    std::string code_id;
    int round_index = 0;
    int n_qubits = 0;

    std::vector<SyndromeEvent> events;
    std::vector<SyndromeDense> dense;

    NoiseParams noise;
    std::unordered_map<std::string, std::string> metadata;
};

struct Correction {
    std::vector<int> qubit_flips;
    std::vector<int> qubit_flips_x;
    std::vector<int> qubit_flips_z;
    double confidence = 0.0;
    std::string decoder_name;
};

struct DecodeResponse {
    Correction correction;
    std::unordered_map<std::string, std::string> diagnostics;
};

inline bool preferDenseSyndrome(int n_bits, int event_count, double threshold = 0.12) {
    if (n_bits <= 0) return false;
    const double occ = static_cast<double>(event_count) / static_cast<double>(n_bits);
    return occ >= threshold;
}

} // namespace decoder_io
