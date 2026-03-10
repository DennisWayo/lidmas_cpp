#include "sim/SurfaceThresholdRunner.h"

#include <algorithm>
#include <cmath>
#include <chrono>
#include <cstdlib>
#include <cstdint>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <set>
#include <sstream>
#include <string>
#include <stdexcept>
#include <random>
#include <utility>
#include <vector>
#include <atomic>
#include <cstdio>

#include "core/DecoderConfig.h"
#include "core/PluginRegistry.h"
#include "core/RegisterPlugins.h"
#include "cv/gaussian_noise.hpp"
#include "gkp/gkp_digitizer.hpp"
#include "gpu/SurfaceGpuSampler.h"
#include "hybrid/hybrid_engine.hpp"
#include "qec/LogicalOperators.h"
#include "surface/ISurfaceDecoderPlugin.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfaceCorrection.h"
#include "surface/SurfacePipeline.h"
#include "surface/SurfaceSyndrome.h"
#include "surface/SyndromeGraph.h"
#include "surface/ScalingAnalysis.h"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

struct PointAccum {
    long long trials = 0;
    long long fail_count = 0;
    long long decoder_fail_count = 0;
    double defect_sum = 0.0;
    double defect_sumsq = 0.0;
    double weight_sum = 0.0;
    double weight_sumsq = 0.0;
};

struct PointStats {
    long long trials = 0;
    long long fail_count = 0;
    double ler = 0.0;
    double ler_lo95 = 0.0;
    double ler_hi95 = 0.0;
    double ci_halfwidth = 0.0;
    double defect_avg = 0.0;
    double defect_stderr = 0.0;
    double weight_avg = 0.0;
    double weight_stderr = 0.0;
    double decoder_fail_rate = 0.0;
    bool ci_target_met = false;
};

struct ThresholdResult {
    int distance = 0;
    double sigma = 0.0;
    double ler = 0.0;
};

struct ThresholdPoint {
    int d = 0;
    double p = 0.0;
    double LER = 0.0;
    double LER_low = 0.0;
    double LER_high = 0.0;
};

struct CrossingPoint {
    int d_small = 0;
    int d_large = 0;
    double p_cross = 0.0;
};

struct ScalingFitResult {
    bool valid = false;
    double p_c = 0.0;
    double nu = 1.0;
    double cost = std::numeric_limits<double>::infinity();
};

struct CrossingAggregate {
    bool valid = false;
    double pc = 0.0;
    double pc_low = 0.0;
    double pc_high = 0.0;
};

std::string normalizeDecoderName(const std::string& name) {
    if (name == "stub" || name == "mwpm_stub") return "stub";
    if (name == "mwpm") return "mwpm";
    if (name == "uf") return "uf";
    if (name == "neural_mwpm") return "neural_mwpm";
    if (name == "bp") return "bp";
    return "mwpm";
}

bool fileExists(const std::string& path) {
    if (path.empty()) return false;
    std::ifstream in(path);
    return in.good();
}

const char* noiseModeName(NoiseMode mode) {
    switch (mode) {
        case NoiseMode::Hybrid: return "hybrid";
        case NoiseMode::GKP: return "gkp";
        case NoiseMode::Pauli:
        default: return "pauli";
    }
}

std::vector<double> makeSweepGrid(double start, double end, double step) {
    std::vector<double> out;
    if (step <= 0.0) return out;
    if (end < start) std::swap(start, end);
    for (double x = start; x <= end + 1e-12; x += step) out.push_back(x);
    return out;
}

std::string iso8601NowUtc() {
    const auto now = std::chrono::system_clock::now();
    const std::time_t t = std::chrono::system_clock::to_time_t(now);
    std::tm tm_utc{};
#if defined(_WIN32)
    gmtime_s(&tm_utc, &t);
#else
    gmtime_r(&t, &tm_utc);
#endif
    std::ostringstream oss;
    oss << std::put_time(&tm_utc, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}

std::string distancesCsv(const std::vector<int>& dists) {
    std::ostringstream oss;
    for (size_t i = 0; i < dists.size(); ++i) {
        if (i > 0) oss << ",";
        oss << dists[i];
    }
    return oss.str();
}

std::vector<std::pair<std::pair<int, int>, double>> estimateSigmaCrossings(
    const std::vector<ThresholdResult>& results,
    const std::vector<int>& distances) {
    std::vector<std::pair<std::pair<int, int>, double>> out;
    if (distances.size() < 2) return out;

    for (size_t i = 0; i + 1 < distances.size(); ++i) {
        const int d1 = distances[i];
        const int d2 = distances[i + 1];
        double best_sigma = 0.0;
        double best_diff = std::numeric_limits<double>::infinity();

        for (const auto& a : results) {
            if (a.distance != d1) continue;
            for (const auto& b : results) {
                if (b.distance != d2) continue;
                if (std::abs(a.sigma - b.sigma) > 1e-9) continue;
                const double diff = std::abs(a.ler - b.ler);
                if (diff < best_diff) {
                    best_diff = diff;
                    best_sigma = a.sigma;
                }
            }
        }

        if (std::isfinite(best_diff)) {
            out.push_back({{d1, d2}, best_sigma});
        }
    }
    return out;
}

bool writeSigmaPlotScript(const std::string& csv_path,
                          const std::string& script_path,
                          const std::string& mode_filter,
                          const std::string& title) {
    std::ostringstream py;
    py << "import pandas as pd\n";
    py << "import matplotlib.pyplot as plt\n\n";
    py << "df = pd.read_csv(\"" << csv_path << "\")\n";
    py << "df = df[df[\"mode\"] == \"" << mode_filter << "\"]\n\n";
    py << "for d in sorted(df[\"distance\"].unique()):\n";
    py << "    sub = df[df[\"distance\"] == d]\n";
    py << "    plt.plot(sub[\"sigma\"], sub[\"ler\"], marker='o', label=f\"d={d}\")\n\n";
    py << "plt.xlabel(\"Sigma (CV noise)\")\n";
    py << "plt.ylabel(\"Logical Error Rate\")\n";
    py << "plt.title(\"" << title << "\")\n";
    py << "plt.legend()\n";
    py << "plt.grid(True)\n";
    py << "plt.savefig(\"threshold_plot.png\", dpi=300)\n";

    std::ofstream out(script_path, std::ios::out | std::ios::trunc);
    if (!out.is_open()) return false;
    out << py.str();
    out.flush();
    return true;
}

double percentile(std::vector<double> vals, double q) {
    if (vals.empty()) return std::numeric_limits<double>::quiet_NaN();
    q = std::clamp(q, 0.0, 1.0);
    std::sort(vals.begin(), vals.end());
    const double idx = q * static_cast<double>(vals.size() - 1);
    const size_t lo = static_cast<size_t>(std::floor(idx));
    const size_t hi = static_cast<size_t>(std::ceil(idx));
    if (lo == hi) return vals[lo];
    const double t = idx - static_cast<double>(lo);
    return vals[lo] * (1.0 - t) + vals[hi] * t;
}

CrossingAggregate aggregateCrossings(const std::vector<CrossingEstimate>& crossings) {
    CrossingAggregate out;
    std::vector<double> pcs;
    std::vector<double> lows;
    std::vector<double> highs;
    for (const auto& c : crossings) {
        if (c.quality >= 0.5) {
            pcs.push_back(c.pc);
            lows.push_back(c.pc_low);
            highs.push_back(c.pc_high);
        }
    }
    if (pcs.empty()) {
        for (const auto& c : crossings) {
            pcs.push_back(c.pc);
            lows.push_back(c.pc_low);
            highs.push_back(c.pc_high);
        }
    }
    if (pcs.empty()) return out;
    out.valid = true;
    out.pc = percentile(pcs, 0.5);
    out.pc_low = percentile(lows, 0.5);
    out.pc_high = percentile(highs, 0.5);
    return out;
}

std::string crossingPairsString(const std::vector<CrossingEstimate>& crossings) {
    std::set<std::pair<int, int>> pairs;
    for (const auto& c : crossings) pairs.insert({c.d1, c.d2});
    std::ostringstream oss;
    bool first = true;
    for (const auto& pr : pairs) {
        if (!first) oss << ", ";
        first = false;
        oss << "d=" << pr.first << " vs " << pr.second;
    }
    return oss.str();
}

bool writeTextFile(const std::string& path, const std::string& content) {
    std::ofstream out(path, std::ios::out | std::ios::trunc);
    if (!out.is_open()) return false;
    out << content;
    out.flush();
    return true;
}

std::string makeScalingReportMarkdown(const SurfaceThresholdConfig& cfg,
                                      const std::vector<SweepPoint>& pts,
                                      const std::vector<CrossingEstimate>& crossings,
                                      const CrossingAggregate& agg,
                                      const CollapseFitResult* collapse) {
    std::set<int> dset;
    for (const auto& pt : pts) dset.insert(pt.d);

    std::ostringstream oss;
    oss << "# LiDMaS+ v0.9 Finite-Size Scaling Report\n\n";
    oss << "## Configuration\n\n";
    oss << "- decoder: `" << cfg.decoder_name << "`\n";
    oss << "- mwpm_graph: `" << cfg.mwpm_graph << "`\n";
    oss << "- weight_mode: `" << cfg.weight_mode << "`\n";
    oss << "- mode: `" << noiseModeName(cfg.mode) << "`\n";
    if (cfg.mode == NoiseMode::Hybrid) {
        oss << "- cv_sigma: " << cfg.cv_sigma << "\n";
    }
    oss << "- p range: [" << cfg.p_start << ", " << cfg.p_end << "] step " << cfg.p_step << "\n";
    oss << "- bootstrap_samples: " << cfg.scaling_bootstrap << "\n";
    oss << "- scaling_seed: " << cfg.scaling_seed << "\n";
    oss << "- grid: pc=" << cfg.grid_pc << ", nu=" << cfg.grid_nu << "\n";
    oss << "- smoothing eps: " << cfg.ler_smooth_eps << "\n\n";

    oss << "## Distances\n\n- ";
    bool first = true;
    for (int d : dset) {
        if (!first) oss << ", ";
        first = false;
        oss << d;
    }
    oss << "\n\n";

    oss << "## Crossing Estimates\n\n";
    if (crossings.empty()) {
        oss << "No crossings detected. Consider increasing p-resolution or trials.\n\n";
    } else {
        oss << "| d1 | d2 | p_c | p_c_low | p_c_high | quality |\n";
        oss << "|---:|---:|---:|---:|---:|---:|\n";
        for (const auto& c : crossings) {
            oss << "|" << c.d1
                << "|" << c.d2
                << "|" << std::fixed << std::setprecision(6) << c.pc
                << "|" << c.pc_low
                << "|" << c.pc_high
                << "|" << std::setprecision(3) << c.quality << "|\n";
        }
        if (agg.valid) {
            oss << "\nAggregate crossing median p_c = " << std::setprecision(6) << agg.pc
                << " [" << agg.pc_low << ", " << agg.pc_high << "]\n\n";
        }
    }

    oss << "## Collapse Fit\n\n";
    if (collapse == nullptr || !std::isfinite(collapse->cost)) {
        oss << "Collapse fit unavailable.\n";
    } else {
        oss << "- Best p_c = " << std::fixed << std::setprecision(6) << collapse->pc
            << " [" << collapse->pc_low << ", " << collapse->pc_high << "]\n";
        oss << "- Best nu = " << collapse->nu
            << " [" << collapse->nu_low << ", " << collapse->nu_high << "]\n";
        oss << "- Collapse cost = " << std::setprecision(8) << collapse->cost << "\n";
        oss << "- Bootstrap samples = " << collapse->bootstrap_samples << "\n";
    }
    return oss.str();
}

std::string makeScalingSummaryJson(uint64_t seed,
                                   const std::vector<CrossingEstimate>& crossings,
                                   const CrossingAggregate& agg,
                                   const CollapseFitResult* collapse) {
    std::ostringstream oss;
    oss << "{\n";
    oss << "  \"seed\": " << seed << ",\n";
    oss << "  \"crossings\": [\n";
    for (size_t i = 0; i < crossings.size(); ++i) {
        const auto& c = crossings[i];
        oss << "    {\"d1\": " << c.d1
            << ", \"d2\": " << c.d2
            << ", \"pc\": " << std::setprecision(12) << c.pc
            << ", \"pc_low\": " << c.pc_low
            << ", \"pc_high\": " << c.pc_high
            << ", \"quality\": " << c.quality << "}";
        if (i + 1 < crossings.size()) oss << ",";
        oss << "\n";
    }
    oss << "  ],\n";
    if (agg.valid) {
        oss << "  \"crossing_median_pc\": " << agg.pc << ",\n";
        oss << "  \"crossing_median_pc_low\": " << agg.pc_low << ",\n";
        oss << "  \"crossing_median_pc_high\": " << agg.pc_high << ",\n";
    } else {
        oss << "  \"crossing_median_pc\": null,\n";
        oss << "  \"crossing_median_pc_low\": null,\n";
        oss << "  \"crossing_median_pc_high\": null,\n";
    }
    if (collapse != nullptr && std::isfinite(collapse->cost)) {
        oss << "  \"collapse\": {\n";
        oss << "    \"pc\": " << collapse->pc << ",\n";
        oss << "    \"nu\": " << collapse->nu << ",\n";
        oss << "    \"cost\": " << collapse->cost << ",\n";
        oss << "    \"pc_low\": " << collapse->pc_low << ",\n";
        oss << "    \"pc_high\": " << collapse->pc_high << ",\n";
        oss << "    \"nu_low\": " << collapse->nu_low << ",\n";
        oss << "    \"nu_high\": " << collapse->nu_high << ",\n";
        oss << "    \"bootstrap_samples\": " << collapse->bootstrap_samples << "\n";
        oss << "  }\n";
    } else {
        oss << "  \"collapse\": null\n";
    }
    oss << "}\n";
    return oss.str();
}

std::vector<double> makePGrid(double p_start, double p_end, double p_step) {
    std::vector<double> out;
    if (p_step <= 0.0) return out;
    for (double p = p_start; p <= p_end + 1e-12; p += p_step) out.push_back(p);
    return out;
}

uint64_t mix64(uint64_t x) {
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return x;
}

uint64_t thresholdTrialSeed(uint64_t base_seed,
                            int d,
                            int p_key,
                            long long trial_index,
                            int thread_id) {
    uint64_t s = base_seed;
    s ^= mix64(static_cast<uint64_t>(d) + 0x9e3779b97f4a7c15ULL);
    s ^= mix64(static_cast<uint64_t>(p_key) + 0x94d049bb133111ebULL);
    s ^= mix64(static_cast<uint64_t>(trial_index) + 0xbf58476d1ce4e5b9ULL);
    s ^= mix64(static_cast<uint64_t>(thread_id) + 0x27d4eb2f165667c5ULL);
    return mix64(s);
}

struct SingleTrialResult {
    bool logical_failure = false;
    bool decoder_failed = false;
    int defect_count = 0;
    int correction_weight = 0;
    std::string failure_dump;
};

struct GKPNoiseConfig {
    double gate_error = 0.0;
    double meas_error = 0.0;
    double idle_error = 0.0;
    double loss_prob = 0.0;
    std::vector<double> loss_map;
};

using SparseRows = std::vector<std::vector<int>>;

SparseRows buildSparseRows(const BinaryMatrix& H) {
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

struct SzTrialSample {
    std::vector<int> ex;
    std::vector<int> sz;
};

struct GkpTrialSample {
    std::vector<int> ex;
    std::vector<int> ez;
    std::vector<int> sx;
    std::vector<int> sz;
};

SzTrialSample sampleSzOnly(const SurfaceCode& code,
                           const SparseRows& hz_rows,
                           double p,
                           uint64_t seed) {
    SzTrialSample out;
    const int n = code.n();
    out.ex.assign(n, 0);

    const double pc = std::clamp(p, 0.0, 1.0);
    std::mt19937_64 rng(seed);
    std::bernoulli_distribution x_flip(pc);
    std::bernoulli_distribution z_flip(pc);

    // Keep RNG draw order aligned with full (X,Z) sampling: draw both per qubit.
    for (int i = 0; i < n; ++i) {
        out.ex[i] = x_flip(rng) ? 1 : 0;
        (void)z_flip(rng);
    }

    out.sz.assign(hz_rows.size(), 0);
    for (size_t r = 0; r < hz_rows.size(); ++r) {
        int parity = 0;
        const auto& row = hz_rows[r];
        for (int c : row) parity ^= (out.ex[c] & 1);
        out.sz[r] = parity;
    }
    return out;
}

GkpTrialSample sampleGkp(const SurfaceCode& code,
                         const SparseRows& hx_rows,
                         const SparseRows& hz_rows,
                         double sigma,
                         const GKPNoiseConfig& noise_cfg,
                         uint64_t seed) {
    GkpTrialSample out;
    const int n = code.n();
    out.ex.assign(n, 0);
    out.ez.assign(n, 0);

    std::mt19937_64 rng(seed);
    const double sigma_eff = std::max(0.0, sigma);
    std::normal_distribution<double> gauss(0.0, sigma_eff);
    std::bernoulli_distribution gate_flip(std::clamp(noise_cfg.gate_error, 0.0, 1.0));
    std::bernoulli_distribution idle_flip(std::clamp(noise_cfg.idle_error, 0.0, 1.0));

    GKPDigitizer digitizer;
    std::bernoulli_distribution random_bit(0.5);

    for (int q = 0; q < n; ++q) {
        const double dq = gauss(rng);
        const double dp = gauss(rng);
        const PauliError e = digitizer.digitize(dq, dp);
        int ex = e.x_flip ? 1 : 0;
        int ez = e.z_flip ? 1 : 0;

        if (gate_flip(rng)) ex ^= 1;
        if (gate_flip(rng)) ez ^= 1;
        if (idle_flip(rng)) ex ^= 1;
        if (idle_flip(rng)) ez ^= 1;

        double loss_p = noise_cfg.loss_prob;
        if (!noise_cfg.loss_map.empty()) {
            loss_p = noise_cfg.loss_map[static_cast<size_t>(q)];
        }
        if (loss_p > 0.0) {
            std::bernoulli_distribution loss_flip(std::clamp(loss_p, 0.0, 1.0));
            if (loss_flip(rng)) {
                ex = random_bit(rng) ? 1 : 0;
                ez = random_bit(rng) ? 1 : 0;
            }
        }

        out.ex[q] = ex;
        out.ez[q] = ez;
    }

    out.sx.assign(hx_rows.size(), 0);
    for (size_t r = 0; r < hx_rows.size(); ++r) {
        int parity = 0;
        for (int c : hx_rows[r]) parity ^= (out.ez[c] & 1);
        out.sx[r] = parity & 1;
    }

    out.sz.assign(hz_rows.size(), 0);
    for (size_t r = 0; r < hz_rows.size(); ++r) {
        int parity = 0;
        for (int c : hz_rows[r]) parity ^= (out.ex[c] & 1);
        out.sz[r] = parity & 1;
    }

    const double meas_p = std::clamp(noise_cfg.meas_error, 0.0, 1.0);
    if (meas_p > 0.0) {
        std::bernoulli_distribution meas_flip(meas_p);
        for (int& v : out.sx) v ^= meas_flip(rng) ? 1 : 0;
        for (int& v : out.sz) v ^= meas_flip(rng) ? 1 : 0;
    }

    return out;
}

std::string formatVector(const std::vector<int>& v, size_t max_items = 256) {
    std::ostringstream oss;
    oss << "[";
    const size_t n = std::min(v.size(), max_items);
    for (size_t i = 0; i < n; ++i) {
        if (i > 0) oss << ",";
        oss << (v[i] & 1);
    }
    if (v.size() > max_items) {
        oss << ",...(" << v.size() << " total)";
    }
    oss << "]";
    return oss.str();
}

std::string formatIntVector(const std::vector<int>& v, size_t max_items = 256) {
    std::ostringstream oss;
    oss << "[";
    const size_t n = std::min(v.size(), max_items);
    for (size_t i = 0; i < n; ++i) {
        if (i > 0) oss << ",";
        oss << v[i];
    }
    if (v.size() > max_items) {
        oss << ",...(" << v.size() << " total)";
    }
    oss << "]";
    return oss.str();
}

std::string formatOneIndices(const std::vector<int>& v, size_t max_items = 256) {
    std::ostringstream oss;
    oss << "[";
    size_t written = 0;
    size_t total = 0;
    for (size_t i = 0; i < v.size(); ++i) {
        if ((v[i] & 1) == 0) continue;
        total += 1;
        if (written < max_items) {
            if (written > 0) oss << ",";
            oss << i;
            written += 1;
        }
    }
    if (total > max_items) {
        oss << ",...(" << total << " defects)";
    }
    oss << "]";
    return oss.str();
}

std::string formatCoords(const std::vector<LatticeCoord>& coords, size_t max_items = 256) {
    std::ostringstream oss;
    oss << "[";
    const size_t n = std::min(coords.size(), max_items);
    for (size_t i = 0; i < n; ++i) {
        if (i > 0) oss << ",";
        oss << "(" << coords[i].r << "," << coords[i].c << ")";
    }
    if (coords.size() > max_items) {
        oss << ",...(" << coords.size() << " total)";
    }
    oss << "]";
    return oss.str();
}

std::string extractLineAfterKey(const std::string& text, const std::string& key) {
    const size_t pos = text.find(key);
    if (pos == std::string::npos) return "";
    size_t end = text.find('\n', pos);
    if (end == std::string::npos) end = text.size();
    return text.substr(pos + key.size(), end - (pos + key.size()));
}

std::vector<int> syndromeFromCorrection(const SparseRows& hz_rows,
                                        int n_data,
                                        const SurfaceCorrection& corr) {
    std::vector<unsigned char> mask(static_cast<size_t>(std::max(0, n_data)), 0);
    for (int q : corr.qubit_flips) {
        if (q >= 0 && q < n_data) mask[static_cast<size_t>(q)] ^= 1u;
    }

    std::vector<int> syn(hz_rows.size(), 0);
    for (size_t r = 0; r < hz_rows.size(); ++r) {
        int parity = 0;
        for (int c : hz_rows[r]) parity ^= static_cast<int>(mask[static_cast<size_t>(c)] & 1u);
        syn[r] = parity & 1;
    }
    return syn;
}

std::string buildFailureDump(const std::string& decoder_name,
                             int d,
                             double p,
                             long long trial_index,
                             uint64_t seed,
                             const std::vector<int>& sx,
                             const std::vector<int>& sz,
                             const SurfaceCorrection* corr,
                             const std::vector<int>* syn_after,
                             const std::string& error_text) {
    std::ostringstream oss;
    std::vector<LatticeCoord> z_coords;
    std::vector<LatticeCoord> x_coords;
    try {
        if (!sz.empty()) z_coords = GetZDefects(sz, d);
    } catch (...) {
    }
    try {
        if (!sx.empty()) x_coords = GetXDefects(sx, d);
    } catch (...) {
    }

    oss << "decoder=" << decoder_name << "\n";
    oss << "d=" << d << " p=" << std::setprecision(12) << p << " trial=" << trial_index << "\n";
    oss << "seed=" << seed << "\n";
    oss << "syndrome_sx=" << formatVector(sx) << "\n";
    oss << "syndrome_sz=" << formatVector(sz) << "\n";
    oss << "defect_coords_sx=" << formatCoords(x_coords) << "\n";
    oss << "defect_coords_sz=" << formatCoords(z_coords) << "\n";
    oss << "defect_rows_sz=" << formatOneIndices(sz) << "\n";
    if (corr != nullptr) {
        const int weight = (corr->weight > 0) ? corr->weight : static_cast<int>(corr->qubit_flips.size());
        oss << "correction_weight=" << weight << "\n";
        oss << "correction_num_flips=" << corr->qubit_flips.size() << "\n";
        oss << "correction_flips=" << formatIntVector(corr->qubit_flips) << "\n";
    } else {
        oss << "correction_weight=unavailable\n";
        oss << "correction_num_flips=unavailable\n";
        oss << "correction_flips=unavailable\n";
    }
    if (syn_after != nullptr) {
        oss << "syndrome_after_correction=" << formatVector(*syn_after) << "\n";
    } else {
        oss << "syndrome_after_correction=unavailable\n";
    }
    const std::string boundary_matches = extractLineAfterKey(error_text, "boundary_matches=");
    if (!boundary_matches.empty()) {
        oss << "boundary_match_for_defect=" << boundary_matches << "\n";
    }
    oss << "error=" << error_text << "\n";
    return oss.str();
}

SingleTrialResult run_single_trial_discrete(const SurfaceCode& code,
                                            const SparseRows& hz_rows,
                                            SurfacePipeline& pipeline,
                                            ISurfaceDecoderPlugin& plugin,
                                            const std::string& decoder_name,
                                            double p,
                                            uint64_t seed_base,
                                            int d,
                                            int p_key,
                                            long long trial_index,
                                            int thread_id) {
    (void)pipeline;
    const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, trial_index, thread_id);
    SzTrialSample sample = sampleSzOnly(code, hz_rows, p, seed);

    SingleTrialResult out;
    for (int v : sample.sz) out.defect_count += (v & 1);

    try {
        SurfaceSyndrome decode_syn;
        decode_syn.sz = sample.sz;
        const SurfaceCorrection corr = plugin.decode(decode_syn, code);

        const std::vector<int> syn_after = syndromeFromCorrection(hz_rows, code.n(), corr);
        bool invariant_ok = (syn_after.size() == sample.sz.size());
        if (invariant_ok) {
            for (size_t i = 0; i < syn_after.size(); ++i) {
                if ((syn_after[i] & 1) != (sample.sz[i] & 1)) {
                    invariant_ok = false;
                    break;
                }
            }
        }

        int weight = corr.weight;
        if (weight == 0 && !corr.qubit_flips.empty()) {
            weight = SurfacePipeline::correctionWeight(corr, code.n());
        }
        out.correction_weight = weight;

        if (!invariant_ok) {
            out.decoder_failed = true;
            out.logical_failure = true;
            out.failure_dump = buildFailureDump(
                decoder_name,
                d,
                p,
                trial_index,
                seed,
                {},
                sample.sz,
                &corr,
                &syn_after,
                "post-decode invariant mismatch: H*correction != syndrome");
            return out;
        }

        int logical_x_parity = dot_mod2(sample.ex, code.logicalXSupport());
        int logical_z_parity = dot_mod2(sample.ex, code.logicalZSupport());
        const auto& lx = code.logicalXSupport();
        const auto& lz = code.logicalZSupport();
        for (int q : corr.qubit_flips) {
            if (q < 0 || q >= code.n()) continue;
            logical_x_parity ^= (lx[q] & 1);
            logical_z_parity ^= (lz[q] & 1);
        }
        out.logical_failure = ((logical_x_parity & 1) != 0) || ((logical_z_parity & 1) != 0);
    } catch (const std::exception& ex) {
        out.decoder_failed = true;
        out.logical_failure = true;
        out.correction_weight = 0;
        out.failure_dump = buildFailureDump(
            decoder_name,
            d,
            p,
            trial_index,
            seed,
            {},
            sample.sz,
            nullptr,
            nullptr,
            ex.what());
    } catch (...) {
        out.decoder_failed = true;
        out.logical_failure = true;
        out.correction_weight = 0;
        out.failure_dump = buildFailureDump(
            decoder_name,
            d,
            p,
            trial_index,
            seed,
            {},
            sample.sz,
            nullptr,
            nullptr,
            "unknown exception");
    }

    return out;
}

SingleTrialResult run_single_trial_gkp(const SurfaceCode& code,
                                       const SparseRows& hx_rows,
                                       const SparseRows& hz_rows,
                                       ISurfaceDecoderPlugin& plugin,
                                       const std::string& decoder_name,
                                       double sigma,
                                       const GKPNoiseConfig& noise_cfg,
                                       uint64_t seed_base,
                                       int d,
                                       int p_key,
                                       long long trial_index,
                                       int thread_id) {
    const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, trial_index, thread_id);
    const GkpTrialSample sample = sampleGkp(code, hx_rows, hz_rows, sigma, noise_cfg, seed);

    SingleTrialResult out;
    for (int v : sample.sx) out.defect_count += (v & 1);
    for (int v : sample.sz) out.defect_count += (v & 1);

    try {
        SurfaceSyndrome syn_x;
        syn_x.sz = sample.sz;
        const SurfaceCorrection corr_x = plugin.decode(syn_x, code);

        SurfaceSyndrome syn_z;
        syn_z.sx = sample.sx;
        const SurfaceCorrection corr_z = plugin.decode(syn_z, code);

        const std::vector<int> syn_after_x = syndromeFromCorrection(hz_rows, code.n(), corr_x);
        const std::vector<int> syn_after_z = syndromeFromCorrection(hx_rows, code.n(), corr_z);

        bool invariant_ok_x = (syn_after_x.size() == sample.sz.size());
        if (invariant_ok_x) {
            for (size_t i = 0; i < syn_after_x.size(); ++i) {
                if ((syn_after_x[i] & 1) != (sample.sz[i] & 1)) {
                    invariant_ok_x = false;
                    break;
                }
            }
        }

        bool invariant_ok_z = (syn_after_z.size() == sample.sx.size());
        if (invariant_ok_z) {
            for (size_t i = 0; i < syn_after_z.size(); ++i) {
                if ((syn_after_z[i] & 1) != (sample.sx[i] & 1)) {
                    invariant_ok_z = false;
                    break;
                }
            }
        }

        int weight_x = corr_x.weight;
        if (weight_x == 0 && !corr_x.qubit_flips.empty()) {
            weight_x = SurfacePipeline::correctionWeight(corr_x, code.n());
        }
        int weight_z = corr_z.weight;
        if (weight_z == 0 && !corr_z.qubit_flips.empty()) {
            weight_z = SurfacePipeline::correctionWeight(corr_z, code.n());
        }
        out.correction_weight = weight_x + weight_z;

        if (!invariant_ok_x || !invariant_ok_z) {
            out.decoder_failed = true;
            out.logical_failure = true;
            const std::string err = (!invariant_ok_x ? "gkp invariant mismatch: Hz*Xcorr != sz"
                                                     : "gkp invariant mismatch: Hx*Zcorr != sx");
            out.failure_dump = buildFailureDump(
                decoder_name,
                d,
                sigma,
                trial_index,
                seed,
                sample.sx,
                sample.sz,
                (!invariant_ok_x ? &corr_x : &corr_z),
                (!invariant_ok_x ? &syn_after_x : &syn_after_z),
                err);
            return out;
        }

        std::vector<int> residual_ex = sample.ex;
        std::vector<int> residual_ez = sample.ez;
        for (int q : corr_x.qubit_flips) {
            if (q >= 0 && q < code.n()) residual_ex[q] ^= 1;
        }
        for (int q : corr_z.qubit_flips) {
            if (q >= 0 && q < code.n()) residual_ez[q] ^= 1;
        }

        out.logical_failure =
            (dot_mod2(residual_ex, code.logicalXSupport()) != 0) ||
            (dot_mod2(residual_ez, code.logicalZSupport()) != 0);
    } catch (const std::exception& ex) {
        out.decoder_failed = true;
        out.logical_failure = true;
        out.correction_weight = 0;
        out.failure_dump = buildFailureDump(
            decoder_name,
            d,
            sigma,
            trial_index,
            seed,
            sample.sx,
            sample.sz,
            nullptr,
            nullptr,
            ex.what());
    } catch (...) {
        out.decoder_failed = true;
        out.logical_failure = true;
        out.correction_weight = 0;
        out.failure_dump = buildFailureDump(
            decoder_name,
            d,
            sigma,
            trial_index,
            seed,
            sample.sx,
            sample.sz,
            nullptr,
            nullptr,
            "unknown exception");
    }

    return out;
}

SingleTrialResult run_single_trial_hybrid(ISurfaceDecoderPlugin* plugin,
                                          const std::string& decoder_name,
                                          double p,
                                          uint64_t seed_base,
                                          int d,
                                          int p_key,
                                          long long trial_index,
                                          int thread_id,
                                          double sigma) {
    const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, trial_index, thread_id);
    SingleTrialResult out;
    try {
        HybridEngine engine(d, sigma, seed);
        if (plugin != nullptr) {
            engine.run_trial(plugin);
        } else {
            engine.run_trial();
        }
        const auto& r = engine.last_result();
        out.logical_failure = r.logical_failure;
        out.decoder_failed = r.decoder_failed;
        out.defect_count = r.defect_count;
        out.correction_weight = r.correction_weight;
        if (r.decoder_failed) {
            SurfaceCorrection corr;
            corr.qubit_flips = r.correction_flips;
            corr.weight = r.correction_weight;
            out.failure_dump = buildFailureDump(
                decoder_name,
                d,
                p,
                trial_index,
                seed,
                {},
                r.syndrome_sz,
                r.correction_flips.empty() ? nullptr : &corr,
                nullptr,
                r.error_message.empty() ? "hybrid decoder failure" : r.error_message);
        }
    } catch (const std::exception& ex) {
        out.decoder_failed = true;
        out.logical_failure = true;
        out.correction_weight = 0;
        out.failure_dump = buildFailureDump(
            decoder_name,
            d,
            p,
            trial_index,
            seed,
            {},
            {},
            nullptr,
            nullptr,
            ex.what());
    } catch (...) {
        out.decoder_failed = true;
        out.logical_failure = true;
        out.correction_weight = 0;
        out.failure_dump = buildFailureDump(
            decoder_name,
            d,
            p,
            trial_index,
            seed,
            {},
            {},
            nullptr,
            nullptr,
            "unknown hybrid exception");
    }
    return out;
}

double sampleStderr(long long n, double sum, double sumsq) {
    if (n <= 1) return 0.0;
    const double dn = static_cast<double>(n);
    const double mean = sum / dn;
    double var = (sumsq - dn * mean * mean) / static_cast<double>(n - 1);
    if (var < 0.0) var = 0.0;
    return std::sqrt(var / dn);
}

void wilson95(long long fail_count,
              long long trials,
              double& ler,
              double& lo95,
              double& hi95,
              double& halfwidth) {
    if (trials <= 0) {
        ler = 0.0;
        lo95 = 0.0;
        hi95 = 1.0;
        halfwidth = 0.5;
        return;
    }

    constexpr double z = 1.959963984540054;
    const double n = static_cast<double>(trials);
    const double p = static_cast<double>(fail_count) / n;
    const double z2 = z * z;

    const double denom = 1.0 + z2 / n;
    const double center = (p + z2 / (2.0 * n)) / denom;
    const double spread = z * std::sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / denom;

    ler = p;
    lo95 = std::max(0.0, center - spread);
    hi95 = std::min(1.0, center + spread);
    halfwidth = spread;
}

PointAccum runBatchTrialsCpu(const SurfaceCode& code,
                             const SparseRows& hx_rows,
                             const SparseRows& hz_rows,
                             SurfacePipeline& pipeline,
                             const PluginRegistry& reg,
                             const std::string& decoder_name,
                             const DecoderConfig& dec_cfg,
                             NoiseMode mode,
                             const GKPNoiseConfig& gkp_cfg,
                             double cv_sigma,
                             double p,
                             uint64_t seed_base,
                             int d,
                             int p_key,
                             long long start_trial,
                             int batch_trials,
                             std::atomic<bool>& first_failure_dumped);

bool runBatchTrialsGpu(const SurfaceCode& code,
                       const SparseRows& hz_rows,
                       const PluginRegistry& reg,
                       const std::string& decoder_name,
                       const DecoderConfig& dec_cfg,
                       double p,
                       uint64_t seed_base,
                       int d,
                       int p_key,
                       long long start_trial,
                       int batch_trials,
                       gpu::SurfaceGpuSampler& gpu_sampler,
                       std::atomic<bool>& first_failure_dumped,
                       PointAccum* out,
                       std::string* error) {
    if (out == nullptr) {
        if (error) *error = "null output accumulator";
        return false;
    }
    *out = PointAccum{};
    if (batch_trials <= 0) return true;

    std::vector<unsigned char> ex_batch;
    std::vector<unsigned char> sz_batch;
    if (!gpu_sampler.sample_pauli_batch(p, seed_base, d, p_key, start_trial, batch_trials,
                                        ex_batch, sz_batch, error)) {
        return false;
    }

    const int n = code.n();
    const int m = static_cast<int>(hz_rows.size());
    if (static_cast<long long>(ex_batch.size()) < static_cast<long long>(batch_trials) * n ||
        static_cast<long long>(sz_batch.size()) < static_cast<long long>(batch_trials) * m) {
        if (error) *error = "GPU batch buffers are smaller than expected";
        return false;
    }

    long long logical_failures = 0;
    long long decoder_failures = 0;
    long long total_trials = 0;
    double total_defects = 0.0;
    double total_defects_sq = 0.0;
    double total_weight = 0.0;
    double total_weight_sq = 0.0;

#ifdef _OPENMP
#pragma omp parallel
    {
        long long local_logical_fail = 0;
        long long local_decoder_fail = 0;
        long long local_trials = 0;
        double local_defects = 0.0;
        double local_defects_sq = 0.0;
        double local_weight = 0.0;
        double local_weight_sq = 0.0;

        std::unique_ptr<IDecoderPlugin> plugin_base;
        ISurfaceDecoderPlugin* surf_plugin = nullptr;
        std::string plugin_init_error;
        try {
            plugin_base = reg.create(decoder_name);
            surf_plugin = dynamic_cast<ISurfaceDecoderPlugin*>(plugin_base.get());
            if (surf_plugin == nullptr) {
                plugin_init_error = "selected plugin is not a surface decoder: " + decoder_name;
            } else {
                surf_plugin->configure(dec_cfg);
            }
        } catch (const std::exception& ex) {
            plugin_init_error = ex.what();
        } catch (...) {
            plugin_init_error = "unknown exception creating/configuring decoder plugin";
        }

        std::vector<int> sz_vec(static_cast<size_t>(m), 0);

#pragma omp for schedule(static)
        for (int i = 0; i < batch_trials; ++i) {
            const long long t = start_trial + i;
            const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, t, 0);
            const unsigned char* ex_ptr = ex_batch.data() + static_cast<size_t>(i) * static_cast<size_t>(n);
            const unsigned char* sz_ptr = sz_batch.data() + static_cast<size_t>(i) * static_cast<size_t>(m);

            SingleTrialResult r;
            int defect_count = 0;
            for (int row = 0; row < m; ++row) {
                const int bit = static_cast<int>(sz_ptr[row] & 1u);
                sz_vec[static_cast<size_t>(row)] = bit;
                defect_count += bit;
            }
            r.defect_count = defect_count;

            if (surf_plugin == nullptr) {
                r.decoder_failed = true;
                r.logical_failure = true;
                r.correction_weight = 0;
                r.failure_dump = buildFailureDump(
                    decoder_name,
                    d,
                    p,
                    t,
                    seed,
                    {},
                    sz_vec,
                    nullptr,
                    nullptr,
                    plugin_init_error.empty() ? "decoder plugin unavailable" : plugin_init_error);
            } else {
                try {
                    SurfaceSyndrome decode_syn;
                    decode_syn.sz = sz_vec;
                    const SurfaceCorrection corr = surf_plugin->decode(decode_syn, code);

                    const std::vector<int> syn_after = syndromeFromCorrection(hz_rows, code.n(), corr);
                    bool invariant_ok = (syn_after.size() == sz_vec.size());
                    if (invariant_ok) {
                        for (size_t k = 0; k < syn_after.size(); ++k) {
                            if ((syn_after[k] & 1) != (sz_vec[k] & 1)) {
                                invariant_ok = false;
                                break;
                            }
                        }
                    }

                    int weight = corr.weight;
                    if (weight == 0 && !corr.qubit_flips.empty()) {
                        weight = SurfacePipeline::correctionWeight(corr, code.n());
                    }
                    r.correction_weight = weight;

                    if (!invariant_ok) {
                        r.decoder_failed = true;
                        r.logical_failure = true;
                        r.failure_dump = buildFailureDump(
                            decoder_name,
                            d,
                            p,
                            t,
                            seed,
                            {},
                            sz_vec,
                            &corr,
                            &syn_after,
                            "post-decode invariant mismatch: H*correction != syndrome");
                    } else {
                        int logical_x_parity = 0;
                        int logical_z_parity = 0;
                        const auto& lx = code.logicalXSupport();
                        const auto& lz = code.logicalZSupport();
                        for (int q = 0; q < n; ++q) {
                            if (ex_ptr[q] & 1u) {
                                logical_x_parity ^= (lx[q] & 1);
                                logical_z_parity ^= (lz[q] & 1);
                            }
                        }
                        for (int q : corr.qubit_flips) {
                            if (q < 0 || q >= n) continue;
                            logical_x_parity ^= (lx[q] & 1);
                            logical_z_parity ^= (lz[q] & 1);
                        }
                        r.logical_failure = ((logical_x_parity & 1) != 0) || ((logical_z_parity & 1) != 0);
                    }
                } catch (const std::exception& ex) {
                    r.decoder_failed = true;
                    r.logical_failure = true;
                    r.correction_weight = 0;
                    r.failure_dump = buildFailureDump(
                        decoder_name,
                        d,
                        p,
                        t,
                        seed,
                        {},
                        sz_vec,
                        nullptr,
                        nullptr,
                        ex.what());
                } catch (...) {
                    r.decoder_failed = true;
                    r.logical_failure = true;
                    r.correction_weight = 0;
                    r.failure_dump = buildFailureDump(
                        decoder_name,
                        d,
                        p,
                        t,
                        seed,
                        {},
                        sz_vec,
                        nullptr,
                        nullptr,
                        "unknown exception");
                }
            }

            if (r.logical_failure) local_logical_fail += 1;
            if (r.decoder_failed) {
                local_decoder_fail += 1;
                if (!r.failure_dump.empty()) {
                    bool expected = false;
                    if (first_failure_dumped.compare_exchange_strong(expected, true)) {
                        std::ofstream dump("surface_decoder_failure_dump.txt", std::ios::out | std::ios::trunc);
                        if (dump.is_open()) {
                            dump << r.failure_dump;
                        }
                    }
                }
            }

            local_defects += static_cast<double>(r.defect_count);
            local_defects_sq += static_cast<double>(r.defect_count) * static_cast<double>(r.defect_count);
            local_weight += static_cast<double>(r.correction_weight);
            local_weight_sq += static_cast<double>(r.correction_weight) * static_cast<double>(r.correction_weight);
            local_trials += 1;
        }

#pragma omp atomic
        logical_failures += local_logical_fail;
#pragma omp atomic
        decoder_failures += local_decoder_fail;
#pragma omp atomic
        total_trials += local_trials;
#pragma omp atomic
        total_defects += local_defects;
#pragma omp atomic
        total_defects_sq += local_defects_sq;
#pragma omp atomic
        total_weight += local_weight;
#pragma omp atomic
        total_weight_sq += local_weight_sq;
    }
#else
    std::unique_ptr<IDecoderPlugin> plugin_base;
    ISurfaceDecoderPlugin* surf_plugin = nullptr;
    std::string plugin_init_error;
    try {
        plugin_base = reg.create(decoder_name);
        surf_plugin = dynamic_cast<ISurfaceDecoderPlugin*>(plugin_base.get());
        if (surf_plugin == nullptr) {
            plugin_init_error = "selected plugin is not a surface decoder: " + decoder_name;
        } else {
            surf_plugin->configure(dec_cfg);
        }
    } catch (const std::exception& ex) {
        plugin_init_error = ex.what();
    } catch (...) {
        plugin_init_error = "unknown exception creating/configuring decoder plugin";
    }

    std::vector<int> sz_vec(static_cast<size_t>(m), 0);

    for (int i = 0; i < batch_trials; ++i) {
        const long long t = start_trial + i;
        const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, t, 0);
        const unsigned char* ex_ptr = ex_batch.data() + static_cast<size_t>(i) * static_cast<size_t>(n);
        const unsigned char* sz_ptr = sz_batch.data() + static_cast<size_t>(i) * static_cast<size_t>(m);

        SingleTrialResult r;
        int defect_count = 0;
        for (int row = 0; row < m; ++row) {
            const int bit = static_cast<int>(sz_ptr[row] & 1u);
            sz_vec[static_cast<size_t>(row)] = bit;
            defect_count += bit;
        }
        r.defect_count = defect_count;

        if (surf_plugin == nullptr) {
            r.decoder_failed = true;
            r.logical_failure = true;
            r.correction_weight = 0;
            r.failure_dump = buildFailureDump(
                decoder_name,
                d,
                p,
                t,
                seed,
                {},
                sz_vec,
                nullptr,
                nullptr,
                plugin_init_error.empty() ? "decoder plugin unavailable" : plugin_init_error);
        } else {
            try {
                SurfaceSyndrome decode_syn;
                decode_syn.sz = sz_vec;
                const SurfaceCorrection corr = surf_plugin->decode(decode_syn, code);

                const std::vector<int> syn_after = syndromeFromCorrection(hz_rows, code.n(), corr);
                bool invariant_ok = (syn_after.size() == sz_vec.size());
                if (invariant_ok) {
                    for (size_t k = 0; k < syn_after.size(); ++k) {
                        if ((syn_after[k] & 1) != (sz_vec[k] & 1)) {
                            invariant_ok = false;
                            break;
                        }
                    }
                }

                int weight = corr.weight;
                if (weight == 0 && !corr.qubit_flips.empty()) {
                    weight = SurfacePipeline::correctionWeight(corr, code.n());
                }
                r.correction_weight = weight;

                if (!invariant_ok) {
                    r.decoder_failed = true;
                    r.logical_failure = true;
                    r.failure_dump = buildFailureDump(
                        decoder_name,
                        d,
                        p,
                        t,
                        seed,
                        {},
                        sz_vec,
                        &corr,
                        &syn_after,
                        "post-decode invariant mismatch: H*correction != syndrome");
                } else {
                    int logical_x_parity = 0;
                    int logical_z_parity = 0;
                    const auto& lx = code.logicalXSupport();
                    const auto& lz = code.logicalZSupport();
                    for (int q = 0; q < n; ++q) {
                        if (ex_ptr[q] & 1u) {
                            logical_x_parity ^= (lx[q] & 1);
                            logical_z_parity ^= (lz[q] & 1);
                        }
                    }
                    for (int q : corr.qubit_flips) {
                        if (q < 0 || q >= n) continue;
                        logical_x_parity ^= (lx[q] & 1);
                        logical_z_parity ^= (lz[q] & 1);
                    }
                    r.logical_failure = ((logical_x_parity & 1) != 0) || ((logical_z_parity & 1) != 0);
                }
            } catch (const std::exception& ex) {
                r.decoder_failed = true;
                r.logical_failure = true;
                r.correction_weight = 0;
                r.failure_dump = buildFailureDump(
                    decoder_name,
                    d,
                    p,
                    t,
                    seed,
                    {},
                    sz_vec,
                    nullptr,
                    nullptr,
                    ex.what());
            } catch (...) {
                r.decoder_failed = true;
                r.logical_failure = true;
                r.correction_weight = 0;
                r.failure_dump = buildFailureDump(
                    decoder_name,
                    d,
                    p,
                    t,
                    seed,
                    {},
                    sz_vec,
                    nullptr,
                    nullptr,
                    "unknown exception");
            }
        }

        if (r.logical_failure) logical_failures += 1;
        if (r.decoder_failed) {
            decoder_failures += 1;
            if (!r.failure_dump.empty()) {
                bool expected = false;
                if (first_failure_dumped.compare_exchange_strong(expected, true)) {
                    std::ofstream dump("surface_decoder_failure_dump.txt", std::ios::out | std::ios::trunc);
                    if (dump.is_open()) {
                        dump << r.failure_dump;
                    }
                }
            }
        }

        total_defects += static_cast<double>(r.defect_count);
        total_defects_sq += static_cast<double>(r.defect_count) * static_cast<double>(r.defect_count);
        total_weight += static_cast<double>(r.correction_weight);
        total_weight_sq += static_cast<double>(r.correction_weight) * static_cast<double>(r.correction_weight);
        total_trials += 1;
    }
#endif

    out->trials = total_trials;
    out->fail_count = logical_failures;
    out->decoder_fail_count = decoder_failures;
    out->defect_sum = total_defects;
    out->defect_sumsq = total_defects_sq;
    out->weight_sum = total_weight;
    out->weight_sumsq = total_weight_sq;
    return true;
}

PointAccum runBatchTrials(const SurfaceCode& code,
                          const SparseRows& hx_rows,
                          const SparseRows& hz_rows,
                          SurfacePipeline& pipeline,
                          const PluginRegistry& reg,
                          const std::string& decoder_name,
                          const DecoderConfig& dec_cfg,
                          NoiseMode mode,
                          const GKPNoiseConfig& gkp_cfg,
                          double cv_sigma,
                          double p,
                          uint64_t seed_base,
                          int d,
                          int p_key,
                          long long start_trial,
                          int batch_trials,
                          gpu::SurfaceGpuSampler* gpu_sampler,
                          std::atomic<bool>& first_failure_dumped) {
    if (gpu_sampler != nullptr && mode == NoiseMode::Pauli) {
        PointAccum acc;
        std::string gpu_error;
        if (runBatchTrialsGpu(code, hz_rows, reg, decoder_name, dec_cfg, p, seed_base, d, p_key,
                              start_trial, batch_trials, *gpu_sampler, first_failure_dumped, &acc, &gpu_error)) {
            return acc;
        }
        std::cerr << "WARNING: GPU batch failed, falling back to CPU: " << gpu_error << "\n";
    }
    return runBatchTrialsCpu(code, hx_rows, hz_rows, pipeline, reg, decoder_name, dec_cfg, mode,
                             gkp_cfg, cv_sigma, p, seed_base, d, p_key, start_trial, batch_trials,
                             first_failure_dumped);
}

PointAccum runBatchTrialsCpu(const SurfaceCode& code,
                          const SparseRows& hx_rows,
                          const SparseRows& hz_rows,
                          SurfacePipeline& pipeline,
                          const PluginRegistry& reg,
                          const std::string& decoder_name,
                          const DecoderConfig& dec_cfg,
                          NoiseMode mode,
                          const GKPNoiseConfig& gkp_cfg,
                          double cv_sigma,
                          double p,
                          uint64_t seed_base,
                          int d,
                          int p_key,
                          long long start_trial,
                          int batch_trials,
                          std::atomic<bool>& first_failure_dumped) {
    PointAccum acc;
    long long logical_failures = 0;
    long long decoder_failures = 0;
    long long total_trials = 0;
    double total_defects = 0.0;
    double total_defects_sq = 0.0;
    double total_weight = 0.0;
    double total_weight_sq = 0.0;
    const bool hybrid_mode = (mode == NoiseMode::Hybrid);
    const bool gkp_mode = (mode == NoiseMode::GKP);

#ifdef _OPENMP
#pragma omp parallel
    {
        long long local_logical_fail = 0;
        long long local_decoder_fail = 0;
        long long local_trials = 0;
        double local_defects = 0.0;
        double local_defects_sq = 0.0;
        double local_weight = 0.0;
        double local_weight_sq = 0.0;

        std::unique_ptr<IDecoderPlugin> plugin_base;
        ISurfaceDecoderPlugin* surf_plugin = nullptr;
        std::string plugin_init_error;
        try {
            plugin_base = reg.create(decoder_name);
            surf_plugin = dynamic_cast<ISurfaceDecoderPlugin*>(plugin_base.get());
            if (surf_plugin == nullptr) {
                plugin_init_error = "selected plugin is not a surface decoder: " + decoder_name;
            } else {
                surf_plugin->configure(dec_cfg);
            }
        } catch (const std::exception& ex) {
            plugin_init_error = ex.what();
        } catch (...) {
            plugin_init_error = "unknown exception creating/configuring decoder plugin";
        }

#pragma omp for schedule(static)
        for (int i = 0; i < batch_trials; ++i) {
            const long long t = start_trial + i;
            const int thread_id = omp_get_thread_num();
            SingleTrialResult r;
            if (gkp_mode && surf_plugin != nullptr) {
                r = run_single_trial_gkp(
                    code, hx_rows, hz_rows, *surf_plugin, decoder_name, cv_sigma, gkp_cfg,
                    seed_base, d, p_key, t, thread_id);
            } else if (gkp_mode) {
                const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, t, thread_id);
                r.decoder_failed = true;
                r.logical_failure = true;
                r.correction_weight = 0;
                r.failure_dump = buildFailureDump(
                    decoder_name,
                    d,
                    cv_sigma,
                    t,
                    seed,
                    {},
                    {},
                    nullptr,
                    nullptr,
                    plugin_init_error.empty() ? "decoder plugin unavailable" : plugin_init_error);
            } else if (hybrid_mode && surf_plugin != nullptr) {
                r = run_single_trial_hybrid(
                    surf_plugin, decoder_name, p, seed_base, d, p_key, t, thread_id, cv_sigma);
            } else if (hybrid_mode) {
                const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, t, thread_id);
                r.decoder_failed = true;
                r.logical_failure = true;
                r.correction_weight = 0;
                r.failure_dump = buildFailureDump(
                    decoder_name,
                    d,
                    p,
                    t,
                    seed,
                    {},
                    {},
                    nullptr,
                    nullptr,
                    plugin_init_error.empty() ? "decoder plugin unavailable" : plugin_init_error);
            } else if (surf_plugin != nullptr) {
                r = run_single_trial_discrete(
                    code, hz_rows, pipeline, *surf_plugin, decoder_name, p, seed_base, d, p_key, t, thread_id);
            } else {
                const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, t, thread_id);
                SzTrialSample sample = sampleSzOnly(code, hz_rows, p, seed);
                for (int v : sample.sz) r.defect_count += (v & 1);
                r.decoder_failed = true;
                r.logical_failure = true;
                r.correction_weight = 0;
                r.failure_dump = buildFailureDump(
                    decoder_name,
                    d,
                    p,
                    t,
                    seed,
                    {},
                    sample.sz,
                    nullptr,
                    nullptr,
                    plugin_init_error.empty() ? "decoder plugin unavailable" : plugin_init_error);
            }

            if (r.logical_failure) local_logical_fail += 1;
            if (r.decoder_failed) {
                local_decoder_fail += 1;
                if (!r.failure_dump.empty()) {
                    bool expected = false;
                    if (first_failure_dumped.compare_exchange_strong(expected, true)) {
                        std::ofstream dump("surface_decoder_failure_dump.txt", std::ios::out | std::ios::trunc);
                        if (dump.is_open()) {
                            dump << r.failure_dump;
                        }
                    }
                }
            }

            local_defects += static_cast<double>(r.defect_count);
            local_defects_sq += static_cast<double>(r.defect_count) * static_cast<double>(r.defect_count);
            local_weight += static_cast<double>(r.correction_weight);
            local_weight_sq += static_cast<double>(r.correction_weight) * static_cast<double>(r.correction_weight);
            local_trials += 1;
        }

#pragma omp atomic
        logical_failures += local_logical_fail;
#pragma omp atomic
        decoder_failures += local_decoder_fail;
#pragma omp atomic
        total_trials += local_trials;
#pragma omp atomic
        total_defects += local_defects;
#pragma omp atomic
        total_defects_sq += local_defects_sq;
#pragma omp atomic
        total_weight += local_weight;
#pragma omp atomic
        total_weight_sq += local_weight_sq;
    }
#else
    std::unique_ptr<IDecoderPlugin> plugin_base;
    ISurfaceDecoderPlugin* surf_plugin = nullptr;
    std::string plugin_init_error;
    try {
        plugin_base = reg.create(decoder_name);
        surf_plugin = dynamic_cast<ISurfaceDecoderPlugin*>(plugin_base.get());
        if (surf_plugin == nullptr) {
            plugin_init_error = "selected plugin is not a surface decoder: " + decoder_name;
        } else {
            surf_plugin->configure(dec_cfg);
        }
    } catch (const std::exception& ex) {
        plugin_init_error = ex.what();
    } catch (...) {
        plugin_init_error = "unknown exception creating/configuring decoder plugin";
    }

    for (int i = 0; i < batch_trials; ++i) {
        const long long t = start_trial + i;
        SingleTrialResult r;
        if (gkp_mode && surf_plugin != nullptr) {
            r = run_single_trial_gkp(
                code, hx_rows, hz_rows, *surf_plugin, decoder_name, cv_sigma, gkp_cfg,
                seed_base, d, p_key, t, 0);
        } else if (gkp_mode) {
            const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, t, 0);
            r.decoder_failed = true;
            r.logical_failure = true;
            r.correction_weight = 0;
            r.failure_dump = buildFailureDump(
                decoder_name,
                d,
                cv_sigma,
                t,
                seed,
                {},
                {},
                nullptr,
                nullptr,
                plugin_init_error.empty() ? "decoder plugin unavailable" : plugin_init_error);
        } else if (hybrid_mode && surf_plugin != nullptr) {
            r = run_single_trial_hybrid(
                surf_plugin, decoder_name, p, seed_base, d, p_key, t, 0, cv_sigma);
        } else if (hybrid_mode) {
            const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, t, 0);
            r.decoder_failed = true;
            r.logical_failure = true;
            r.correction_weight = 0;
            r.failure_dump = buildFailureDump(
                decoder_name,
                d,
                p,
                t,
                seed,
                {},
                {},
                nullptr,
                nullptr,
                plugin_init_error.empty() ? "decoder plugin unavailable" : plugin_init_error);
        } else if (surf_plugin != nullptr) {
            r = run_single_trial_discrete(
                code, hz_rows, pipeline, *surf_plugin, decoder_name, p, seed_base, d, p_key, t, 0);
        } else {
            const uint64_t seed = thresholdTrialSeed(seed_base, d, p_key, t, 0);
            SzTrialSample sample = sampleSzOnly(code, hz_rows, p, seed);
            for (int v : sample.sz) r.defect_count += (v & 1);
            r.decoder_failed = true;
            r.logical_failure = true;
            r.correction_weight = 0;
            r.failure_dump = buildFailureDump(
                decoder_name,
                d,
                p,
                t,
                seed,
                {},
                sample.sz,
                nullptr,
                nullptr,
                plugin_init_error.empty() ? "decoder plugin unavailable" : plugin_init_error);
        }
        if (r.logical_failure) logical_failures += 1;
        if (r.decoder_failed) {
            decoder_failures += 1;
            if (!r.failure_dump.empty()) {
                bool expected = false;
                if (first_failure_dumped.compare_exchange_strong(expected, true)) {
                    std::ofstream dump("surface_decoder_failure_dump.txt", std::ios::out | std::ios::trunc);
                    if (dump.is_open()) {
                        dump << r.failure_dump;
                    }
                }
            }
        }
        total_defects += static_cast<double>(r.defect_count);
        total_defects_sq += static_cast<double>(r.defect_count) * static_cast<double>(r.defect_count);
        total_weight += static_cast<double>(r.correction_weight);
        total_weight_sq += static_cast<double>(r.correction_weight) * static_cast<double>(r.correction_weight);
        total_trials += 1;
    }
#endif

    acc.trials = total_trials;
    acc.fail_count = logical_failures;
    acc.decoder_fail_count = decoder_failures;
    acc.defect_sum = total_defects;
    acc.defect_sumsq = total_defects_sq;
    acc.weight_sum = total_weight;
    acc.weight_sumsq = total_weight_sq;
    return acc;
}

void mergeAccum(PointAccum& total, const PointAccum& batch) {
    total.trials += batch.trials;
    total.fail_count += batch.fail_count;
    total.decoder_fail_count += batch.decoder_fail_count;
    total.defect_sum += batch.defect_sum;
    total.defect_sumsq += batch.defect_sumsq;
    total.weight_sum += batch.weight_sum;
    total.weight_sumsq += batch.weight_sumsq;
}

PointStats finalizePoint(const PointAccum& acc,
                        double target_ci_halfwidth,
                        double target_rel_ci) {
    PointStats s;
    s.trials = acc.trials;
    s.fail_count = acc.fail_count;

    if (acc.trials > 0) {
        const double n = static_cast<double>(acc.trials);
        s.defect_avg = acc.defect_sum / n;
        s.weight_avg = acc.weight_sum / n;
        s.defect_stderr = sampleStderr(acc.trials, acc.defect_sum, acc.defect_sumsq);
        s.weight_stderr = sampleStderr(acc.trials, acc.weight_sum, acc.weight_sumsq);
        s.decoder_fail_rate = static_cast<double>(acc.decoder_fail_count) / n;
    }

    wilson95(acc.fail_count, acc.trials, s.ler, s.ler_lo95, s.ler_hi95, s.ci_halfwidth);
    const bool abs_ok = (target_ci_halfwidth > 0.0) && (s.ci_halfwidth <= target_ci_halfwidth);
    const bool rel_ok = (target_rel_ci > 0.0)
        && (s.ci_halfwidth / std::max(s.ler, 1e-12) <= target_rel_ci);
    s.ci_target_met = abs_ok || rel_ok;
    return s;
}

std::vector<CrossingPoint> detectPairwiseCrossings(
    const std::map<int, std::vector<ThresholdPoint>>& results_by_distance,
    const std::vector<int>& distances) {
    constexpr double kEps = std::numeric_limits<double>::epsilon();
    std::vector<CrossingPoint> crossings;

    for (size_t i = 0; i + 1 < distances.size(); ++i) {
        const int d_small = distances[i];
        const int d_large = distances[i + 1];
        const auto it_small = results_by_distance.find(d_small);
        const auto it_large = results_by_distance.find(d_large);
        if (it_small == results_by_distance.end() || it_large == results_by_distance.end()) continue;

        const auto& v_small = it_small->second;
        const auto& v_large = it_large->second;
        const size_t n = std::min(v_small.size(), v_large.size());
        if (n < 2) continue;

        for (size_t k = 0; k + 1 < n; ++k) {
            const double l_small_k = v_small[k].LER;
            const double l_large_k = v_large[k].LER;
            const double l_small_next = v_small[k + 1].LER;
            const double l_large_next = v_large[k + 1].LER;

            const bool flips_up =
                (l_small_k + kEps < l_large_k) &&
                (l_small_next > l_large_next + kEps);
            const bool flips_down =
                (l_small_k > l_large_k + kEps) &&
                (l_small_next + kEps < l_large_next);
            if (!flips_up && !flips_down) continue;

            const double delta_k = l_small_k - l_large_k;
            const double delta_next = l_small_next - l_large_next;
            const double denom = delta_k - delta_next;
            if (std::abs(denom) <= kEps) continue;

            const double p_k = v_small[k].p;
            const double p_next = v_small[k + 1].p;
            const double t = delta_k / denom;
            const double p_cross = p_k + (p_next - p_k) * t;
            crossings.push_back(CrossingPoint{d_small, d_large, p_cross});
        }
    }

    return crossings;
}

std::string formatPairsUsed(const std::vector<CrossingPoint>& crossings) {
    std::set<std::pair<int, int>> pair_set;
    for (const auto& c : crossings) {
        pair_set.insert({c.d_small, c.d_large});
    }

    std::ostringstream oss;
    bool first = true;
    for (const auto& pr : pair_set) {
        if (!first) oss << ", ";
        first = false;
        oss << "d=" << pr.first << " vs " << pr.second;
    }
    return oss.str();
}

double collapseCost(const std::vector<ThresholdPoint>& points,
                    double p_c,
                    double nu,
                    int bins) {
    constexpr double kEps = std::numeric_limits<double>::epsilon();
    if (points.empty() || nu <= kEps || bins <= 0) {
        return std::numeric_limits<double>::infinity();
    }

    std::vector<std::pair<double, double>> x_ler;
    x_ler.reserve(points.size());
    double x_min = std::numeric_limits<double>::infinity();
    double x_max = -std::numeric_limits<double>::infinity();
    for (const auto& pt : points) {
        if (pt.d <= 0) continue;
        const double x = (pt.p - p_c) * std::pow(static_cast<double>(pt.d), 1.0 / nu);
        x_ler.push_back({x, pt.LER});
        x_min = std::min(x_min, x);
        x_max = std::max(x_max, x);
    }
    if (x_ler.empty() || (x_max - x_min) <= kEps) {
        return std::numeric_limits<double>::infinity();
    }

    struct BinAccum {
        int n = 0;
        double sum = 0.0;
        double sumsq = 0.0;
    };
    std::vector<BinAccum> bin_acc(static_cast<size_t>(bins));

    for (const auto& xl : x_ler) {
        const double x = xl.first;
        const double ler = xl.second;
        const double pos = (x - x_min) / (x_max - x_min);
        int idx = static_cast<int>(pos * static_cast<double>(bins));
        if (idx < 0) idx = 0;
        if (idx >= bins) idx = bins - 1;
        BinAccum& b = bin_acc[static_cast<size_t>(idx)];
        b.n += 1;
        b.sum += ler;
        b.sumsq += ler * ler;
    }

    double total_cost = 0.0;
    int used_bins = 0;
    for (const auto& b : bin_acc) {
        if (b.n < 2) continue;
        const double n = static_cast<double>(b.n);
        const double mean = b.sum / n;
        double var = (b.sumsq - n * mean * mean) / (n - 1.0);
        if (var < 0.0) var = 0.0;
        total_cost += var;
        used_bins += 1;
    }

    if (used_bins == 0) {
        return std::numeric_limits<double>::infinity();
    }
    return total_cost / static_cast<double>(used_bins);
}

ScalingFitResult runScalingFit(const std::map<int, std::vector<ThresholdPoint>>& results_by_distance,
                               double min_p,
                               double max_p) {
    ScalingFitResult best;
    std::vector<ThresholdPoint> points;
    for (const auto& kv : results_by_distance) {
        points.insert(points.end(), kv.second.begin(), kv.second.end());
    }
    if (points.empty() || min_p > max_p) return best;

    constexpr double kPcStep = 0.002;
    constexpr double kNuStart = 0.5;
    constexpr double kNuEnd = 2.0;
    constexpr double kNuStep = 0.05;
    constexpr double kEps = 1e-12;

    for (double p_c = min_p; p_c <= max_p + kEps; p_c += kPcStep) {
        for (double nu = kNuStart; nu <= kNuEnd + kEps; nu += kNuStep) {
            const double cost = collapseCost(points, p_c, nu, 40);
            if (cost < best.cost) {
                best.valid = true;
                best.p_c = p_c;
                best.nu = nu;
                best.cost = cost;
            }
        }
    }

    return best;
}

} // namespace

int SurfaceThresholdRunner::run(const SurfaceThresholdConfig& cfg) {
    PluginRegistry local;
    RegisterAllPlugins(local);
    return run(cfg, local);
}

int SurfaceThresholdRunner::run(const SurfaceThresholdConfig& cfg, const PluginRegistry& reg) {
    std::remove("surface_decoder_failure_dump.txt");
    const bool hybrid_mode = (cfg.mode == NoiseMode::Hybrid);
    const bool gkp_mode = (cfg.mode == NoiseMode::GKP);
    const bool sigma_mode = hybrid_mode || gkp_mode;
    const std::string surface_mode = noiseModeName(cfg.mode);

    std::ofstream out(cfg.out_csv);
    if (!out.is_open()) {
        std::cerr << "error: cannot open output CSV '" << cfg.out_csv << "'\n";
        return 1;
    }
    out << "mode,distance,sigma,pauli_p,trials,ler,ci_low,ci_high,defect_mean,weight_mean,"
        << "decoder_fail_rate,mwpm_weight_scale,mwpm_graph,timestamp\n";

    std::string decoder_name = normalizeDecoderName(cfg.decoder_name);
    if (cfg.decoder_name != decoder_name) {
        std::cout << "WARNING: unknown decoder '" << cfg.decoder_name
                  << "', falling back to mwpm\n";
    }
    if (decoder_name == "neural_mwpm" && !fileExists(cfg.neural_model_path)) {
        std::cerr << "ERROR: neural_mwpm requires --neural_model <path>\n";
        return 1;
    }
    if (gkp_mode && !cfg.gkp_loss_map.empty() && cfg.distances.size() > 1) {
        std::cerr << "error: gkp_loss_map requires a single distance (use --d=<single>)\n";
        return 1;
    }
    std::string mwpm_graph = cfg.mwpm_graph;
    if (mwpm_graph != "full" && mwpm_graph != "simple") {
        std::cout << "WARNING: unknown mwpm_graph '" << cfg.mwpm_graph
                  << "', falling back to full\n";
        mwpm_graph = "full";
    }

    const std::vector<double> sweep_values = sigma_mode
        ? makeSweepGrid(cfg.sigma_start, cfg.sigma_end, cfg.sigma_step)
        : makeSweepGrid(cfg.p_start, cfg.p_end, cfg.p_step);
    if (sweep_values.empty()) {
        std::cerr << "error: empty " << (sigma_mode ? "sigma" : "p")
                  << " grid for threshold run\n";
        return 1;
    }

    int threads = 1;
#ifdef _OPENMP
    if (cfg.threads > 0) {
        omp_set_dynamic(0);
        omp_set_num_threads(cfg.threads);
    }
    threads = omp_get_max_threads();
#endif
    std::cout << "threshold: threads=" << threads << "\n";
    std::cout << "mode: " << surface_mode;
    if (sigma_mode) {
        std::cout << " sigma_range=[" << sweep_values.front() << "," << sweep_values.back()
                  << "] step=" << cfg.sigma_step;
    }
    std::cout << "\n";
    if (!sigma_mode && cfg.weight_mode == "llr") {
        const auto p_or_sweep = [](double v) -> std::string {
            if (v >= 0.0) {
                std::ostringstream oss;
                oss << v;
                return oss.str();
            }
            return "<sweep_p>";
        };
        std::cout << "weights: mode=llr"
                  << " p_data=" << p_or_sweep(cfg.llr_p_data)
                  << " p_meas=" << p_or_sweep(cfg.llr_p_meas)
                  << " p_idle=" << p_or_sweep(cfg.llr_p_idle)
                  << " clamp=[" << cfg.llr_clamp_min << "," << cfg.llr_clamp_max << "]"
                  << " mwpm_weight_scale=" << cfg.mwpm_weight_scale
                  << " mwpm_graph=" << mwpm_graph
                  << "\n";
    } else if (sigma_mode) {
        std::cout << "weights: sigma mode (pauli p disabled)"
                  << " mwpm_weight_scale=" << cfg.mwpm_weight_scale
                  << " mwpm_graph=" << mwpm_graph
                  << "\n";
    } else {
        std::cout << "weights: mode=" << cfg.weight_mode
                  << " mwpm_weight_scale=" << cfg.mwpm_weight_scale
                  << " mwpm_graph=" << mwpm_graph
                  << "\n";
    }

    const bool fixed_mode = !cfg.adaptive_enabled;
    const int resolved_max_trials = fixed_mode
        ? std::max(1, cfg.trials)
        : (cfg.max_trials > 0 ? cfg.max_trials : (cfg.trials_explicit ? std::max(1, cfg.trials) : 20000));
    const int resolved_min_trials = fixed_mode
        ? std::max(1, cfg.trials)
        : std::max(1, std::min(cfg.min_trials, resolved_max_trials));
    constexpr int kFixedBatchTrials = 25;
    const int resolved_batch_trials = fixed_mode
        ? std::max(1, std::min(cfg.trials, kFixedBatchTrials))
        : std::max(1, cfg.batch_trials);

    constexpr double kEps = 1e-12;
    std::atomic<bool> first_failure_dumped{false};
    std::vector<SweepPoint> scaling_points;
    scaling_points.reserve(static_cast<size_t>(cfg.distances.size() * sweep_values.size()));
    std::vector<ThresholdResult> results;
    results.reserve(static_cast<size_t>(cfg.distances.size() * sweep_values.size()));
    for (int d : cfg.distances) {
        SurfaceCode code(d);
        SurfacePipeline pipeline(code);
        const SparseRows hx_rows = buildSparseRows(code.Hx());
        const SparseRows hz_rows = buildSparseRows(code.Hz());
        std::unique_ptr<gpu::SurfaceGpuSampler> gpu_sampler;

        if (cfg.use_gpu) {
            if (cfg.mode != NoiseMode::Pauli) {
                std::cout << "WARNING: GPU backend currently supports pauli mode only; using CPU.\n";
            } else if (!gpu::is_available()) {
                std::cout << "WARNING: GPU backend requested but no CUDA device detected; using CPU.\n";
            } else {
                std::string gpu_error;
                gpu_sampler = std::make_unique<gpu::SurfaceGpuSampler>(code.n(), hz_rows, &gpu_error);
                if (!gpu_sampler->ok()) {
                    std::cout << "WARNING: GPU backend init failed; using CPU. " << gpu_error << "\n";
                    gpu_sampler.reset();
                } else {
                    std::cout << "gpu: " << gpu::backend_name() << " device=" << gpu::device_name()
                              << " pauli sampling enabled\n";
                }
            }
        }

        if (gkp_mode && !cfg.gkp_loss_map.empty()
            && static_cast<int>(cfg.gkp_loss_map.size()) != code.n()) {
            std::cerr << "error: gkp_loss_map size must match code.n() ("
                      << cfg.gkp_loss_map.size() << " vs " << code.n() << ")\n";
            return 1;
        }

        DecoderConfig dec_cfg;
        dec_cfg.decoder_name = decoder_name;
        dec_cfg.distance = d;
        dec_cfg.seed = cfg.seed + static_cast<uint64_t>(d) * 1000000ULL;
        dec_cfg.alpha = cfg.bp_alpha;
        dec_cfg.string_params["decoder_name"] = decoder_name;
        dec_cfg.string_params["bp_mode"] =
            (cfg.bp_mode == BeliefPropagation::Mode::NORMALIZED_MIN_SUM) ? "nms" : "sum-product";
        dec_cfg.string_params["weight_mode"] = cfg.weight_mode;
        dec_cfg.string_params["mwpm_graph"] = mwpm_graph;
        dec_cfg.string_params["neural_model"] = cfg.neural_model_path;
        dec_cfg.string_params["neural_weights"] =
            cfg.neural_weights_path.empty() ? cfg.neural_model_path : cfg.neural_weights_path;
        dec_cfg.int_params["distance"] = d;
        dec_cfg.int_params["seed"] = static_cast<int>(dec_cfg.seed & 0x7fffffffULL);
        dec_cfg.int_params["uf_weighted"] =
            (cfg.uf_weighted || cfg.weight_mode == "neural" || cfg.weight_mode == "llr") ? 1 : 0;
        dec_cfg.ptr_params["surface_code"] = &code;

        {
            std::unique_ptr<IDecoderPlugin> check_plugin = reg.create(decoder_name);
            auto* check_surface = dynamic_cast<ISurfaceDecoderPlugin*>(check_plugin.get());
            if (check_surface == nullptr) {
                std::cerr << "error: selected plugin is not a surface decoder: "
                          << decoder_name << "\n";
                return 1;
            }
        }

        double prev_raw_ler = -1.0;
        double smoothed_ler = 0.0;
        for (size_t sweep_index = 0; sweep_index < sweep_values.size(); ++sweep_index) {
            const double sweep = sweep_values[sweep_index];
            const double sigma = sigma_mode ? sweep : 0.0;
            const double p = sigma_mode ? 0.0 : sweep;
            const int p_key = static_cast<int>(std::llround(sweep * 1e6));
            dec_cfg.p = p;
            const double llr_p_data = sigma_mode ? 0.0 : ((cfg.llr_p_data >= 0.0) ? cfg.llr_p_data : p);
            const double llr_p_meas = sigma_mode ? 0.0 : ((cfg.llr_p_meas >= 0.0) ? cfg.llr_p_meas : p);
            const double llr_p_idle = sigma_mode ? 0.0 : ((cfg.llr_p_idle >= 0.0) ? cfg.llr_p_idle : p);
            dec_cfg.double_params["llr_p_data"] = llr_p_data;
            dec_cfg.double_params["llr_p_meas"] = llr_p_meas;
            dec_cfg.double_params["llr_p_idle"] = llr_p_idle;
            dec_cfg.double_params["llr_clamp_min"] = cfg.llr_clamp_min;
            dec_cfg.double_params["llr_clamp_max"] = cfg.llr_clamp_max;
            dec_cfg.double_params["mwpm_weight_scale"] = cfg.mwpm_weight_scale;

            if (sigma_mode) {
                std::cout << "running d=" << d
                          << " sigma=" << std::fixed << std::setprecision(3) << sigma
                          << " target_trials=" << resolved_max_trials
                          << " batch=" << resolved_batch_trials
                          << "\n";
            } else {
                std::cout << "running d=" << d
                          << " p=" << std::fixed << std::setprecision(3) << p
                          << " target_trials=" << resolved_max_trials
                          << " batch=" << resolved_batch_trials
                          << "\n";
            }

            PointAccum accum;
            bool ci_met = false;
            const long long progress_step = fixed_mode
                ? std::max<long long>(1, resolved_batch_trials)
                : std::max<long long>(1, static_cast<long long>(resolved_batch_trials) * 5LL);
            long long next_progress = progress_step;
            while (accum.trials < resolved_max_trials) {
                const long long remaining = static_cast<long long>(resolved_max_trials) - accum.trials;
                const long long need_min = fixed_mode
                    ? 0LL
                    : std::max<long long>(0, static_cast<long long>(resolved_min_trials) - accum.trials);
                int batch = static_cast<int>(std::min<long long>(remaining, std::max<long long>(resolved_batch_trials, need_min)));
                if (batch <= 0) break;

                const PointAccum batch_acc = runBatchTrials(
                    code,
                    hx_rows,
                    hz_rows,
                    pipeline,
                    reg,
                    decoder_name,
                    dec_cfg,
                    cfg.mode,
                    GKPNoiseConfig{cfg.gkp_gate_error, cfg.gkp_meas_error,
                                   cfg.gkp_idle_error, cfg.gkp_loss_prob, cfg.gkp_loss_map},
                    sigma,
                    p,
                    dec_cfg.seed,
                    d,
                    p_key + static_cast<int>(sweep_index * 997),
                    accum.trials,
                    batch,
                    gpu_sampler.get(),
                    first_failure_dumped);
                mergeAccum(accum, batch_acc);

                if (accum.trials >= next_progress && accum.trials < resolved_max_trials) {
                    std::cout << "progress d=" << d;
                    if (sigma_mode) {
                        std::cout << " sigma=" << std::fixed << std::setprecision(3) << sigma;
                    } else {
                        std::cout << " p=" << std::fixed << std::setprecision(3) << p;
                    }
                    std::cout << " trials=" << accum.trials;
                    if (fixed_mode) {
                        std::cout << "/" << resolved_max_trials;
                    }
                    std::cout << "\n";
                    next_progress += progress_step;
                }

                if (fixed_mode) continue;
                if (accum.trials < resolved_min_trials) continue;

                PointStats current = finalizePoint(accum, cfg.target_ci_halfwidth, cfg.target_rel_ci);
                if (current.ci_target_met) {
                    ci_met = true;
                    break;
                }
            }

            PointStats stats = finalizePoint(accum, cfg.target_ci_halfwidth, cfg.target_rel_ci);
            if (!fixed_mode && !ci_met && accum.trials >= resolved_max_trials) {
                std::cout << "NOTE: reached max_trials at d=" << d << ", ";
                if (sigma_mode) {
                    std::cout << "sigma=" << sigma;
                } else {
                    std::cout << "p=" << p;
                }
                std::cout << "\n";
            }
            if (stats.decoder_fail_rate > 0.0) {
                std::cout << "WARNING: decoder_fail_rate>0 at d=" << d;
                if (sigma_mode) {
                    std::cout << " sigma=" << sigma;
                } else {
                    std::cout << " p=" << p;
                }
                std::cout
                          << " fail_rate=" << stats.decoder_fail_rate
                          << " (first failure dump: surface_decoder_failure_dump.txt)\n";
            }

            if (!sigma_mode && std::abs(p) <= kEps && stats.ler > kEps) {
                std::cout << "WARNING: p=0 produced non-zero LER at d=" << d
                          << " (LER=" << stats.ler
                          << ", trials=" << stats.trials << ")\n";
            }
            if (prev_raw_ler >= 0.0 && stats.ler + kEps < prev_raw_ler) {
                std::cout << "WARNING: non-monotonic LER at d=" << d;
                if (sigma_mode) {
                    std::cout << " sigma=" << sigma;
                } else {
                    std::cout << " p=" << p;
                }
                std::cout
                          << " prev=" << prev_raw_ler
                          << " now=" << stats.ler
                          << " likely finite-trial variance; CI_halfwidth=" << stats.ci_halfwidth
                          << "\n";
            }
            prev_raw_ler = stats.ler;

            if (sweep_index == 0) smoothed_ler = stats.ler;
            else smoothed_ler = std::max(smoothed_ler, stats.ler);
            const double ler_report = cfg.monotonic_smooth ? smoothed_ler : stats.ler;
            SweepPoint sp;
            sp.d = d;
            sp.p = sweep;
            sp.trials = static_cast<int>(stats.trials);
            sp.ler = stats.ler;
            sp.ci_low = stats.ler_lo95;
            sp.ci_high = stats.ler_hi95;
            scaling_points.push_back(sp);
            results.push_back(ThresholdResult{d, sigma, ler_report});

            out << surface_mode << ","
                << d << ","
                << sigma << ","
                << p << ","
                << stats.trials << ","
                << ler_report << ","
                << stats.ler_lo95 << ","
                << stats.ler_hi95 << ","
                << stats.defect_avg << ","
                << stats.weight_avg << ","
                << stats.decoder_fail_rate << ","
                << cfg.mwpm_weight_scale << ","
                << mwpm_graph << ","
                << iso8601NowUtc()
                << "\n";

            std::cout << std::fixed << "d=" << d;
            if (sigma_mode) {
                std::cout << " sigma=" << std::setprecision(3) << sigma;
            } else {
                std::cout << " p=" << std::setprecision(3) << p;
            }
            std::cout << " trials=" << stats.trials
                      << " LER=" << std::setprecision(6) << ler_report
                      << " [" << stats.ler_lo95 << "," << stats.ler_hi95 << "]"
                      << " defect=" << std::setprecision(4) << stats.defect_avg
                      << "+/-" << stats.defect_stderr
                      << " weight=" << stats.weight_avg
                      << "+/-" << stats.weight_stderr
                      << " fail_rate=" << std::setprecision(6) << stats.decoder_fail_rate
                      << "\n";
        }
    }

    if (sigma_mode) {
        const auto crossing_est = estimateSigmaCrossings(results, cfg.distances);
        for (const auto& c : crossing_est) {
            std::cout << "Estimated crossing between d=" << c.first.first
                      << " and d=" << c.first.second
                      << " at sigma ~= " << std::fixed << std::setprecision(2) << c.second
                      << "\n";
        }

        const std::string plot_title = gkp_mode ? "GKP Sigma Threshold Curve" : "Hybrid CV-Discrete Threshold Curve";
        if (writeSigmaPlotScript(cfg.out_csv, "plot_threshold.py", surface_mode, plot_title)) {
            std::cout << "Plot script written to plot_threshold.py\n";
            const int py_status = std::system("python3 plot_threshold.py > /dev/null 2>&1");
            if (py_status == 0) {
                std::cout << "threshold_plot.png generated\n";
            } else {
                std::cout << "WARNING: automatic plot generation failed; run python3 plot_threshold.py manually\n";
            }
        } else {
            std::cout << "WARNING: failed to write plot script to plot_threshold.py\n";
        }

        std::cout << "--------------------------------\n";
        std::cout << "Sigma Threshold Summary\n";
        std::cout << "--------------------------------\n";
        std::cout << "Distances tested: " << distancesCsv(cfg.distances) << "\n";
        std::cout << "Sigma range: " << std::fixed << std::setprecision(2)
                  << sweep_values.front() << " - " << sweep_values.back() << "\n";
        std::cout << "Trials per point: " << cfg.trials << "\n";
        for (size_t i = 0; i + 1 < cfg.distances.size(); ++i) {
            const int d1 = cfg.distances[i];
            const int d2 = cfg.distances[i + 1];
            bool found = false;
            double sigma_cross = 0.0;
            for (const auto& c : crossing_est) {
                if (c.first.first == d1 && c.first.second == d2) {
                    found = true;
                    sigma_cross = c.second;
                    break;
                }
            }
            std::cout << "Estimated crossing d=" << d1 << "/" << d2 << ": ";
            if (found) {
                std::cout << std::fixed << std::setprecision(2) << sigma_cross;
            } else {
                std::cout << "n/a";
            }
            std::cout << "\n";
        }
        std::cout << "--------------------------------\n";
    } else {
        const bool do_estimate_threshold = cfg.auto_threshold || cfg.estimate_threshold;
        std::vector<CrossingEstimate> crossings;
        CrossingAggregate crossing_agg;
        CollapseFitResult collapse_fit{};
        bool have_collapse = false;

        if (do_estimate_threshold) {
            ScalingOutputs cross_out = ScalingAnalysis::run_all(
                scaling_points,
                true,
                false,
                cfg.monotonic_smooth,
                cfg.ler_smooth_eps,
                cfg.scaling_bootstrap,
                cfg.scaling_seed);
            crossings = std::move(cross_out.crossings);
            crossing_agg = aggregateCrossings(crossings);

            std::cout << "--------------------------------------\n";
            std::cout << "Threshold Crossing Estimate\n";
            if (crossings.empty()) {
                std::cout << "WARNING: no crossings found. Increase p resolution "
                          << "(smaller --p_step) or widen p range.\n";
            } else {
                for (const auto& c : crossings) {
                    std::cout << "pair d=" << c.d1 << " vs " << c.d2
                              << " crossing p*=" << std::fixed << std::setprecision(6) << c.pc
                              << " [" << c.pc_low << "," << c.pc_high << "]"
                              << " q=" << std::setprecision(3) << c.quality
                              << "\n";
                }
                if (crossing_agg.valid) {
                    std::cout << "Pairs used: " << crossingPairsString(crossings) << "\n";
                    std::cout << "Estimated p_c = " << std::setprecision(6) << crossing_agg.pc
                              << " [" << crossing_agg.pc_low << ", " << crossing_agg.pc_high << "]\n";
                    std::cout << "Method: pairwise crossing (d pairs used: "
                              << crossingPairsString(crossings) << ")\n";
                }
            }
            std::cout << "--------------------------------------\n";
        } else if (cfg.scaling_fit) {
            // Used only to seed the collapse optimizer when threshold estimation is not explicitly requested.
            crossings = ScalingAnalysis::estimate_crossings(
                scaling_points, cfg.monotonic_smooth, cfg.ler_smooth_eps, 1);
            crossing_agg = aggregateCrossings(crossings);
        }

        if (cfg.scaling_fit) {
            double pc_min = cfg.pc_min_set ? cfg.pc_min : sweep_values.front();
            double pc_max = cfg.pc_max_set ? cfg.pc_max : sweep_values.back();
            if (pc_max < pc_min) std::swap(pc_min, pc_max);

            double nu_min = cfg.nu_min_set ? cfg.nu_min : 0.5;
            double nu_max = cfg.nu_max_set ? cfg.nu_max : 3.0;
            if (nu_max < nu_min) std::swap(nu_min, nu_max);

            const double pc_init = crossing_agg.valid ? crossing_agg.pc : 0.5 * (pc_min + pc_max);
            const double nu_init = 1.0;

            collapse_fit = ScalingAnalysis::fit_collapse(
                scaling_points,
                cfg.monotonic_smooth,
                cfg.ler_smooth_eps,
                pc_init,
                nu_init,
                pc_min,
                pc_max,
                nu_min,
                nu_max,
                cfg.grid_pc,
                cfg.grid_nu,
                cfg.scaling_bootstrap,
                cfg.scaling_seed);
            have_collapse = std::isfinite(collapse_fit.cost);

            std::cout << "--------------------------------------\n";
            std::cout << "Finite-Size Scaling Fit\n";
            if (crossing_agg.valid) {
                std::cout << "Crossing median p_c = " << std::fixed << std::setprecision(6)
                          << crossing_agg.pc
                          << " [" << crossing_agg.pc_low << ", " << crossing_agg.pc_high << "]\n";
            }
            if (have_collapse) {
                std::cout << "Best p_c = " << std::fixed << std::setprecision(6)
                          << collapse_fit.pc
                          << " [" << collapse_fit.pc_low << ", " << collapse_fit.pc_high << "]\n";
                std::cout << "Best nu = " << std::fixed << std::setprecision(6)
                          << collapse_fit.nu
                          << " [" << collapse_fit.nu_low << ", " << collapse_fit.nu_high << "]\n";
                std::cout << "Collapse cost = " << std::fixed << std::setprecision(8)
                          << collapse_fit.cost << "\n";
            } else {
                std::cout << "WARNING: scaling fit unavailable (insufficient threshold data).\n";
            }
            std::cout << "--------------------------------------\n";
        }

        if (do_estimate_threshold || cfg.scaling_fit) {
            const std::string report_md = makeScalingReportMarkdown(
                cfg, scaling_points, crossings, crossing_agg, have_collapse ? &collapse_fit : nullptr);
            const std::string summary_json = makeScalingSummaryJson(
                cfg.scaling_seed, crossings, crossing_agg, have_collapse ? &collapse_fit : nullptr);
            if (!writeTextFile(cfg.scaling_report, report_md)) {
                std::cout << "WARNING: failed to write scaling report to " << cfg.scaling_report << "\n";
            } else {
                std::cout << "scaling report written to " << cfg.scaling_report << "\n";
            }
            if (!writeTextFile(cfg.scaling_json, summary_json)) {
                std::cout << "WARNING: failed to write scaling summary JSON to " << cfg.scaling_json << "\n";
            } else {
                std::cout << "scaling summary JSON written to " << cfg.scaling_json << "\n";
            }
        }
    }

    out.flush();
    std::cout << "surface threshold CSV written to " << cfg.out_csv << "\n";
    return 0;
}
