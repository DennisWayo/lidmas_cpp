#include "surface/MWPMStubDecoder.h"

#include <limits>

MWPMStubDecoder::MWPMStubDecoder(const SurfaceCode& code)
    : code_(code),
      pipeline_(code) {}

std::vector<int> MWPMStubDecoder::decode(const SurfaceSyndrome& syn) {
    std::vector<int> correction(code_.n(), 0);

    MatchingProblem mp = pipeline_.buildMatchingProblemFromSyndrome(syn);
    const int n_def = mp.numDefects();
    if (n_def == 0) return correction;

    std::vector<int> used(n_def, 0);
    const auto& defects = mp.defects();

    // Placeholder decoder: greedy nearest-neighbor pairing with optional boundary pairing.
    for (int i = 0; i < n_def; ++i) {
        if (used[i]) continue;

        int best_j = -1;
        int best_w = std::numeric_limits<int>::max();
        for (int j = i + 1; j < n_def; ++j) {
            if (used[j]) continue;
            const int w = mp.pairWeight(i, j);
            if (w < best_w) {
                best_w = w;
                best_j = j;
            }
        }

        const int b_w = mp.boundaryWeight(i);
        if (best_j >= 0 && best_w <= b_w) {
            used[i] = 1;
            used[best_j] = 1;
            const int q = (defects[i].id + defects[best_j].id) % code_.n();
            correction[q] ^= 1;
        } else {
            used[i] = 1;
            const int q = defects[i].id % code_.n();
            correction[q] ^= 1;
        }
    }

    return correction;
}
