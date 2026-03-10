#include "sim/CSSThresholdRunner.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include "decoders/BPDecoderAdapter.h"
#include "graph/TannerGraph.h"
#include "qec/LogicalOperators.h"
#include "qec/PauliChannelAdapter.h"
#include "qec/QuantumCSSSimulator.h"
#include "sim/CSSSimulation.h"

namespace {

struct PointAccum {
    long long trials = 0;
    long long fail_total = 0;
    long long fail_x = 0;
    long long fail_z = 0;
    double iter_x_sum = 0.0;
    double iter_z_sum = 0.0;
};

struct PointStats {
    long long trials = 0;
    long long fail_total = 0;
    double ler_total = 0.0;
    double ler_total_lo95 = 0.0;
    double ler_total_hi95 = 1.0;
    double ci_halfwidth = 0.5;
    double ler_x = 0.0;
    double ler_z = 0.0;
    double avg_iter_x = 0.0;
    double avg_iter_z = 0.0;
    bool ci_target_met = false;
};

const char* modeName(CSSNoiseMode mode) {
    return (mode == CSSNoiseMode::Hybrid) ? "hybrid" : "pauli";
}

QECNoiseModel toNoiseModel(CSSNoiseMode mode) {
    return (mode == CSSNoiseMode::Hybrid)
        ? QECNoiseModel::HYBRID_GKP
        : QECNoiseModel::INDEPENDENT_XZ;
}

bool buildSweepGrid(double start,
                    double end,
                    double step,
                    std::vector<double>* out,
                    std::string* error) {
    if (out == nullptr || error == nullptr) return false;
    out->clear();

    if (step <= 0.0) {
        *error = "step must be > 0";
        return false;
    }
    if (end + 1e-12 < start) {
        *error = "end must be >= start";
        return false;
    }

    constexpr int kMaxPoints = 20000;
    for (double v = start; v <= end + 1e-12; v += step) {
        out->push_back(std::max(0.0, v));
        if (static_cast<int>(out->size()) > kMaxPoints) {
            *error = "sweep has too many points (check step size)";
            out->clear();
            return false;
        }
    }
    if (out->empty()) {
        out->push_back(std::max(0.0, start));
    }
    return true;
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

long long clampFailCount(double fail_rate, int trials) {
    if (trials <= 0 || !std::isfinite(fail_rate)) return 0;
    long long c = static_cast<long long>(std::llround(fail_rate * static_cast<double>(trials)));
    if (c < 0) c = 0;
    if (c > trials) c = trials;
    return c;
}

void mergeBatch(PointAccum& total,
                const CSSDemoPointStats& batch,
                int batch_trials) {
    total.trials += batch_trials;
    total.fail_total += clampFailCount(batch.ler_total, batch_trials);
    total.fail_x += clampFailCount(batch.ler_x, batch_trials);
    total.fail_z += clampFailCount(batch.ler_z, batch_trials);
    total.iter_x_sum += batch.avg_iter_x * static_cast<double>(batch_trials);
    total.iter_z_sum += batch.avg_iter_z * static_cast<double>(batch_trials);
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

PointStats finalizePoint(const PointAccum& acc,
                        double target_ci_halfwidth,
                        double target_rel_ci) {
    PointStats out;
    out.trials = acc.trials;
    out.fail_total = acc.fail_total;

    wilson95(acc.fail_total,
             acc.trials,
             out.ler_total,
             out.ler_total_lo95,
             out.ler_total_hi95,
             out.ci_halfwidth);

    if (acc.trials > 0) {
        const double n = static_cast<double>(acc.trials);
        out.ler_x = static_cast<double>(acc.fail_x) / n;
        out.ler_z = static_cast<double>(acc.fail_z) / n;
        out.avg_iter_x = acc.iter_x_sum / n;
        out.avg_iter_z = acc.iter_z_sum / n;
    }

    const bool abs_ok = (target_ci_halfwidth > 0.0) && (out.ci_halfwidth <= target_ci_halfwidth);
    const bool rel_ok = (target_rel_ci > 0.0)
        && (out.ci_halfwidth / std::max(out.ler_total, 1e-12) <= target_rel_ci);
    out.ci_target_met = abs_ok || rel_ok;
    return out;
}

} // namespace

int CSSThresholdRunner::run(const CSSThresholdConfig& cfg,
                            const BeliefPropagation::Params& bp_params,
                            const BinaryMatrix& hx,
                            const BinaryMatrix& hz,
                            const LogicalOperators& logicals) {
    std::vector<double> sweep_values;
    std::string sweep_error;
    const bool hybrid_mode = (cfg.mode == CSSNoiseMode::Hybrid);
    if (hybrid_mode) {
        if (!buildSweepGrid(cfg.sigma_start, cfg.sigma_end, cfg.sigma_step, &sweep_values, &sweep_error)) {
            std::cerr << "error: invalid CSS hybrid sigma sweep: " << sweep_error << "\n";
            return 1;
        }
    } else {
        if (!buildSweepGrid(cfg.p_start, cfg.p_end, cfg.p_step, &sweep_values, &sweep_error)) {
            std::cerr << "error: invalid CSS pauli p sweep: " << sweep_error << "\n";
            return 1;
        }
    }

    std::ofstream out(cfg.out_csv, std::ios::out | std::ios::trunc);
    if (!out.is_open()) {
        std::cerr << "error: cannot open output CSV '" << cfg.out_csv << "'\n";
        return 1;
    }
    out << "mode,decoder,p,sigma,trials,ler_total,ci_low,ci_high,ci_halfwidth,"
        << "ler_x,ler_z,avg_iter_x,avg_iter_z,ci_target_met,timestamp\n";

    TannerGraph Gx(hx);
    TannerGraph Gz(hz);
    const auto dec_x_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(Gz, bp_params);
    };
    const auto dec_z_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(Gx, bp_params);
    };
    PauliChannelAdapter qec_channel;
    QuantumCSSSimulator sim(hx, hz, dec_x_factory, dec_z_factory, qec_channel);

    const QECNoiseModel noise_model = toNoiseModel(cfg.mode);
    const bool fixed_mode = !cfg.adaptive_enabled;
    const int fixed_trials = std::max(1, cfg.trials);
    const int resolved_max_trials = fixed_mode
        ? fixed_trials
        : (cfg.max_trials > 0 ? cfg.max_trials : (cfg.trials_explicit ? fixed_trials : 20000));
    const int resolved_min_trials = fixed_mode
        ? fixed_trials
        : std::max(1, std::min(cfg.min_trials, resolved_max_trials));
    const int resolved_batch_trials = fixed_mode
        ? std::max(1, std::min(fixed_trials, 200))
        : std::max(1, cfg.batch_trials);

    const int sanity_trials = std::min(100, resolved_min_trials);
    const auto sanity = CSSSimulation::run_point(
        sim, 0.0, sanity_trials, cfg.seed + 9000000ULL, &logicals, noise_model);
    std::cout << "[css_threshold sanity] " << (hybrid_mode ? "sigma" : "p") << "=0.0000"
              << " LER_total=" << sanity.ler_total
              << " LER_X=" << sanity.ler_x
              << " LER_Z=" << sanity.ler_z << "\n";
    if (sanity.ler_total > 1e-12) {
        std::cout << "WARNING: zero-noise sanity failed for CSS threshold runner\n";
    }

    std::cout << "css_threshold: mode=" << modeName(cfg.mode)
              << " decoder=" << cfg.decoder_name
              << " points=" << sweep_values.size()
              << " trial_mode=" << (fixed_mode ? "fixed" : "adaptive")
              << " out=" << cfg.out_csv << "\n";

    for (size_t point_idx = 0; point_idx < sweep_values.size(); ++point_idx) {
        const double sweep_value = sweep_values[point_idx];
        const uint64_t point_seed = cfg.seed + static_cast<uint64_t>(point_idx) * 1000000ULL;

        PointAccum accum;
        while (accum.trials < resolved_max_trials) {
            const int remaining = static_cast<int>(resolved_max_trials - accum.trials);
            const int batch_trials = std::max(1, std::min(resolved_batch_trials, remaining));
            const uint64_t batch_seed = point_seed + static_cast<uint64_t>(accum.trials);
            const auto batch = CSSSimulation::run_point(
                sim,
                sweep_value,
                batch_trials,
                batch_seed,
                &logicals,
                noise_model);
            mergeBatch(accum, batch, batch_trials);

            if (!fixed_mode && accum.trials >= resolved_min_trials) {
                const PointStats mid = finalizePoint(accum, cfg.target_ci_halfwidth, cfg.target_rel_ci);
                if (mid.ci_target_met) break;
            }
        }

        const PointStats stats = finalizePoint(accum, cfg.target_ci_halfwidth, cfg.target_rel_ci);
        const double p_value = hybrid_mode ? 0.0 : sweep_value;
        const double sigma_value = hybrid_mode ? sweep_value : 0.0;
        out << modeName(cfg.mode) << ","
            << cfg.decoder_name << ","
            << p_value << ","
            << sigma_value << ","
            << stats.trials << ","
            << stats.ler_total << ","
            << stats.ler_total_lo95 << ","
            << stats.ler_total_hi95 << ","
            << stats.ci_halfwidth << ","
            << stats.ler_x << ","
            << stats.ler_z << ","
            << stats.avg_iter_x << ","
            << stats.avg_iter_z << ","
            << (stats.ci_target_met ? 1 : 0) << ","
            << iso8601NowUtc() << "\n";
        out.flush();

        std::cout << (hybrid_mode ? "sigma" : "p")
                  << "=" << std::fixed << std::setprecision(4) << sweep_value
                  << " trials=" << stats.trials
                  << " LER_total=" << std::setprecision(6) << stats.ler_total
                  << " CI95=[" << stats.ler_total_lo95 << "," << stats.ler_total_hi95 << "]"
                  << " LER_X=" << stats.ler_x
                  << " LER_Z=" << stats.ler_z
                  << " avg_iter_X=" << std::setprecision(2) << stats.avg_iter_x
                  << " avg_iter_Z=" << stats.avg_iter_z;
        if (!fixed_mode) {
            std::cout << " ci_target_met=" << (stats.ci_target_met ? "yes" : "no");
        }
        std::cout << "\n";
    }

    return 0;
}
