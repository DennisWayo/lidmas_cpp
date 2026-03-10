#pragma once

#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

#include "cv/gaussian_noise.hpp"
#include "gkp/gkp_digitizer.hpp"
#include "qec/LogicalOperators.h"
#include "surface/ISurfaceDecoderPlugin.h"
#include "surface/MWPMDecoder.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfaceCorrection.h"
#include "surface/SurfacePipeline.h"
#include "surface/SurfaceSyndrome.h"

class HybridEngine {
public:
    struct TrialResult {
        bool logical_failure = false;
        bool decoder_failed = false;
        int defect_count = 0;
        int correction_weight = 0;
        std::vector<int> syndrome_sz;
        std::vector<int> correction_flips;
        std::string error_message;
    };

    HybridEngine(int distance,
                 double sigma,
                 uint64_t seed)
        : d(distance),
          noise(sigma, seed),
          digitizer(),
          code(distance),
          pipeline(code),
          decoder(code, MWPMDecoder::GraphMode::FULL),
          hz_rows(buildSparseRows(code.Hz())) {}

    void run_trial() {
        run_trial(nullptr);
    }

    void run_trial(ISurfaceDecoderPlugin* plugin) {
        last_ = TrialResult{};
        const int n = code.n();

        std::vector<int> ex(n, 0);
        std::vector<int> ez(n, 0);
        for (int q = 0; q < n; ++q) {
            const auto [dq, dp] = noise.sample();
            const PauliError e = digitizer.digitize(dq, dp);
            ex[q] = e.x_flip ? 1 : 0;
            ez[q] = e.z_flip ? 1 : 0;
        }

        SurfaceSyndrome syn;
        syn.sz.assign(hz_rows.size(), 0);
        for (size_t r = 0; r < hz_rows.size(); ++r) {
            int parity = 0;
            for (int c : hz_rows[r]) parity ^= (ex[c] & 1);
            syn.sz[r] = parity & 1;
            last_.defect_count += syn.sz[r];
        }
        last_.syndrome_sz = syn.sz;

        try {
            SurfaceCorrection corr;
            if (plugin != nullptr) {
                corr = plugin->decode(syn, code);
            } else {
                corr = bitmaskToCorrection(decoder.decode(syn));
            }
            const std::vector<int> syn_after = syndromeFromCorrection(hz_rows, code.n(), corr);

            bool invariant_ok = (syn_after.size() == syn.sz.size());
            if (invariant_ok) {
                for (size_t i = 0; i < syn_after.size(); ++i) {
                    if ((syn_after[i] & 1) != (syn.sz[i] & 1)) {
                        invariant_ok = false;
                        break;
                    }
                }
            }

            last_.correction_flips = corr.qubit_flips;
            last_.correction_weight = corr.weight;
            if (last_.correction_weight == 0 && !last_.correction_flips.empty()) {
                last_.correction_weight = static_cast<int>(last_.correction_flips.size());
            }

            if (!invariant_ok) {
                last_.decoder_failed = true;
                last_.logical_failure = true;
                last_.error_message = "hybrid invariant mismatch: H*correction != syndrome";
                return;
            }

            int logical_x_parity = dot_mod2(ex, code.logicalXSupport());
            int logical_z_parity = dot_mod2(ex, code.logicalZSupport());
            const auto& lx = code.logicalXSupport();
            const auto& lz = code.logicalZSupport();
            for (int q : last_.correction_flips) {
                if (q < 0 || q >= n) continue;
                logical_x_parity ^= (lx[q] & 1);
                logical_z_parity ^= (lz[q] & 1);
            }
            (void)ez; // reserved for future X-check decoding path.
            last_.logical_failure = ((logical_x_parity & 1) != 0) || ((logical_z_parity & 1) != 0);
        } catch (const std::exception& exn) {
            last_.decoder_failed = true;
            last_.logical_failure = true;
            last_.error_message = exn.what();
        } catch (...) {
            last_.decoder_failed = true;
            last_.logical_failure = true;
            last_.error_message = "unknown exception";
        }
    }

    const TrialResult& last_result() const {
        return last_;
    }

private:
    using SparseRows = std::vector<std::vector<int>>;

    static SparseRows buildSparseRows(const BinaryMatrix& H) {
        SparseRows rows(static_cast<size_t>(H.rows()));
        for (int r = 0; r < H.rows(); ++r) {
            auto& row = rows[static_cast<size_t>(r)];
            row.reserve(static_cast<size_t>(H.cols() / 8 + 1));
            for (int c = 0; c < H.cols(); ++c) {
                if ((H.get(r, c) & 1) != 0) row.push_back(c);
            }
        }
        return rows;
    }

    static std::vector<int> syndromeFromCorrection(const SparseRows& rows,
                                                   int n_data,
                                                   const SurfaceCorrection& corr) {
        std::vector<unsigned char> mask(static_cast<size_t>(std::max(0, n_data)), 0);
        for (int q : corr.qubit_flips) {
            if (q >= 0 && q < n_data) mask[static_cast<size_t>(q)] ^= 1u;
        }

        std::vector<int> syn(rows.size(), 0);
        for (size_t r = 0; r < rows.size(); ++r) {
            int parity = 0;
            for (int c : rows[r]) parity ^= static_cast<int>(mask[static_cast<size_t>(c)] & 1u);
            syn[r] = parity & 1;
        }
        return syn;
    }

    static SurfaceCorrection bitmaskToCorrection(const std::vector<int>& bitmask) {
        SurfaceCorrection corr;
        corr.qubit_flips.reserve(bitmask.size());
        for (int i = 0; i < static_cast<int>(bitmask.size()); ++i) {
            if ((bitmask[i] & 1) != 0) corr.qubit_flips.push_back(i);
        }
        corr.weight = static_cast<int>(corr.qubit_flips.size());
        return corr;
    }

    int d = 0;
    GaussianNoise noise;
    GKPDigitizer digitizer;
    SurfaceCode code;
    SurfacePipeline pipeline;
    MWPMDecoder decoder;
    SparseRows hz_rows;
    TrialResult last_;
};
