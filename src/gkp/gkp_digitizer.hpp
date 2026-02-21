#pragma once

#include <cmath>
#include <cstdlib>

struct PauliError {
    bool x_flip = false;
    bool z_flip = false;
};

class GKPDigitizer {
public:
    explicit GKPDigitizer(double lattice_scale = std::sqrt(3.14159265358979323846))
        : scale((lattice_scale > 0.0) ? lattice_scale : std::sqrt(3.14159265358979323846)) {}

    PauliError digitize(double dq, double dp) {
        const long long n_q = std::llround(dq / scale);
        const long long n_p = std::llround(dp / scale);
        PauliError out;
        out.x_flip = (std::llabs(n_q) % 2LL) == 1LL;
        out.z_flip = (std::llabs(n_p) % 2LL) == 1LL;
        return out;
    }

private:
    double scale = std::sqrt(3.14159265358979323846);
};
