#include "surface/SurfaceSyndrome.h"
#include <algorithm>
#include <random>

SurfaceSyndrome SurfaceSyndrome::sample(const SurfaceCode& code,
                                        double px,
                                        double pz,
                                        uint64_t seed) {
    SurfaceSyndrome out;
    const int n = code.n();

    out.ex.assign(n, 0);
    out.ez.assign(n, 0);

    const double px_c = std::clamp(px, 0.0, 1.0);
    const double pz_c = std::clamp(pz, 0.0, 1.0);
    std::mt19937_64 rng(seed);
    std::bernoulli_distribution x_flip(px_c);
    std::bernoulli_distribution z_flip(pz_c);

    for (int i = 0; i < n; ++i) {
        out.ex[i] = x_flip(rng) ? 1 : 0;
        out.ez[i] = z_flip(rng) ? 1 : 0;
    }

    out.sx = code.Hx().multiply(out.ez);  // X checks detect Z errors.
    out.sz = code.Hz().multiply(out.ex);  // Z checks detect X errors.
    for (int& v : out.sx) v &= 1;
    for (int& v : out.sz) v &= 1;

    return out;
}
