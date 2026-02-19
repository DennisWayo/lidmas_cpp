#include "qec/PauliChannel.h"
#include <algorithm>

PauliSample PauliChannel::sampleIndependentXZ(int n, double pX, double pZ, std::mt19937& rng) {
    const double px = std::clamp(pX, 0.0, 1.0);
    const double pz = std::clamp(pZ, 0.0, 1.0);

    std::bernoulli_distribution dx(px);
    std::bernoulli_distribution dz(pz);

    PauliSample out;
    out.eX.assign(n, 0);
    out.eZ.assign(n, 0);
    out.paulis.assign(n, Pauli::I);

    for (int i = 0; i < n; ++i) {
        const int x = dx(rng) ? 1 : 0;
        const int z = dz(rng) ? 1 : 0;
        out.eX[i] = x;
        out.eZ[i] = z;

        if (x && z) out.paulis[i] = Pauli::Y;
        else if (x) out.paulis[i] = Pauli::X;
        else if (z) out.paulis[i] = Pauli::Z;
        else out.paulis[i] = Pauli::I;
    }

    return out;
}

PauliSample PauliChannel::sampleDepolarizing(int n, double p, std::mt19937& rng) {
    const double pp = std::clamp(p, 0.0, 1.0);
    std::bernoulli_distribution has_error(pp);
    std::uniform_int_distribution<int> pick(0, 2);  // 0:X, 1:Z, 2:Y

    PauliSample out;
    out.eX.assign(n, 0);
    out.eZ.assign(n, 0);
    out.paulis.assign(n, Pauli::I);

    for (int i = 0; i < n; ++i) {
        if (!has_error(rng)) {
            out.paulis[i] = Pauli::I;
            continue;
        }

        const int k = pick(rng);
        if (k == 0) {
            out.eX[i] = 1;
            out.eZ[i] = 0;
            out.paulis[i] = Pauli::X;
        } else if (k == 1) {
            out.eX[i] = 0;
            out.eZ[i] = 1;
            out.paulis[i] = Pauli::Z;
        } else {
            out.eX[i] = 1;
            out.eZ[i] = 1;
            out.paulis[i] = Pauli::Y;
        }
    }

    return out;
}
