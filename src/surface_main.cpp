#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

#include "decoders/BeliefPropagation.h"
#include "surface/SurfaceCode.h"
#include "surface/SurfaceDecoder.h"
#include "surface/SurfaceSyndrome.h"

namespace {

struct Options {
    int d = 3;
    int trials = 1000;
    double px = 0.05;
    double pz = 0.05;

    bool sweep = false;
    double p_start = 0.01;
    double p_end = 0.10;
    double p_step = 0.01;
};

struct TrialStats {
    double logicalXFailRate = 0.0;
    double logicalZFailRate = 0.0;
    double logicalFailRate = 0.0;
    double avgItersX = 0.0;
    double avgItersZ = 0.0;
};

bool startsWith(const std::string& s, const std::string& prefix) {
    return s.rfind(prefix, 0) == 0;
}

Options parseOptions(int argc, char** argv) {
    Options out;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--sweep") {
            out.sweep = true;
        } else if (startsWith(arg, "--d=")) {
            out.d = std::stoi(arg.substr(4));
        } else if (startsWith(arg, "--trials=")) {
            out.trials = std::stoi(arg.substr(9));
        } else if (startsWith(arg, "--px=")) {
            out.px = std::stod(arg.substr(5));
        } else if (startsWith(arg, "--pz=")) {
            out.pz = std::stod(arg.substr(5));
        } else if (startsWith(arg, "--p_start=")) {
            out.p_start = std::stod(arg.substr(10));
        } else if (startsWith(arg, "--p_end=")) {
            out.p_end = std::stod(arg.substr(8));
        } else if (startsWith(arg, "--p_step=")) {
            out.p_step = std::stod(arg.substr(9));
        } else if (arg == "--help") {
            std::cout << "Usage: lidmas_surface [--d=3] [--trials=1000] [--px=0.05] [--pz=0.05]\n";
            std::cout << "       lidmas_surface --d=3 --sweep --p_start=0.01 --p_end=0.10 --p_step=0.01 --trials=500\n";
            std::exit(0);
        } else {
            throw std::invalid_argument("Unknown argument: " + arg);
        }
    }
    return out;
}

bool commutationOK(const BinaryMatrix& Hx, const BinaryMatrix& Hz) {
    if (Hx.cols() != Hz.cols()) return false;

    const int n = Hx.cols();
    for (int i = 0; i < Hx.rows(); ++i) {
        for (int j = 0; j < Hz.rows(); ++j) {
            int parity = 0;
            for (int k = 0; k < n; ++k) {
                parity ^= ((Hx.get(i, k) & 1) & (Hz.get(j, k) & 1));
            }
            if ((parity & 1) != 0) {
                return false;
            }
        }
    }
    return true;
}

std::string rateString(double v) {
    if (std::abs(v) < 1e-15) return "0";
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(6) << v;
    return oss.str();
}

TrialStats runTrials(const SurfaceCode& code,
                    const SurfaceDecoder& decoder,
                    int trials,
                    double px,
                    double pz,
                    uint64_t seed_base) {
    long long fail_x = 0;
    long long fail_z = 0;
    long long fail_any = 0;
    long long iters_x = 0;
    long long iters_z = 0;

    for (int t = 0; t < trials; ++t) {
        const auto s = SurfaceSyndrome::sample(
            code, px, pz, seed_base + static_cast<uint64_t>(t));
        const auto dec = decoder.decode(code, s, px, pz);

        if (dec.logicalXFail) fail_x++;
        if (dec.logicalZFail) fail_z++;
        if (dec.logicalFail) fail_any++;
        iters_x += dec.itersX;
        iters_z += dec.itersZ;
    }

    TrialStats out;
    const double denom = std::max(1, trials);
    out.logicalXFailRate = static_cast<double>(fail_x) / denom;
    out.logicalZFailRate = static_cast<double>(fail_z) / denom;
    out.logicalFailRate = static_cast<double>(fail_any) / denom;
    out.avgItersX = static_cast<double>(iters_x) / denom;
    out.avgItersZ = static_cast<double>(iters_z) / denom;
    return out;
}

void printResultLine(int d,
                     int trials,
                     double px,
                     double pz,
                     const TrialStats& stats) {
    std::cout << "d=" << d
              << " trials=" << trials
              << " px=" << std::fixed << std::setprecision(3) << px
              << " pz=" << std::fixed << std::setprecision(3) << pz
              << " logicalX_fail_rate=" << rateString(stats.logicalXFailRate)
              << " logicalZ_fail_rate=" << rateString(stats.logicalZFailRate)
              << " logical_fail_rate=" << rateString(stats.logicalFailRate)
              << " avg_iters_x=" << std::fixed << std::setprecision(2) << stats.avgItersX
              << " avg_iters_z=" << std::fixed << std::setprecision(2) << stats.avgItersZ
              << "\n";
}

} // namespace

int main(int argc, char** argv) {
    try {
        const Options opts = parseOptions(argc, argv);

        SurfaceCode code(opts.d);
        BeliefPropagation::Params bp_params;
        SurfaceDecoder decoder(bp_params);

        std::cout << "LiDMaS+ Surface Decoder\n";
        std::cout << "commutation_ok=" << (commutationOK(code.Hx(), code.Hz()) ? 1 : 0) << "\n";

        // Always run a small zero-noise sanity check.
        const int sanity_trials = std::min(200, std::max(1, opts.trials));
        const auto sanity = runTrials(code, decoder, sanity_trials, 0.0, 0.0, 9000000);
        std::cout << "[sanity] ";
        printResultLine(opts.d, sanity_trials, 0.0, 0.0, sanity);

        if (opts.sweep) {
            for (double p = opts.p_start; p <= opts.p_end + 1e-12; p += opts.p_step) {
                const auto stats = runTrials(code, decoder, opts.trials, p, p, 1234567 + static_cast<uint64_t>(p * 1e6));
                printResultLine(opts.d, opts.trials, p, p, stats);
            }
        } else {
            const auto stats = runTrials(code, decoder, opts.trials, opts.px, opts.pz, 1234567);
            printResultLine(opts.d, opts.trials, opts.px, opts.pz, stats);
        }
    } catch (const std::exception& ex) {
        std::cerr << "error: " << ex.what() << "\n";
        return 1;
    }
    return 0;
}
