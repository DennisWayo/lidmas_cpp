#pragma once

#include <cstdint>
#include <random>
#include <vector>

enum class Pauli : uint8_t { I = 0, X = 1, Z = 2, Y = 3 };

struct PauliSample {
    std::vector<int> eX;             // X-component of Pauli error
    std::vector<int> eZ;             // Z-component of Pauli error
    std::vector<Pauli> paulis;       // Optional debug trace per qubit
};

class PauliChannel {
public:
    static PauliSample sampleIndependentXZ(int n, double pX, double pZ, std::mt19937& rng);
    static PauliSample sampleDepolarizing(int n, double p, std::mt19937& rng);
};
