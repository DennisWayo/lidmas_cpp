// ================================
// FILE: src/main.cpp
// LDPC + BSC + BP sweeps with diagnostics
// ================================

#include <iomanip>
#include <iostream>
#include <fstream>
#include <memory>
#include <random>
#include <sstream>
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <optional>
#include <map>

#include "codes/LDPCGenerator.h"
#include "codes/RepetitionCode.h"
#include "codes/ShorCode.h"
#include "core/PluginRegistry.h"
#include "core/RegisterPlugins.h"
#include "decoders/BPDecoderAdapter.h"
#include "decoders/BeliefPropagation.h"
#include "graph/GraphDiagnostics.h"
#include "qec/PauliChannelAdapter.h"
#include "qec/CSSCode.h"
#include "qec/QuantumCSSSimulator.h"
#include "graph/TannerGraph.h"
#include "sim/CSSSimulation.h"
#include "sim/CSSThresholdRunner.h"
#include "sim/GpuBench.h"
#include "sim/LDPCSimulation.h"
#include "sim/SmokeTests.h"
#include "sim/SurfaceSimulation.h"
#include "sim/SurfaceThresholdRunner.h"
#include "utils/BSCChannel.h"
#include "utils/CSVWriter.h"
#include "utils/SeedUtils.h"
#include "utils/SyndromeUtils.h"
#include "utils/MatrixIO.h"

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {

struct SweepConfig {
    int m = 0;
    int n = 0;
    int col_weight = 3;
    int trials = 200;
    double p_start = 0.02;
    double p_end = 0.15;
    double p_step = 0.01;
    std::string label;
    std::string csv_file;
};

struct RuntimeOptions {
    BeliefPropagation::Mode mode = BeliefPropagation::Mode::SUM_PRODUCT;
    double alpha = 0.8;
    bool log_decode_iterations = false;
    std::string qec_mode;
    bool selftest = false;
};

enum class QECEngine {
    Auto,
    Surface,
    CSS,
    LDPC
};

struct PointStats {
    double ber = 0.0;
    double fer = 0.0;
    double avg_iter = 0.0;
    double parity_sat_rate = 0.0;
    double max_iter_hit_rate = 0.0;
};

std::vector<std::string> toArgs(int argc, char** argv) {
    std::vector<std::string> args;
    args.reserve(std::max(0, argc - 1));
    for (int i = 1; i < argc; ++i) {
        args.emplace_back(argv[i]);
    }
    return args;
}

bool hasFlag(const std::vector<std::string>& args, const std::string& flag) {
    return std::find(args.begin(), args.end(), flag) != args.end();
}

bool fileExists(const std::string& path) {
    if (path.empty()) return false;
    std::ifstream in(path);
    return in.good();
}

bool validateNeuralModelRequirement(const std::string& decoder_name,
                                    const std::string& neural_model_path) {
    if (decoder_name != "neural_mwpm") return true;
    if (fileExists(neural_model_path)) return true;
    std::cerr << "ERROR: neural_mwpm requires --neural_model <path>\n";
    return false;
}

std::string getValuePrefix(const std::vector<std::string>& args, const std::string& prefix) {
    for (const auto& arg : args) {
        if (arg.rfind(prefix, 0) == 0) {
            return arg.substr(prefix.size());
        }
    }
    return "";
}

struct CSSInput {
    BinaryMatrix hx;
    BinaryMatrix hz;
    LogicalOperators logicals;
};

std::string stripQuotes(const std::string& s) {
    if (s.size() < 2) return s;
    if ((s.front() == '"' && s.back() == '"') || (s.front() == '\'' && s.back() == '\'')) {
        return s.substr(1, s.size() - 2);
    }
    return s;
}

std::string resolveSpecPath(const std::string& base_dir, const std::string& path) {
    if (path.empty()) return path;
    std::filesystem::path p(path);
    if (p.is_absolute()) return p.string();
    if (base_dir.empty()) return p.string();
    return (std::filesystem::path(base_dir) / p).string();
}

bool extractJsonStringField(const std::string& content,
                            const std::string& key,
                            std::string* out,
                            std::string* error) {
    if (out == nullptr || error == nullptr) return false;
    const std::string needle = "\"" + key + "\"";
    size_t pos = content.find(needle);
    if (pos == std::string::npos) return false;
    pos = content.find(':', pos + needle.size());
    if (pos == std::string::npos) {
        *error = "malformed JSON (missing ':' for key " + key + ")";
        return false;
    }
    pos++;
    while (pos < content.size() && std::isspace(static_cast<unsigned char>(content[pos]))) pos++;
    if (pos >= content.size() || content[pos] != '"') {
        *error = "expected string value for key " + key;
        return false;
    }
    pos++;
    std::string value;
    while (pos < content.size()) {
        char ch = content[pos++];
        if (ch == '\\') {
            if (pos < content.size()) {
                value.push_back(content[pos++]);
            }
            continue;
        }
        if (ch == '"') break;
        value.push_back(ch);
    }
    *out = value;
    return true;
}

bool parseCssSpecFile(const std::string& path,
                      std::string* hx,
                      std::string* hz,
                      std::string* lx,
                      std::string* lz,
                      std::string* error) {
    if (hx == nullptr || hz == nullptr || lx == nullptr || lz == nullptr || error == nullptr) return false;

    std::ifstream in(path);
    if (!in.is_open()) {
        *error = "cannot open CSS spec file: " + path;
        return false;
    }

    const std::filesystem::path spec_path(path);
    const std::string base_dir = spec_path.has_parent_path() ? spec_path.parent_path().string() : "";
    const std::string ext = spec_path.extension().string();

    if (ext == ".json") {
        std::stringstream buffer;
        buffer << in.rdbuf();
        const std::string content = buffer.str();
        std::string parse_error;
        if (!extractJsonStringField(content, "hx", hx, &parse_error)) {
            if (!parse_error.empty()) { *error = parse_error; return false; }
        }
        if (!extractJsonStringField(content, "hz", hz, &parse_error)) {
            if (!parse_error.empty()) { *error = parse_error; return false; }
        }
        if (!extractJsonStringField(content, "lx", lx, &parse_error)) {
            if (!parse_error.empty()) { *error = parse_error; return false; }
        }
        if (!extractJsonStringField(content, "lz", lz, &parse_error)) {
            if (!parse_error.empty()) { *error = parse_error; return false; }
        }
    } else {
        std::string line;
        while (std::getline(in, line)) {
            std::string stripped = line;
            const size_t hash_pos = stripped.find('#');
            const size_t slash_pos = stripped.find("//");
            size_t cut = std::string::npos;
            if (hash_pos != std::string::npos) cut = hash_pos;
            if (slash_pos != std::string::npos) cut = (cut == std::string::npos) ? slash_pos : std::min(cut, slash_pos);
            if (cut != std::string::npos) stripped = stripped.substr(0, cut);
            auto trim = [](const std::string& s) {
                size_t start = 0;
                while (start < s.size() && std::isspace(static_cast<unsigned char>(s[start]))) start++;
                size_t end = s.size();
                while (end > start && std::isspace(static_cast<unsigned char>(s[end - 1]))) end--;
                return s.substr(start, end - start);
            };
            stripped = trim(stripped);
            if (stripped.empty()) continue;

            const size_t colon = stripped.find(':');
            if (colon == std::string::npos) continue;
            const std::string key = trim(stripped.substr(0, colon));
            std::string value = trim(stripped.substr(colon + 1));
            value = stripQuotes(value);
            if (key == "hx") *hx = value;
            else if (key == "hz") *hz = value;
            else if (key == "lx") *lx = value;
            else if (key == "lz") *lz = value;
        }
    }

    if (hx->empty() || hz->empty() || lx->empty() || lz->empty()) {
        *error = "CSS spec must define hx, hz, lx, lz";
        return false;
    }

    *hx = resolveSpecPath(base_dir, *hx);
    *hz = resolveSpecPath(base_dir, *hz);
    *lx = resolveSpecPath(base_dir, *lx);
    *lz = resolveSpecPath(base_dir, *lz);
    return true;
}

std::optional<CSSInput> loadCssInput(const std::vector<std::string>& args, std::string* error) {
    if (error == nullptr) return std::nullopt;

    std::string hx_path = getValuePrefix(args, "--css_hx=");
    std::string hz_path = getValuePrefix(args, "--css_hz=");
    std::string lx_path = getValuePrefix(args, "--css_lx=");
    std::string lz_path = getValuePrefix(args, "--css_lz=");
    const std::string spec_path = getValuePrefix(args, "--css_spec=");
    const std::string rep_arg = getValuePrefix(args, "--css_repetition=");
    const bool use_shor = hasFlag(args, "--css_shor");

    if (!rep_arg.empty()) {
        if (use_shor || !spec_path.empty() || !hx_path.empty() || !hz_path.empty()
            || !lx_path.empty() || !lz_path.empty()) {
            *error = "use either --css_repetition, --css_shor, --css_spec, or explicit --css_hx/--css_hz/--css_lx/--css_lz";
            return std::nullopt;
        }
        const int n = std::max(0, std::stoi(rep_arg));
        if (n < 2) {
            *error = "css_repetition requires n >= 2";
            return std::nullopt;
        }
        try {
            BinaryMatrix hx(0, n);
            BinaryMatrix hz(0, n);
            LogicalOperators logicals;
            RepetitionCode::buildCSS(n, &hx, &hz, &logicals);
            return CSSInput{std::move(hx), std::move(hz), std::move(logicals)};
        } catch (const std::exception& ex) {
            *error = ex.what();
            return std::nullopt;
        }
    }

    if (use_shor) {
        if (!spec_path.empty() || !hx_path.empty() || !hz_path.empty()
            || !lx_path.empty() || !lz_path.empty()) {
            *error = "use either --css_shor, --css_spec, or explicit --css_hx/--css_hz/--css_lx/--css_lz";
            return std::nullopt;
        }
        try {
            BinaryMatrix hx(0, 9);
            BinaryMatrix hz(0, 9);
            LogicalOperators logicals;
            ShorCode::buildCSS(&hx, &hz, &logicals);
            return CSSInput{std::move(hx), std::move(hz), std::move(logicals)};
        } catch (const std::exception& ex) {
            *error = ex.what();
            return std::nullopt;
        }
    }

    if (!spec_path.empty()) {
        if (!hx_path.empty() || !hz_path.empty() || !lx_path.empty() || !lz_path.empty()) {
            *error = "use either --css_spec or explicit --css_hx/--css_hz/--css_lx/--css_lz, not both";
            return std::nullopt;
        }
        std::string spec_error;
        if (!parseCssSpecFile(spec_path, &hx_path, &hz_path, &lx_path, &lz_path, &spec_error)) {
            *error = spec_error;
            return std::nullopt;
        }
    }

    if (hx_path.empty() || hz_path.empty()) {
        *error = "CSS requires --css_hx=<path> and --css_hz=<path> (or --css_spec=<path>)";
        return std::nullopt;
    }
    if (lx_path.empty() || lz_path.empty()) {
        *error = "CSS requires --css_lx=<path> and --css_lz=<path> (or --css_spec=<path>)";
        return std::nullopt;
    }

    BinaryMatrix hx(1, 1);
    BinaryMatrix hz(1, 1);
    std::string io_error;
    if (!loadBinaryMatrixFromFile(hx_path, &hx, &io_error)) {
        *error = "failed to load Hx: " + io_error;
        return std::nullopt;
    }
    if (!loadBinaryMatrixFromFile(hz_path, &hz, &io_error)) {
        *error = "failed to load Hz: " + io_error;
        return std::nullopt;
    }
    if (hx.cols() != hz.cols()) {
        *error = "CSS Hx/Hz column mismatch";
        return std::nullopt;
    }

    CSSCode code(hx, hz);
    if (!code.validateCSS()) {
        *error = "CSS validation failed (Hx * Hz^T not zero)";
        return std::nullopt;
    }

    LogicalOperators logicals;
    BinaryMatrix lx_mat(1, 1);
    BinaryMatrix lz_mat(1, 1);
    if (!loadBinaryMatrixFromFile(lx_path, &lx_mat, &io_error)) {
        *error = "failed to load Lx: " + io_error;
        return std::nullopt;
    }
    if (!loadBinaryMatrixFromFile(lz_path, &lz_mat, &io_error)) {
        *error = "failed to load Lz: " + io_error;
        return std::nullopt;
    }

    if (lx_mat.cols() != hx.cols() || lz_mat.cols() != hx.cols()) {
        *error = "logical operator length must match Hx/Hz column count";
        return std::nullopt;
    }

    logicals.LX.reserve(lx_mat.rows());
    for (int r = 0; r < lx_mat.rows(); ++r) {
        std::vector<int> row;
        row.reserve(lx_mat.cols());
        for (int c = 0; c < lx_mat.cols(); ++c) row.push_back(lx_mat.get(r, c));
        logicals.LX.push_back(std::move(row));
    }
    logicals.LZ.reserve(lz_mat.rows());
    for (int r = 0; r < lz_mat.rows(); ++r) {
        std::vector<int> row;
        row.reserve(lz_mat.cols());
        for (int c = 0; c < lz_mat.cols(); ++c) row.push_back(lz_mat.get(r, c));
        logicals.LZ.push_back(std::move(row));
    }

    for (const auto& lz : logicals.LZ) {
        const std::vector<int> lz_check = hx.multiply(lz);
        for (int v : lz_check) {
            if ((v & 1) != 0) {
                *error = "Lz does not commute with Hx (Hx * Lz != 0)";
                return std::nullopt;
            }
        }
    }
    for (const auto& lx : logicals.LX) {
        const std::vector<int> lx_check = hz.multiply(lx);
        for (int v : lx_check) {
            if ((v & 1) != 0) {
                *error = "Lx does not commute with Hz (Hz * Lx != 0)";
                return std::nullopt;
            }
        }
    }

    return CSSInput{std::move(hx), std::move(hz), std::move(logicals)};
}

std::string joinNames(const std::vector<std::string>& names) {
    std::string out;
    for (size_t i = 0; i < names.size(); ++i) {
        if (i > 0) out += "|";
        out += names[i];
    }
    return out;
}

const char* engineName(QECEngine engine) {
    switch (engine) {
        case QECEngine::Surface: return "surface";
        case QECEngine::CSS: return "css";
        case QECEngine::LDPC: return "ldpc";
        case QECEngine::Auto:
        default: return "auto";
    }
}

bool isSurfaceQecMode(const std::string& qec_mode) {
    return qec_mode == "surface_stub"
        || qec_mode == "surface_mwpm"
        || qec_mode == "surface_uf"
        || qec_mode == "surface_neural_mwpm";
}

void printHelp(const PluginRegistry& plugins) {
    const std::string surface_decoders = joinNames(plugins.list());
    std::cout << "LiDMaS+ usage\n"
              << "  ./lidmas                      Run classical LDPC BSC sweep (default)\n"
              << "  ./lidmas --engine=ldpc        Force LDPC engine mode\n"
              << "  ./lidmas --engine=css         Run CSS engine demo mode (pauli/hybrid)\n"
              << "  ./lidmas --engine=surface --surface_threshold ...\n"
              << "  ./lidmas --engine=css --css_threshold --css_spec=<path>\n"
              << "  ./lidmas --engine=css --css_threshold --css_repetition=<n>\n"
              << "  ./lidmas --engine=css --css_threshold --css_shor\n"
              << "  ./lidmas --engine=css --css_threshold --css_hx=<path> --css_hz=<path>\n"
              << "                             --css_lx=<path> --css_lz=<path>\n"
              << "  ./lidmas --qec=css_demo       Run CSS demo using BP decoder core\n"
              << "  ./lidmas --surface_demo=stub  Run surface pipeline demo (stub)\n"
              << "  ./lidmas --surface_demo=mwpm  Run surface pipeline demo (MWPM)\n"
              << "  ./lidmas --surface_demo=uf    Run surface pipeline demo (UF placeholder)\n"
              << "  ./lidmas --surface_demo=bp    Run surface pipeline demo (BP)\n"
              << "  ./lidmas --surface_demo=neural_mwpm  Run surface pipeline demo (neural-guided MWPM)\n"
              << "  ./lidmas --surface_threshold [--decoder=" << surface_decoders << "] [--d=3,5,7]\n"
              << "                               [--p_start=0.01 --p_end=0.15 --p_step=0.01]\n"
              << "                               [--sigma_start=0.05 --sigma_end=0.60 --sigma_step=0.05]\n"
              << "                               [--trials=2000 --seed=12345 --out=surface_threshold.csv]\n"
              << "                               [--mode=pauli|hybrid|gkp]\n"
              << "                               [--threads=<N>]\n"
              << "                               [--min_trials=200 --max_trials=20000 --batch_trials=200]\n"
              << "                               [--target_ci_halfwidth=0.01 --target_rel_ci=0.10]\n"
              << "                               [--auto_threshold]\n"
              << "                               [--estimate_threshold]\n"
              << "                               [--scaling_fit]\n"
              << "                               [--monotonic_smooth]\n"
              << "  ./lidmas --css_threshold [--decoder=bp|bp_sum|bp_nms]\n"
              << "                           --css_spec=<path>\n"
              << "                           [--css_hx=<path> --css_hz=<path>]\n"
              << "                           [--css_lx=<path> --css_lz=<path>]\n"
              << "                           [--p_start=0.001 --p_end=0.02 --p_step=0.001]\n"
              << "                           [--sigma_start=0.05 --sigma_end=0.25 --sigma_step=0.05]\n"
              << "                           [--trials=2000 --seed=7300000 --out=css_threshold.csv]\n"
              << "                           [--mode=pauli|hybrid]\n"
              << "                           [--min_trials=200 --max_trials=20000 --batch_trials=200]\n"
              << "                           [--target_ci_halfwidth=0.01 --target_rel_ci=0.10]\n"
              << "  ./lidmas --smoke              Run lightweight surface smoke checks\n"
              << "\n"
              << "Flags\n"
              << "  --engine=<surface|css|ldpc>   Select QEC engine routing (default auto)\n"
              << "  --surface_threshold           Run surface threshold workflow\n"
              << "  --css_threshold               Run CSS threshold workflow\n"
              << "  --css_spec=<path>             CSS code spec (JSON/YAML with hx/hz/lx/lz paths)\n"
              << "  --css_repetition=<n>          Build bit-flip repetition code (auto)\n"
              << "  --css_shor                    Build Shor [[9,1,3]] code (auto)\n"
              << "  --css_hx=<path>               CSS X-check matrix (dense 0/1 text)\n"
              << "  --css_hz=<path>               CSS Z-check matrix (dense 0/1 text)\n"
              << "  --css_lx=<path>               CSS logical-X operators (one or more rows)\n"
              << "  --css_lz=<path>               CSS logical-Z operators (one or more rows)\n"
              << "  --bp=sum-product              Use sum-product BP\n"
              << "  --bp=nms                      Use normalized min-sum BP\n"
              << "  --alpha=<value>               Set normalized min-sum alpha\n"
              << "  --neural_model=<path>         Neural model JSON file for neural_mwpm\n"
              << "  --weight_mode=<uniform|neural|llr> Select shared surface weight mode (default uniform)\n"
              << "  --uf_weighted                 Enable weighted Union-Find growth\n"
              << "  --neural_weights=<path>       Neural weights JSON for weighted uf\n"
              << "  --llr_p_data=<x>              LLR mode data-edge probability (default sweep p)\n"
              << "  --llr_p_meas=<x>              LLR mode measurement-edge probability (default sweep p)\n"
              << "  --llr_p_idle=<x>              LLR mode idle-edge probability (default sweep p)\n"
              << "  --llr_clamp_min=<x>           LLR probability clamp min (default 1e-12)\n"
              << "  --llr_clamp_max=<x>           LLR probability clamp max (default 1-1e-12)\n"
              << "  --mwpm_weight_scale=<x>       MWPM weight scaling factor (default 1000)\n"
              << "  --mwpm_graph=<full|simple>    MWPM graph topology mode (default full)\n"
              << "  --mode=<pauli|hybrid|gkp>     Surface error model mode (default pauli)\n"
              << "                                (also used by CSS demo/css_threshold)\n"
              << "  --gkp_gate=<x>               GKP gate error rate (mode=gkp)\n"
              << "  --gkp_meas=<x>               GKP measurement error rate (mode=gkp)\n"
              << "  --gkp_idle=<x>               GKP idle error rate (mode=gkp)\n"
              << "  --gkp_loss=<x>               GKP uniform per-qubit loss (mode=gkp)\n"
              << "  --gkp_loss_map=<path>        GKP per-qubit loss map (one row of doubles)\n"
              << "  --demo_sigma_start=<x>       Surface demo sigma sweep start (mode=gkp)\n"
              << "  --demo_sigma_end=<x>         Surface demo sigma sweep end (mode=gkp)\n"
              << "  --demo_sigma_step=<x>        Surface demo sigma sweep step (mode=gkp)\n"
              << "  --demo_sigma_values=<csv>    Surface demo sigma values list\n"
              << "  --demo_p_values=<csv>        Surface demo p values list (pauli mode)\n"
              << "  --demo_p_start=<x>           Surface demo p sweep start (pauli mode)\n"
              << "  --demo_p_end=<x>             Surface demo p sweep end (pauli mode)\n"
              << "  --demo_p_step=<x>            Surface demo p sweep step (pauli mode)\n"
              << "  --demo_d=<odd>               Surface demo distance (default 3)\n"
              << "  --demo_trials=<N>            Surface demo trials per point (default 200)\n"
              << "  --demo_seed=<uint>           Surface demo RNG seed base\n"
              << "  --demo_distance_list=<csv>   Surface demo distance list (odd, >=3)\n"
              << "  --demo_d_list=<csv>          Alias for --demo_distance_list\n"
              << "  --demo_seed_per_distance     Salt demo seed by distance\n"
              << "  --demo_sigma_by_d=<spec>     Per-distance sigma list, e.g. 3:0.10,0.12;5:0.14,0.16\n"
              << "  --demo_p_by_d=<spec>         Per-distance p list, e.g. 3:0.01,0.02;5:0.015\n"
              << "  --decoder=<name>              Surface: " << surface_decoders
              << " | CSS: bp|bp_sum|bp_nms\n"
              << "  --sigma_start=<x>             Hybrid sigma sweep start\n"
              << "  --sigma_end=<x>               Hybrid sigma sweep end\n"
              << "  --sigma_step=<x>              Hybrid sigma sweep step\n"
              << "  --cv_sigma=<x>                Single-point hybrid sigma (legacy alias)\n"
              << "  --min_trials=<N>              Adaptive threshold minimum trials per point\n"
              << "  --max_trials=<N>              Adaptive threshold maximum trials per point\n"
              << "  --batch_trials=<N>            Adaptive threshold trials per increment\n"
              << "  --target_ci_halfwidth=<x>     Stop when absolute LER CI half-width <= x\n"
              << "  --target_rel_ci=<x>           Stop when relative LER CI half-width <= x\n"
              << "  --threads=<N>                 OpenMP threads for surface_threshold\n"
              << "  --gpu                         Enable CUDA backend for pauli surface_threshold sampling\n"
              << "  --gpu_bench                   Run CPU vs GPU sampling benchmark (pauli only)\n"
              << "  --gpu_bench_quick             Run a short GPU benchmark preset\n"
              << "  --gpu_bench_full              Run a longer GPU benchmark preset\n"
              << "  --gpu_bench_d=<odd>            Benchmark distance (default 5)\n"
              << "  --gpu_bench_trials=<N>         Benchmark trials (default 2000)\n"
              << "  --gpu_bench_batch=<N>          Benchmark batch size (default 200)\n"
              << "  --gpu_bench_p=<x>              Benchmark Pauli p (default 0.05)\n"
              << "  --gpu_bench_seed=<uint>        Benchmark seed base (default 1337)\n"
              << "  --auto_threshold              Estimate threshold crossings after sweep\n"
              << "  --estimate_threshold          Pairwise crossing estimate of p_c\n"
              << "  --scaling_fit                Finite-size scaling fit for p_c and nu\n"
              << "  --scaling_bootstrap=<N>       Bootstrap samples for crossing/collapse CIs (default 200)\n"
              << "  --scaling_seed=<uint>         RNG seed for scaling bootstrap (default 12345)\n"
              << "  --pc_min=<x> --pc_max=<x>     Optional p_c search bounds override\n"
              << "  --nu_min=<x> --nu_max=<x>     Optional nu search bounds override\n"
              << "  --grid_pc=<N> --grid_nu=<N>   Grid resolution for collapse fit (default 61x51)\n"
              << "  --ler_smooth_eps=<x>          Isotonic smoothing tolerance epsilon (default 0)\n"
              << "  --scaling_report=<path>       Markdown scaling report path\n"
              << "  --scaling_json=<path>         JSON scaling summary path\n"
              << "  --quiet-iter-log              Disable per-iteration decode logging\n"
              << "  surface decoders              " << surface_decoders << "\n"
              << "  --help, -h                    Show this help text\n";
}

RuntimeOptions parseOptions(int argc, char** argv) {
    RuntimeOptions opts;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--bp=sum-product") {
            opts.mode = BeliefPropagation::Mode::SUM_PRODUCT;
        } else if (arg == "--bp=nms") {
            opts.mode = BeliefPropagation::Mode::NORMALIZED_MIN_SUM;
        } else if (arg.rfind("--alpha=", 0) == 0) {
            opts.alpha = std::stod(arg.substr(std::string("--alpha=").size()));
        } else if (arg == "--quiet-iter-log") {
            opts.log_decode_iterations = false;
        } else if (arg.rfind("--qec=", 0) == 0) {
            opts.qec_mode = arg.substr(std::string("--qec=").size());
        } else if (arg == "--selftest") {
            opts.selftest = true;
        }
    }
    return opts;
}

BeliefPropagation::Params makeParams(const RuntimeOptions& opts) {
    BeliefPropagation::Params params;
    params.max_iters = 80;
    params.damping = 0.0;
    params.mode = opts.mode;
    params.alpha = opts.alpha;
    params.llr_max = 50.0;
    params.convergence_tol = 1e-6;
    params.log_iteration_stats = false;
    return params;
}

bool buildLinearSweep(double start,
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

bool parseCssDecoderParams(const RuntimeOptions& opts,
                           const std::string& decoder_name,
                           BeliefPropagation::Params* params_out,
                           std::string* canonical_name) {
    if (params_out == nullptr || canonical_name == nullptr) return false;

    std::string name = decoder_name;
    if (name.empty()) name = "bp";

    BeliefPropagation::Params params = makeParams(opts);
    if (name == "bp") {
        *canonical_name = "bp";
    } else if (name == "bp_sum" || name == "bp_sum_product" || name == "sum-product") {
        params.mode = BeliefPropagation::Mode::SUM_PRODUCT;
        *canonical_name = "bp_sum";
    } else if (name == "bp_nms" || name == "nms") {
        params.mode = BeliefPropagation::Mode::NORMALIZED_MIN_SUM;
        *canonical_name = "bp_nms";
    } else {
        return false;
    }

    *params_out = params;
    return true;
}

int runQecCssDemo(const RuntimeOptions& opts,
                  const std::vector<std::string>& args,
                  const std::string& mode_arg) {
    if (mode_arg == "gkp") {
        std::cerr << "error: CSS demo does not support --mode=gkp\n";
        return 1;
    }
    const bool hybrid_mode = (mode_arg == "hybrid");
    const std::string decoder_arg = getValuePrefix(args, "--decoder=");

    BeliefPropagation::Params params;
    std::string decoder_name;
    if (!parseCssDecoderParams(opts, decoder_arg, &params, &decoder_name)) {
        std::cerr << "error: unknown CSS decoder '" << decoder_arg
                  << "' (expected bp|bp_sum|bp_nms)\n";
        return 1;
    }

    std::string css_error;
    auto css_input = loadCssInput(args, &css_error);
    if (!css_input.has_value()) {
        std::cerr << "error: " << css_error << "\n";
        return 1;
    }

    std::string out_path = getValuePrefix(args, "--out=");
    if (out_path.empty()) out_path = "qec_css_demo.csv";

    const std::string seed_arg = getValuePrefix(args, "--seed=");
    const uint64_t seed_base = seed_arg.empty()
        ? 7300000ULL
        : static_cast<uint64_t>(std::stoull(seed_arg));

    const std::string trials_arg = getValuePrefix(args, "--trials=");
    const int trials = trials_arg.empty() ? 200 : std::max(1, std::stoi(trials_arg));

    std::vector<double> sweep_values;
    std::string sweep_error;
    if (hybrid_mode) {
        const std::string p_start_arg = getValuePrefix(args, "--p_start=");
        const std::string p_end_arg = getValuePrefix(args, "--p_end=");
        const std::string p_step_arg = getValuePrefix(args, "--p_step=");
        if (!p_start_arg.empty() || !p_end_arg.empty() || !p_step_arg.empty()) {
            std::cout << "WARNING: ignoring --p_start/--p_end/--p_step in CSS hybrid mode\n";
        }

        const std::string sigma_start_arg = getValuePrefix(args, "--sigma_start=");
        const std::string sigma_end_arg = getValuePrefix(args, "--sigma_end=");
        const std::string sigma_step_arg = getValuePrefix(args, "--sigma_step=");
        const std::string cv_sigma_arg = getValuePrefix(args, "--cv_sigma=");
        const bool sigma_sweep_provided = !sigma_start_arg.empty() || !sigma_end_arg.empty() || !sigma_step_arg.empty();
        if (sigma_sweep_provided) {
            const double sigma_start = sigma_start_arg.empty() ? 0.05 : std::stod(sigma_start_arg);
            const double sigma_end = sigma_end_arg.empty() ? sigma_start : std::stod(sigma_end_arg);
            const double sigma_step = sigma_step_arg.empty() ? 0.05 : std::stod(sigma_step_arg);
            if (!buildLinearSweep(sigma_start, sigma_end, sigma_step, &sweep_values, &sweep_error)) {
                std::cerr << "error: invalid CSS hybrid sigma sweep: " << sweep_error << "\n";
                return 1;
            }
            if (!cv_sigma_arg.empty()) {
                std::cout << "WARNING: ignoring --cv_sigma because sigma sweep is explicitly set\n";
            }
        } else if (!cv_sigma_arg.empty()) {
            sweep_values = {std::max(0.0, std::stod(cv_sigma_arg))};
        } else {
            sweep_values = {0.05, 0.10, 0.15, 0.20, 0.25};
        }
    } else {
        const std::string sigma_start_arg = getValuePrefix(args, "--sigma_start=");
        const std::string sigma_end_arg = getValuePrefix(args, "--sigma_end=");
        const std::string sigma_step_arg = getValuePrefix(args, "--sigma_step=");
        const std::string cv_sigma_arg = getValuePrefix(args, "--cv_sigma=");
        if (!sigma_start_arg.empty() || !sigma_end_arg.empty() || !sigma_step_arg.empty() || !cv_sigma_arg.empty()) {
            std::cout << "WARNING: ignoring sigma options in CSS pauli mode\n";
        }

        const std::string p_start_arg = getValuePrefix(args, "--p_start=");
        const std::string p_end_arg = getValuePrefix(args, "--p_end=");
        const std::string p_step_arg = getValuePrefix(args, "--p_step=");
        const bool p_sweep_provided = !p_start_arg.empty() || !p_end_arg.empty() || !p_step_arg.empty();
        if (p_sweep_provided) {
            const double p_start = p_start_arg.empty() ? 0.001 : std::stod(p_start_arg);
            const double p_end = p_end_arg.empty() ? p_start : std::stod(p_end_arg);
            const double p_step = p_step_arg.empty() ? 0.001 : std::stod(p_step_arg);
            if (!buildLinearSweep(p_start, p_end, p_step, &sweep_values, &sweep_error)) {
                std::cerr << "error: invalid CSS pauli p sweep: " << sweep_error << "\n";
                return 1;
            }
        } else {
            sweep_values = {0.001, 0.010, 0.020};
        }
    }

    std::cout << "LiDMaS+ v0.6 Quantum CSS Demo\n";
    std::cout << "mode=" << (hybrid_mode ? "hybrid" : "pauli")
              << " decoder=" << decoder_name
              << " trials=" << trials
              << " out=" << out_path << "\n";

    const BinaryMatrix& Hx = css_input->hx;
    const BinaryMatrix& Hz = css_input->hz;
    const LogicalOperators& logicals = css_input->logicals;

    TannerGraph Gx(Hx);
    TannerGraph Gz(Hz);
    const auto dec_x_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(Gz, params);
    };
    const auto dec_z_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(Gx, params);
    };

    PauliChannelAdapter qec_channel;
    QuantumCSSSimulator sim(Hx, Hz, dec_x_factory, dec_z_factory, qec_channel);

    const QECNoiseModel noise_model = hybrid_mode ? QECNoiseModel::HYBRID_GKP : QECNoiseModel::INDEPENDENT_XZ;
    const std::string x_name = hybrid_mode ? "sigma" : "p";
    CSVWriter csv(out_path, x_name + ",ler_total,ler_x,ler_z,avg_iter_x,avg_iter_z");

    const auto sanity = CSSSimulation::run_point(sim, 0.0, trials, seed_base + 1000, &logicals, noise_model);
    std::cout << "[sanity] " << x_name << "=0.000"
              << "  LER_total=" << sanity.ler_total
              << "  LER_X=" << sanity.ler_x
              << "  LER_Z=" << sanity.ler_z
              << "  avg_iter_X=" << sanity.avg_iter_x
              << "  avg_iter_Z=" << sanity.avg_iter_z
              << "\n";

    const auto points = CSSSimulation::run_css_demo(
        sim, sweep_values, trials, seed_base, &logicals, noise_model);
    for (const auto& stats : points) {
        csv.writeCurve(
            stats.p,
            stats.ler_total,
            stats.ler_x,
            stats.ler_z,
            stats.avg_iter_x,
            stats.avg_iter_z
        );

        std::cout << x_name << "=" << std::fixed << std::setprecision(3) << stats.p
                  << "  LER_total=" << std::setprecision(6) << stats.ler_total
                  << "  LER_X=" << std::setprecision(6) << stats.ler_x
                  << "  LER_Z=" << std::setprecision(6) << stats.ler_z
                  << "  avg_iter_X=" << std::setprecision(2) << stats.avg_iter_x
                  << "  avg_iter_Z=" << std::setprecision(2) << stats.avg_iter_z
                  << "\n";
    }
    return 0;
}

int runCssThreshold(const RuntimeOptions& opts,
                    const std::vector<std::string>& args,
                    const std::string& mode_arg) {
    if (mode_arg == "gkp") {
        std::cerr << "error: CSS threshold does not support --mode=gkp\n";
        return 1;
    }
    const bool hybrid_mode = (mode_arg == "hybrid");
    const std::string decoder_arg = getValuePrefix(args, "--decoder=");

    BeliefPropagation::Params params;
    std::string decoder_name;
    if (!parseCssDecoderParams(opts, decoder_arg, &params, &decoder_name)) {
        std::cerr << "error: unknown CSS decoder '" << decoder_arg
                  << "' (expected bp|bp_sum|bp_nms)\n";
        return 1;
    }

    std::string css_error;
    auto css_input = loadCssInput(args, &css_error);
    if (!css_input.has_value()) {
        std::cerr << "error: " << css_error << "\n";
        return 1;
    }

    CSSThresholdConfig cfg;
    cfg.mode = hybrid_mode ? CSSNoiseMode::Hybrid : CSSNoiseMode::Pauli;
    cfg.decoder_name = decoder_name;

    const std::string trials_arg = getValuePrefix(args, "--trials=");
    if (!trials_arg.empty()) {
        cfg.trials = std::max(1, std::stoi(trials_arg));
        cfg.trials_explicit = true;
    }

    const std::string seed_arg = getValuePrefix(args, "--seed=");
    if (!seed_arg.empty()) {
        cfg.seed = static_cast<uint64_t>(std::stoull(seed_arg));
    }

    std::string out_arg = getValuePrefix(args, "--out=");
    if (out_arg.empty()) out_arg = getValuePrefix(args, "--output=");
    if (!out_arg.empty()) {
        cfg.out_csv = out_arg;
    }

    const std::string p_start_arg = getValuePrefix(args, "--p_start=");
    const std::string p_end_arg = getValuePrefix(args, "--p_end=");
    const std::string p_step_arg = getValuePrefix(args, "--p_step=");
    const std::string sigma_start_arg = getValuePrefix(args, "--sigma_start=");
    const std::string sigma_end_arg = getValuePrefix(args, "--sigma_end=");
    const std::string sigma_step_arg = getValuePrefix(args, "--sigma_step=");
    const std::string cv_sigma_arg = getValuePrefix(args, "--cv_sigma=");
    const bool p_sweep_provided = !p_start_arg.empty() || !p_end_arg.empty() || !p_step_arg.empty();
    const bool sigma_sweep_provided = !sigma_start_arg.empty() || !sigma_end_arg.empty() || !sigma_step_arg.empty();

    if (p_sweep_provided && sigma_sweep_provided) {
        std::cerr << "error: cannot provide both p sweep and sigma sweep arguments\n";
        return 1;
    }
    if (hybrid_mode) {
        if (p_sweep_provided) {
            std::cerr << "error: CSS hybrid mode does not allow --p_start/--p_end/--p_step\n";
            return 1;
        }
        if (sigma_sweep_provided) {
            if (!sigma_start_arg.empty()) cfg.sigma_start = std::stod(sigma_start_arg);
            if (!sigma_end_arg.empty()) cfg.sigma_end = std::stod(sigma_end_arg);
            if (!sigma_step_arg.empty()) cfg.sigma_step = std::stod(sigma_step_arg);
            if (!cv_sigma_arg.empty()) {
                std::cout << "WARNING: ignoring --cv_sigma because sigma sweep is explicitly set\n";
            }
        } else if (!cv_sigma_arg.empty()) {
            cfg.sigma_start = std::max(0.0, std::stod(cv_sigma_arg));
            cfg.sigma_end = cfg.sigma_start;
            cfg.sigma_step = 1.0;
        }
    } else {
        if (sigma_sweep_provided || !cv_sigma_arg.empty()) {
            std::cerr << "error: CSS pauli mode does not allow sigma sweep arguments\n";
            return 1;
        }
        if (p_sweep_provided) {
            if (!p_start_arg.empty()) cfg.p_start = std::stod(p_start_arg);
            if (!p_end_arg.empty()) cfg.p_end = std::stod(p_end_arg);
            if (!p_step_arg.empty()) cfg.p_step = std::stod(p_step_arg);
        }
    }

    bool adaptive_requested = false;
    const std::string min_trials_arg = getValuePrefix(args, "--min_trials=");
    if (!min_trials_arg.empty()) {
        cfg.min_trials = std::max(1, std::stoi(min_trials_arg));
        adaptive_requested = true;
    }
    const std::string max_trials_arg = getValuePrefix(args, "--max_trials=");
    if (!max_trials_arg.empty()) {
        cfg.max_trials = std::max(1, std::stoi(max_trials_arg));
        adaptive_requested = true;
    }
    const std::string batch_trials_arg = getValuePrefix(args, "--batch_trials=");
    if (!batch_trials_arg.empty()) {
        cfg.batch_trials = std::max(1, std::stoi(batch_trials_arg));
        adaptive_requested = true;
    }
    const std::string target_abs_arg = getValuePrefix(args, "--target_ci_halfwidth=");
    if (!target_abs_arg.empty()) {
        cfg.target_ci_halfwidth = std::max(0.0, std::stod(target_abs_arg));
        adaptive_requested = true;
    }
    const std::string target_rel_arg = getValuePrefix(args, "--target_rel_ci=");
    if (!target_rel_arg.empty()) {
        cfg.target_rel_ci = std::stod(target_rel_arg);
        adaptive_requested = true;
    }
    cfg.adaptive_enabled = adaptive_requested;

    return CSSThresholdRunner::run(cfg, params, css_input->hx, css_input->hz, css_input->logicals);
}

std::vector<int> parseDistancesCsv(const std::string& s) {
    std::vector<int> out;
    if (s.empty()) return out;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ',')) {
        if (item.empty()) continue;
        const int d = std::stoi(item);
        if (d >= 3 && (d % 2) == 1) out.push_back(d);
    }
    return out;
}

std::string trim(const std::string& s) {
    size_t start = 0;
    while (start < s.size() && std::isspace(static_cast<unsigned char>(s[start]))) start++;
    size_t end = s.size();
    while (end > start && std::isspace(static_cast<unsigned char>(s[end - 1]))) end--;
    return s.substr(start, end - start);
}

std::vector<double> parseDoubleCsv(const std::string& s) {
    std::vector<double> out;
    if (s.empty()) return out;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ',')) {
        item = trim(item);
        if (item.empty()) continue;
        out.push_back(std::stod(item));
    }
    return out;
}

std::map<int, std::vector<double>> parseSigmaByDistance(const std::string& s) {
    std::map<int, std::vector<double>> out;
    if (s.empty()) return out;
    std::stringstream ss(s);
    std::string entry;
    while (std::getline(ss, entry, ';')) {
        entry = trim(entry);
        if (entry.empty()) continue;
        const size_t colon = entry.find(':');
        if (colon == std::string::npos) continue;
        std::string d_str = trim(entry.substr(0, colon));
        std::string vals_str = trim(entry.substr(colon + 1));
        if (d_str.empty() || vals_str.empty()) continue;
        const int d = std::stoi(d_str);
        const std::vector<double> vals = parseDoubleCsv(vals_str);
        if (!vals.empty()) out[d] = vals;
    }
    return out;
}

std::vector<double> makeSweepGrid(double start, double end, double step) {
    std::vector<double> out;
    if (step <= 0.0) return out;
    if (end < start) std::swap(start, end);
    constexpr double kEps = 1e-12;
    for (double v = start; v <= end + kEps; v += step) out.push_back(v);
    return out;
}

struct SurfaceGkpConfig {
    double gate_error = 0.0;
    double meas_error = 0.0;
    double idle_error = 0.0;
    double loss_prob = 0.0;
    std::vector<double> loss_map;
};

struct SurfaceDemoSweepConfig {
    std::vector<double> p_values;
    std::vector<double> sigma_values;
};

int runQecSurfaceDemo(const std::string& mode,
                      const std::string& surface_mode,
                      const SurfaceGkpConfig& gkp_cfg,
                      const SurfaceDemoSweepConfig& demo_sweep,
                      int demo_d,
                      int demo_trials,
                      uint64_t demo_seed,
                      const std::vector<int>& demo_distances,
                      bool demo_seed_per_distance,
                      const std::map<int, std::vector<double>>& demo_sigma_by_d,
                      const std::map<int, std::vector<double>>& demo_p_by_d,
                      const std::string& weight_mode,
                      const std::string& mwpm_graph,
                      bool uf_weighted,
                      const std::string& neural_weights_path,
                      const std::string& neural_model_path,
                      double llr_p_data,
                      double llr_p_meas,
                      double llr_p_idle,
                      double llr_clamp_min,
                      double llr_clamp_max,
                      double mwpm_weight_scale,
                      BeliefPropagation::Mode bp_mode,
                      double bp_alpha,
                      const PluginRegistry& plugins) {
    std::string decoder = mode;
    if (decoder.empty()) decoder = "stub";
    if (decoder == "mwpm_stub") decoder = "stub";
    const std::vector<std::string> available = plugins.list();
    if (std::find(available.begin(), available.end(), decoder) == available.end()) {
        std::cout << "Unknown surface demo mode '" << mode
                  << "', falling back to stub.\n";
        decoder = "stub";
    }
    if (!validateNeuralModelRequirement(decoder, neural_model_path)) {
        return 1;
    }
    std::cout << (decoder == "mwpm"
                     ? "LiDMaS+ Surface MWPM Demo (experimental)\n"
                     : (decoder == "uf"
                            ? "LiDMaS+ Surface UF Demo (experimental)\n"
                            : (decoder == "neural_mwpm"
                                   ? "LiDMaS+ Surface Neural MWPM Demo (experimental)\n"
                                   : "LiDMaS+ Surface Stub Demo (experimental)\n")));

    SurfaceSweepConfig cfg;
    SurfaceNoiseMode demo_mode = SurfaceNoiseMode::Pauli;
    if (surface_mode == "gkp") {
        demo_mode = SurfaceNoiseMode::GKP;
    } else if (surface_mode == "hybrid") {
        std::cerr << "error: surface demo does not support --mode=hybrid (use --mode=gkp or pauli)\n";
        return 1;
    }
    cfg.d = std::max(3, demo_d);
    if ((cfg.d % 2) == 0) cfg.d += 1;
    cfg.trials = std::max(1, demo_trials);
    cfg.seed_base = demo_seed;
    cfg.p_values = {0.00, 0.02, 0.05, 0.08};
    cfg.mode = demo_mode;
    if (demo_mode == SurfaceNoiseMode::GKP) {
        if (cfg.sigma_values.empty()) {
            cfg.sigma_values = {0.10, 0.15, 0.20};
        }
        cfg.gkp_gate_error = gkp_cfg.gate_error;
        cfg.gkp_meas_error = gkp_cfg.meas_error;
        cfg.gkp_idle_error = gkp_cfg.idle_error;
        cfg.gkp_loss_prob = gkp_cfg.loss_prob;
        cfg.gkp_loss_map = gkp_cfg.loss_map;
    }
    if (!demo_sweep.p_values.empty()) {
        cfg.p_values = demo_sweep.p_values;
    }
    if (!demo_sweep.sigma_values.empty()) {
        cfg.sigma_values = demo_sweep.sigma_values;
    }
    cfg.decoder_name = decoder;
    cfg.weight_mode = weight_mode;
    cfg.mwpm_graph = mwpm_graph;
    cfg.uf_weighted = uf_weighted || (weight_mode == "neural") || (weight_mode == "llr");
    cfg.llr_p_data = llr_p_data;
    cfg.llr_p_meas = llr_p_meas;
    cfg.llr_p_idle = llr_p_idle;
    cfg.llr_clamp_min = llr_clamp_min;
    cfg.llr_clamp_max = llr_clamp_max;
    cfg.mwpm_weight_scale = mwpm_weight_scale;
    cfg.bp_mode = bp_mode;
    cfg.bp_alpha = bp_alpha;
    cfg.neural_weights_path = neural_weights_path;
    cfg.neural_model_path = neural_model_path;

    std::vector<int> distances = demo_distances;
    if (distances.empty()) distances.push_back(cfg.d);
    const char* sweep_label = (demo_mode == SurfaceNoiseMode::GKP) ? "sigma" : "p";
    bool warned_sigma_override = false;
    bool warned_p_override = false;
    for (int d : distances) {
        if (d < 3) continue;
        const int requested_d = d;
        if ((d % 2) == 0) d += 1;
        cfg.d = d;
        if (demo_seed_per_distance) {
            cfg.seed_base = demo_seed + static_cast<uint64_t>(d) * 1000003ULL;
        } else {
            cfg.seed_base = demo_seed;
        }
        if (demo_mode == SurfaceNoiseMode::GKP && !demo_sigma_by_d.empty()) {
            auto it = demo_sigma_by_d.find(requested_d);
            if (it == demo_sigma_by_d.end() && requested_d != d) {
                it = demo_sigma_by_d.find(d);
            }
            if (it != demo_sigma_by_d.end() && !it->second.empty()) {
                cfg.sigma_values = it->second;
            }
        } else if (demo_mode != SurfaceNoiseMode::GKP && !demo_sigma_by_d.empty() && !warned_sigma_override) {
            std::cout << "WARNING: --demo_sigma_by_d ignored in pauli mode\n";
            warned_sigma_override = true;
        }
        if (demo_mode == SurfaceNoiseMode::Pauli && !demo_p_by_d.empty()) {
            auto it = demo_p_by_d.find(requested_d);
            if (it == demo_p_by_d.end() && requested_d != d) {
                it = demo_p_by_d.find(d);
            }
            if (it != demo_p_by_d.end() && !it->second.empty()) {
                cfg.p_values = it->second;
            }
        } else if (demo_mode != SurfaceNoiseMode::Pauli && !demo_p_by_d.empty() && !warned_p_override) {
            std::cout << "WARNING: --demo_p_by_d ignored in gkp mode\n";
            warned_p_override = true;
        }
        const auto points = SurfaceSimulation::run_decoder_sweep(cfg, plugins);
        std::cout << "distance=" << d << " trials=" << cfg.trials << " seed=" << cfg.seed_base << "\n";
        for (const auto& s : points) {
            std::cout << sweep_label << "=" << std::fixed << std::setprecision(3) << s.p
                      << "  defect_count_avg=" << std::setprecision(4) << s.defect_count_avg
                      << "  correction_weight_avg=" << std::setprecision(4) << s.correction_weight_avg
                      << "  logical_fail_rate=" << std::setprecision(6) << s.logical_fail_rate
                      << "\n";
        }
    }
    return 0;
}

void runDebugDecodeLog(const BinaryMatrix& H,
                       const TannerGraph& G,
                       const BeliefPropagation::Params& params,
                       int n,
                       double p_error,
                       int seed,
                       const std::string& label) {
    BeliefPropagation::Params debug_params = params;
    debug_params.log_iteration_stats = true;
    debug_params.log_llr_breakdown = false;
    debug_params.log_edge_debug = true;
    debug_params.edge_debug_var = 0;
    BPDecoderAdapter decoder(G, debug_params);

    std::mt19937 rng(seed);
    std::bernoulli_distribution flip(p_error);

    std::vector<int> received(n, 0);
    std::vector<int> erasures(n, 0);
    for (int i = 0; i < n; ++i)
        received[i] = flip(rng) ? 1 : 0;

    std::cout << "[decode-log] " << label
              << " p=" << std::setprecision(3) << p_error
              << "\n";
    const std::vector<int> no_syndrome = zero_syndrome(H.rows());
    DecodeRequest req;
    req.syndrome = &no_syndrome;
    req.received_bits = &received;
    req.erasures = &erasures;
    req.p_error = p_error;
    const DecodeResult dec = decoder.decode(req);
    std::cout << "  hit_max_iters=" << (dec.hit_max_iters ? "yes" : "no")
              << "\n";
}

void runSweep(const SweepConfig& cfg, const RuntimeOptions& opts) {
    std::cout << "\n=== Sweep " << cfg.label
              << " (n=" << cfg.n
              << ", m=" << cfg.m
              << ", col_w=" << cfg.col_weight
              << ", trials=" << cfg.trials
              << ") ===\n";

    BinaryMatrix H = LDPCGenerator::generatePEG(cfg.m, cfg.n, cfg.col_weight, 42);
    TannerGraph G(H);

    GraphDiagnostics::printDegreeDistribution(
        GraphDiagnostics::variableDegreeDistribution(G), "Variable");
    GraphDiagnostics::printDegreeDistribution(
        GraphDiagnostics::checkDegreeDistribution(G), "Check");

    const int girth_bounded = GraphDiagnostics::estimateGirthBounded(G, 12);
    if (girth_bounded > 0) {
        std::cout << "Estimated girth (bounded search): " << girth_bounded
                  << " (<=12)\n";
    } else {
        std::cout << "Estimated girth (bounded search): >12\n";
    }

    const BeliefPropagation::Params params = makeParams(opts);
    BSCChannel channel;
    const auto decoder_factory = [&]() -> std::unique_ptr<IDecoder> {
        return std::make_unique<BPDecoderAdapter>(G, params);
    };

    CSVWriter csv(cfg.csv_file, "p,ber,fer,avg_iterations,parity_sat_rate,max_iter_hit_rate");

    const char* mode_name = (opts.mode == BeliefPropagation::Mode::SUM_PRODUCT)
        ? "SUM_PRODUCT"
        : "NORMALIZED_MIN_SUM";
    std::cout << "Decoder mode=" << mode_name
              << " alpha=" << opts.alpha
              << " llr_max=" << params.llr_max
              << " max_iters=" << params.max_iters
              << "\n";

    // Sanity checks
    const int sanity_trials = std::min(100, cfg.trials);
    const auto zero_noise = LDPCSimulation::run_point(H, decoder_factory, channel, cfg.n, sanity_trials, 0.0, 9100000);
    const auto tiny_noise = LDPCSimulation::run_point(H, decoder_factory, channel, cfg.n, sanity_trials, 0.001, 9200000);

    std::cout << "[sanity] p=0.000  BER=" << zero_noise.ber
              << " FER=" << zero_noise.fer
              << " avg_iter=" << zero_noise.avg_iter
              << " parity_sat=" << zero_noise.parity_sat_rate
              << "\n";
    if (zero_noise.ber > 1e-12 || zero_noise.fer > 1e-12) {
        std::cout << "WARNING: zero-noise sanity failed (expected BER=FER=0)\n";
    }

    std::cout << "[sanity] p=0.001  BER=" << tiny_noise.ber
              << " FER=" << tiny_noise.fer
              << " avg_iter=" << tiny_noise.avg_iter
              << " parity_sat=" << tiny_noise.parity_sat_rate
              << "\n";
    if (tiny_noise.fer > 0.05) {
        std::cout << "WARNING: small-noise sanity FER is unexpectedly high\n";
    }

    std::cout << std::fixed;
    std::vector<double> p_vals;
    std::vector<double> fer_vals;
    bool fer_monotonic = true;

    for (double p_error = cfg.p_start; p_error <= cfg.p_end + 1e-12; p_error += cfg.p_step) {
        std::cout << "log((1-p)/p)="
                  << std::log((1.0 - p_error) / p_error)
                  << "\n";

        if (opts.log_decode_iterations) {
            const int log_seed = ldpc_debug_seed(p_error, cfg.n);
            runDebugDecodeLog(H, G, params, cfg.n, p_error, log_seed, cfg.label);
        }

        const auto stats = LDPCSimulation::run_point(
            H, decoder_factory, channel, cfg.n, cfg.trials, p_error, 1234567);
        csv.writeCurve(p_error, stats.ber, stats.fer, stats.avg_iter, stats.parity_sat_rate, stats.max_iter_hit_rate);

        std::cout << "n=" << cfg.n
                  << " p=" << std::setprecision(3) << p_error
                  << " BER=" << std::setprecision(6) << stats.ber
                  << " FER=" << std::setprecision(6) << stats.fer
                  << " avg_iter=" << std::setprecision(2) << stats.avg_iter
                  << " parity_sat=" << std::setprecision(4) << stats.parity_sat_rate
                  << " max_iter_hit=" << std::setprecision(4) << stats.max_iter_hit_rate
                  << "\n";

        if (!fer_vals.empty() && stats.fer + 1e-12 < fer_vals.back()) {
            fer_monotonic = false;
            std::cout << "WARNING: FER non-monotonic between p=" << p_vals.back()
                      << " (FER=" << fer_vals.back() << ") and p=" << p_error
                      << " (FER=" << stats.fer << ")\n";
        }

        p_vals.push_back(p_error);
        fer_vals.push_back(stats.fer);
    }

    std::cout << "FER monotonicity check: " << (fer_monotonic ? "PASS" : "FAIL") << "\n";
}

} // namespace

int main(int argc, char** argv) {
    const std::vector<std::string> args = toArgs(argc, argv);
    PluginRegistry plugins;
    RegisterAllPlugins(plugins);
    std::string weight_mode = getValuePrefix(args, "--weight_mode=");
    if (weight_mode.empty()) weight_mode = "uniform";
    if (weight_mode != "uniform" && weight_mode != "neural" && weight_mode != "llr") {
        std::cout << "Unknown --weight_mode='" << weight_mode
                  << "', falling back to uniform.\n";
        weight_mode = "uniform";
    }
    std::string mwpm_graph = getValuePrefix(args, "--mwpm_graph=");
    if (mwpm_graph.empty()) mwpm_graph = "full";
    if (mwpm_graph != "full" && mwpm_graph != "simple") {
        std::cout << "Unknown --mwpm_graph='" << mwpm_graph
                  << "', falling back to full.\n";
        mwpm_graph = "full";
    }
    const std::string llr_p_data_arg = getValuePrefix(args, "--llr_p_data=");
    const std::string llr_p_meas_arg = getValuePrefix(args, "--llr_p_meas=");
    const std::string llr_p_idle_arg = getValuePrefix(args, "--llr_p_idle=");
    const std::string llr_clamp_min_arg = getValuePrefix(args, "--llr_clamp_min=");
    const std::string llr_clamp_max_arg = getValuePrefix(args, "--llr_clamp_max=");
    const std::string mwpm_weight_scale_arg = getValuePrefix(args, "--mwpm_weight_scale=");
    const double llr_p_data = llr_p_data_arg.empty() ? -1.0 : std::stod(llr_p_data_arg);
    const double llr_p_meas = llr_p_meas_arg.empty() ? -1.0 : std::stod(llr_p_meas_arg);
    const double llr_p_idle = llr_p_idle_arg.empty() ? -1.0 : std::stod(llr_p_idle_arg);
    const double llr_clamp_min = llr_clamp_min_arg.empty() ? 1e-12 : std::stod(llr_clamp_min_arg);
    const double llr_clamp_max = llr_clamp_max_arg.empty() ? (1.0 - 1e-12) : std::stod(llr_clamp_max_arg);
    const double mwpm_weight_scale = mwpm_weight_scale_arg.empty() ? 1000.0 : std::stod(mwpm_weight_scale_arg);
    const bool uf_weighted = hasFlag(args, "--uf_weighted");
    const std::string neural_weights_path = getValuePrefix(args, "--neural_weights=");
    const std::string neural_model_path = getValuePrefix(args, "--neural_model=");
    std::string surface_mode = getValuePrefix(args, "--mode=");
    if (surface_mode.empty()) surface_mode = "pauli";
    if (surface_mode == "discrete") surface_mode = "pauli"; // backward-compatible alias
    if (surface_mode != "pauli" && surface_mode != "hybrid" && surface_mode != "gkp") {
        std::cout << "Unknown --mode='" << surface_mode
                  << "', falling back to pauli.\n";
        surface_mode = "pauli";
    }
    SurfaceGkpConfig gkp_cfg;
    const std::string gkp_gate = getValuePrefix(args, "--gkp_gate=");
    if (!gkp_gate.empty()) gkp_cfg.gate_error = std::stod(gkp_gate);
    const std::string gkp_meas = getValuePrefix(args, "--gkp_meas=");
    if (!gkp_meas.empty()) gkp_cfg.meas_error = std::stod(gkp_meas);
    const std::string gkp_idle = getValuePrefix(args, "--gkp_idle=");
    if (!gkp_idle.empty()) gkp_cfg.idle_error = std::stod(gkp_idle);
    const std::string gkp_loss = getValuePrefix(args, "--gkp_loss=");
    if (!gkp_loss.empty()) gkp_cfg.loss_prob = std::stod(gkp_loss);
    const std::string gkp_loss_map = getValuePrefix(args, "--gkp_loss_map=");
    if (!gkp_loss_map.empty()) {
        std::string loss_error;
        if (!loadDoubleVectorFromFile(gkp_loss_map, &gkp_cfg.loss_map, &loss_error)) {
            std::cerr << "error: failed to load gkp_loss_map: " << loss_error << "\n";
            return 1;
        }
    }
    SurfaceDemoSweepConfig demo_sweep;
    const std::string demo_sigma_values_arg = getValuePrefix(args, "--demo_sigma_values=");
    const std::string demo_sigma_start_arg = getValuePrefix(args, "--demo_sigma_start=");
    const std::string demo_sigma_end_arg = getValuePrefix(args, "--demo_sigma_end=");
    const std::string demo_sigma_step_arg = getValuePrefix(args, "--demo_sigma_step=");
    const std::string demo_sigma_by_d_arg = getValuePrefix(args, "--demo_sigma_by_d=");
    const std::string demo_p_by_d_arg = getValuePrefix(args, "--demo_p_by_d=");
    const std::string demo_p_values_arg = getValuePrefix(args, "--demo_p_values=");
    const std::string demo_p_start_arg = getValuePrefix(args, "--demo_p_start=");
    const std::string demo_p_end_arg = getValuePrefix(args, "--demo_p_end=");
    const std::string demo_p_step_arg = getValuePrefix(args, "--demo_p_step=");
    const std::string demo_d_arg = getValuePrefix(args, "--demo_d=");
    const std::string demo_trials_arg = getValuePrefix(args, "--demo_trials=");
    const std::string demo_seed_arg = getValuePrefix(args, "--demo_seed=");
    std::string demo_distance_list_arg = getValuePrefix(args, "--demo_distance_list=");
    if (demo_distance_list_arg.empty()) {
        demo_distance_list_arg = getValuePrefix(args, "--demo_d_list=");
    }

    int demo_d = 3;
    int demo_trials = 200;
    uint64_t demo_seed = 8400000;
    std::vector<int> demo_distances;
    const bool demo_seed_per_distance = hasFlag(args, "--demo_seed_per_distance");
    const std::map<int, std::vector<double>> demo_sigma_by_d = parseSigmaByDistance(demo_sigma_by_d_arg);
    const std::map<int, std::vector<double>> demo_p_by_d = parseSigmaByDistance(demo_p_by_d_arg);
    if (!demo_d_arg.empty()) {
        demo_d = std::stoi(demo_d_arg);
    }
    if (!demo_trials_arg.empty()) {
        demo_trials = std::stoi(demo_trials_arg);
    }
    if (!demo_seed_arg.empty()) {
        demo_seed = static_cast<uint64_t>(std::stoull(demo_seed_arg));
    }
    if (!demo_distance_list_arg.empty()) {
        demo_distances = parseDistancesCsv(demo_distance_list_arg);
    }

    if (!demo_sigma_values_arg.empty()) {
        demo_sweep.sigma_values = parseDoubleCsv(demo_sigma_values_arg);
    } else if (!demo_sigma_start_arg.empty() || !demo_sigma_end_arg.empty() || !demo_sigma_step_arg.empty()) {
        const double start = demo_sigma_start_arg.empty() ? 0.1 : std::stod(demo_sigma_start_arg);
        const double end = demo_sigma_end_arg.empty() ? start : std::stod(demo_sigma_end_arg);
        const double step = demo_sigma_step_arg.empty() ? 0.05 : std::stod(demo_sigma_step_arg);
        demo_sweep.sigma_values = makeSweepGrid(start, end, step);
    }

    if (!demo_p_values_arg.empty()) {
        demo_sweep.p_values = parseDoubleCsv(demo_p_values_arg);
    } else if (!demo_p_start_arg.empty() || !demo_p_end_arg.empty() || !demo_p_step_arg.empty()) {
        const double start = demo_p_start_arg.empty() ? 0.0 : std::stod(demo_p_start_arg);
        const double end = demo_p_end_arg.empty() ? start : std::stod(demo_p_end_arg);
        const double step = demo_p_step_arg.empty() ? 0.02 : std::stod(demo_p_step_arg);
        demo_sweep.p_values = makeSweepGrid(start, end, step);
    }

    if (demo_sweep.sigma_values.empty()) {
        const std::string sigma_start_arg = getValuePrefix(args, "--sigma_start=");
        const std::string sigma_end_arg = getValuePrefix(args, "--sigma_end=");
        const std::string sigma_step_arg = getValuePrefix(args, "--sigma_step=");
        if (!sigma_start_arg.empty() || !sigma_end_arg.empty() || !sigma_step_arg.empty()) {
            const double start = sigma_start_arg.empty() ? 0.1 : std::stod(sigma_start_arg);
            const double end = sigma_end_arg.empty() ? start : std::stod(sigma_end_arg);
            const double step = sigma_step_arg.empty() ? 0.05 : std::stod(sigma_step_arg);
            demo_sweep.sigma_values = makeSweepGrid(start, end, step);
        }
    }
    const std::string cv_sigma_arg = getValuePrefix(args, "--cv_sigma=");
    const double cv_sigma = cv_sigma_arg.empty() ? 0.0 : std::max(0.0, std::stod(cv_sigma_arg));
    const RuntimeOptions opts = parseOptions(argc, argv);

    const std::string qec_mode = getValuePrefix(args, "--qec=");
    const bool has_surface_demo_flag = hasFlag(args, "--surface_demo");
    const std::string surface_demo_mode = getValuePrefix(args, "--surface_demo=");
    const bool has_surface_demo_request = has_surface_demo_flag || !surface_demo_mode.empty();
    const bool has_surface_threshold = hasFlag(args, "--surface_threshold");
    const bool has_gpu_bench = hasFlag(args, "--gpu_bench");
    const bool has_css_threshold = hasFlag(args, "--css_threshold");
    const bool has_css_qec_mode = (qec_mode == "css_demo");
    const bool has_surface_qec_mode = isSurfaceQecMode(qec_mode);

    const std::string engine_arg = getValuePrefix(args, "--engine=");
    bool engine_explicit = !engine_arg.empty();
    QECEngine engine = QECEngine::Auto;
    if (engine_explicit) {
        if (engine_arg == "surface") {
            engine = QECEngine::Surface;
        } else if (engine_arg == "css") {
            engine = QECEngine::CSS;
        } else if (engine_arg == "ldpc") {
            engine = QECEngine::LDPC;
        } else {
            std::cerr << "error: unknown --engine='" << engine_arg
                      << "' (expected surface|css|ldpc)\n";
            return 1;
        }
    }
    if (hasFlag(args, "--help") || hasFlag(args, "-h")) {
        printHelp(plugins);
        return 0;
    }
    if (!qec_mode.empty() && !has_css_qec_mode && !has_surface_qec_mode) {
        std::cerr << "error: unknown --qec mode '" << qec_mode << "'\n";
        return 1;
    }
    if (engine_explicit) {
        if (engine == QECEngine::Surface) {
            if (has_css_qec_mode || has_css_threshold) {
                std::cerr << "error: CSS commands are incompatible with --engine=surface\n";
                return 1;
            }
        } else if (engine == QECEngine::CSS) {
            if (has_surface_threshold || has_surface_demo_request || has_surface_qec_mode) {
                std::cerr << "error: surface commands require --engine=surface (current engine="
                          << engineName(engine) << ")\n";
                return 1;
            }
        } else if (engine == QECEngine::LDPC) {
            if (has_surface_threshold || has_surface_demo_request || has_surface_qec_mode
                || has_css_qec_mode || has_css_threshold) {
                std::cerr << "error: qec/surface commands are incompatible with --engine=ldpc\n";
                return 1;
            }
        }
    }
    if (has_gpu_bench) {
        const bool bench_quick = hasFlag(args, "--gpu_bench_quick");
        const bool bench_full = hasFlag(args, "--gpu_bench_full");
        int bench_d = 5;
        int bench_trials = 2000;
        int bench_batch = 200;
        if (bench_full) {
            bench_d = 7;
            bench_trials = 10000;
            bench_batch = 500;
        } else if (bench_quick) {
            bench_d = 3;
            bench_trials = 500;
            bench_batch = 100;
        }
        double bench_p = 0.05;
        uint64_t bench_seed = 1337;

        const std::string bench_d_arg = getValuePrefix(args, "--gpu_bench_d=");
        if (!bench_d_arg.empty()) bench_d = std::max(3, std::stoi(bench_d_arg));
        const std::string bench_trials_arg = getValuePrefix(args, "--gpu_bench_trials=");
        if (!bench_trials_arg.empty()) bench_trials = std::max(1, std::stoi(bench_trials_arg));
        const std::string bench_batch_arg = getValuePrefix(args, "--gpu_bench_batch=");
        if (!bench_batch_arg.empty()) bench_batch = std::max(1, std::stoi(bench_batch_arg));
        const std::string bench_p_arg = getValuePrefix(args, "--gpu_bench_p=");
        if (!bench_p_arg.empty()) bench_p = std::stod(bench_p_arg);
        const std::string bench_seed_arg = getValuePrefix(args, "--gpu_bench_seed=");
        if (!bench_seed_arg.empty()) bench_seed = static_cast<uint64_t>(std::stoull(bench_seed_arg));

        return run_gpu_bench(bench_d, bench_trials, bench_batch, bench_p, bench_seed);
    }

    if (has_surface_threshold && has_css_threshold) {
        std::cerr << "error: use either --surface_threshold or --css_threshold, not both\n";
        return 1;
    }
    if (hasFlag(args, "--smoke")) {
        SmokeConfig smoke_cfg;
        smoke_cfg.distance = 3;
        smoke_cfg.p = 0.02;
        smoke_cfg.trials = 50;
        smoke_cfg.seed = 1337;
        smoke_cfg.decoder_name = "mwpm";
        smoke_cfg.mode = "pauli";
        smoke_cfg.weight_mode = "uniform";
        const bool ok = run_smoke_tests(smoke_cfg);
        return ok ? 0 : 1;
    }
    if (has_css_threshold) {
        if (engine_explicit && engine != QECEngine::CSS) {
            std::cerr << "error: --css_threshold requires --engine=css\n";
            return 1;
        }
        return runCssThreshold(opts, args, surface_mode);
    }
    if (has_surface_threshold) {
        if (engine_explicit && engine != QECEngine::Surface) {
            std::cerr << "error: --surface_threshold requires --engine=surface\n";
            return 1;
        }
        SurfaceThresholdConfig cfg;
        cfg.bp_mode = opts.mode;
        cfg.bp_alpha = opts.alpha;
        bool adaptive_requested = false;
        const std::string decoder = getValuePrefix(args, "--decoder=");
        if (!decoder.empty()) cfg.decoder_name = decoder;
        std::string d_csv = getValuePrefix(args, "--d=");
        if (d_csv.empty()) d_csv = getValuePrefix(args, "--d_list=");
        if (!d_csv.empty()) {
            const auto dlist = parseDistancesCsv(d_csv);
            if (!dlist.empty()) cfg.distances = dlist;
        }
        const std::string p_start = getValuePrefix(args, "--p_start=");
        const std::string sigma_start = getValuePrefix(args, "--sigma_start=");
        if (!p_start.empty()) cfg.p_start = std::stod(p_start);
        if (!sigma_start.empty()) cfg.sigma_start = std::stod(sigma_start);
        const std::string p_end = getValuePrefix(args, "--p_end=");
        const std::string sigma_end = getValuePrefix(args, "--sigma_end=");
        if (!p_end.empty()) cfg.p_end = std::stod(p_end);
        if (!sigma_end.empty()) cfg.sigma_end = std::stod(sigma_end);
        const std::string p_step = getValuePrefix(args, "--p_step=");
        const std::string sigma_step = getValuePrefix(args, "--sigma_step=");
        if (!p_step.empty()) cfg.p_step = std::stod(p_step);
        if (!sigma_step.empty()) cfg.sigma_step = std::stod(sigma_step);
        const std::string trials = getValuePrefix(args, "--trials=");
        if (!trials.empty()) {
            cfg.trials = std::stoi(trials);
            cfg.trials_explicit = true;
        }
        const std::string seed = getValuePrefix(args, "--seed=");
        if (!seed.empty()) cfg.seed = static_cast<uint64_t>(std::stoull(seed));
        std::string out = getValuePrefix(args, "--out=");
        if (out.empty()) out = getValuePrefix(args, "--output=");
        if (!out.empty()) cfg.out_csv = out;
        if (hasFlag(args, "--monotonic_smooth")) cfg.monotonic_smooth = true;
        cfg.weight_mode = weight_mode;
        cfg.mwpm_graph = mwpm_graph;
        if (uf_weighted || weight_mode == "neural" || weight_mode == "llr") cfg.uf_weighted = true;
        cfg.llr_p_data = llr_p_data;
        cfg.llr_p_meas = llr_p_meas;
        cfg.llr_p_idle = llr_p_idle;
        cfg.llr_clamp_min = llr_clamp_min;
        cfg.llr_clamp_max = llr_clamp_max;
        cfg.mwpm_weight_scale = mwpm_weight_scale;
        if (surface_mode == "hybrid") {
            cfg.mode = NoiseMode::Hybrid;
        } else if (surface_mode == "gkp") {
            cfg.mode = NoiseMode::GKP;
        } else {
            cfg.mode = NoiseMode::Pauli;
        }

        cfg.gkp_gate_error = gkp_cfg.gate_error;
        cfg.gkp_meas_error = gkp_cfg.meas_error;
        cfg.gkp_idle_error = gkp_cfg.idle_error;
        cfg.gkp_loss_prob = gkp_cfg.loss_prob;
        cfg.gkp_loss_map = gkp_cfg.loss_map;

        const bool p_sweep_provided = !p_start.empty() || !p_end.empty() || !p_step.empty();
        const bool sigma_sweep_provided = !sigma_start.empty() || !sigma_end.empty() || !sigma_step.empty();
        if (p_sweep_provided && sigma_sweep_provided) {
            std::cerr << "error: cannot provide both p sweep and sigma sweep arguments\n";
            return 1;
        }
        if (cfg.mode == NoiseMode::Hybrid || cfg.mode == NoiseMode::GKP) {
            if (p_sweep_provided) {
                std::cerr << "error: sigma mode does not allow --p_start/--p_end/--p_step\n";
                return 1;
            }
            if (!sigma_sweep_provided && cv_sigma_arg.empty()) {
                std::cerr << "error: sigma mode requires --sigma_start/--sigma_end/--sigma_step "
                          << "(or legacy --cv_sigma for single-point run)\n";
                return 1;
            }
            if (sigma_sweep_provided) {
                cfg.cv_sigma = cfg.sigma_start;
                if (!cv_sigma_arg.empty()) {
                    std::cout << "WARNING: ignoring --cv_sigma because sigma sweep is explicitly set\n";
                }
            } else {
                cfg.cv_sigma = cv_sigma;
                cfg.sigma_start = cfg.cv_sigma;
                cfg.sigma_end = cfg.cv_sigma;
                cfg.sigma_step = 1.0;
            }
        } else {
            cfg.cv_sigma = 0.0;
        }
        const std::string min_trials = getValuePrefix(args, "--min_trials=");
        if (!min_trials.empty()) {
            cfg.min_trials = std::stoi(min_trials);
            adaptive_requested = true;
        }
        const std::string max_trials = getValuePrefix(args, "--max_trials=");
        if (!max_trials.empty()) {
            cfg.max_trials = std::stoi(max_trials);
            adaptive_requested = true;
        }
        const std::string batch_trials = getValuePrefix(args, "--batch_trials=");
        if (!batch_trials.empty()) {
            cfg.batch_trials = std::stoi(batch_trials);
            adaptive_requested = true;
        }
        const std::string target_abs = getValuePrefix(args, "--target_ci_halfwidth=");
        if (!target_abs.empty()) {
            cfg.target_ci_halfwidth = std::stod(target_abs);
            adaptive_requested = true;
        }
        const std::string target_rel = getValuePrefix(args, "--target_rel_ci=");
        if (!target_rel.empty()) {
            cfg.target_rel_ci = std::stod(target_rel);
            adaptive_requested = true;
        }
        const std::string threads = getValuePrefix(args, "--threads=");
        if (!threads.empty()) {
            cfg.threads = std::max(1, std::stoi(threads));
        }
        if (hasFlag(args, "--gpu")) {
            cfg.use_gpu = true;
        }
        if (hasFlag(args, "--auto_threshold")) {
            cfg.auto_threshold = true;
            cfg.estimate_threshold = true; // backward-compatible alias
        }
        if (hasFlag(args, "--estimate_threshold")) cfg.estimate_threshold = true;
        if (hasFlag(args, "--scaling_fit")) cfg.scaling_fit = true;
        const std::string scaling_bootstrap = getValuePrefix(args, "--scaling_bootstrap=");
        if (!scaling_bootstrap.empty()) {
            cfg.scaling_bootstrap = std::max(0, std::stoi(scaling_bootstrap));
        }
        const std::string scaling_seed = getValuePrefix(args, "--scaling_seed=");
        if (!scaling_seed.empty()) {
            cfg.scaling_seed = static_cast<uint64_t>(std::stoull(scaling_seed));
        }
        const std::string pc_min = getValuePrefix(args, "--pc_min=");
        if (!pc_min.empty()) {
            cfg.pc_min = std::stod(pc_min);
            cfg.pc_min_set = true;
        }
        const std::string pc_max = getValuePrefix(args, "--pc_max=");
        if (!pc_max.empty()) {
            cfg.pc_max = std::stod(pc_max);
            cfg.pc_max_set = true;
        }
        const std::string nu_min = getValuePrefix(args, "--nu_min=");
        if (!nu_min.empty()) {
            cfg.nu_min = std::stod(nu_min);
            cfg.nu_min_set = true;
        }
        const std::string nu_max = getValuePrefix(args, "--nu_max=");
        if (!nu_max.empty()) {
            cfg.nu_max = std::stod(nu_max);
            cfg.nu_max_set = true;
        }
        const std::string grid_pc = getValuePrefix(args, "--grid_pc=");
        if (!grid_pc.empty()) {
            cfg.grid_pc = std::max(2, std::stoi(grid_pc));
        }
        const std::string grid_nu = getValuePrefix(args, "--grid_nu=");
        if (!grid_nu.empty()) {
            cfg.grid_nu = std::max(2, std::stoi(grid_nu));
        }
        const std::string ler_smooth_eps = getValuePrefix(args, "--ler_smooth_eps=");
        if (!ler_smooth_eps.empty()) {
            cfg.ler_smooth_eps = std::max(0.0, std::stod(ler_smooth_eps));
        }
        const std::string scaling_report = getValuePrefix(args, "--scaling_report=");
        if (!scaling_report.empty()) {
            cfg.scaling_report = scaling_report;
        }
        const std::string scaling_json = getValuePrefix(args, "--scaling_json=");
        if (!scaling_json.empty()) {
            cfg.scaling_json = scaling_json;
        }
        cfg.adaptive_enabled = adaptive_requested;
        cfg.neural_weights_path = neural_weights_path;
        cfg.neural_model_path = neural_model_path;
        if (!validateNeuralModelRequirement(cfg.decoder_name, cfg.neural_model_path)) {
            return 1;
        }
        return SurfaceThresholdRunner::run(cfg, plugins);
    }

    if (opts.selftest) {
        const bool ok = run_self_tests(makeParams(opts));
        return ok ? 0 : 1;
    }
    if (has_surface_demo_request) {
        if (engine_explicit && engine != QECEngine::Surface) {
            std::cerr << "error: --surface_demo requires --engine=surface\n";
            return 1;
        }
        const std::string mode = surface_demo_mode.empty() ? "stub" : surface_demo_mode;
        return runQecSurfaceDemo(mode, surface_mode, gkp_cfg, demo_sweep, demo_d, demo_trials, demo_seed, demo_distances,
                                 demo_seed_per_distance, demo_sigma_by_d, demo_p_by_d, weight_mode, mwpm_graph, uf_weighted,
                                 neural_weights_path, neural_model_path, llr_p_data, llr_p_meas, llr_p_idle,
                                 llr_clamp_min, llr_clamp_max, mwpm_weight_scale, opts.mode, opts.alpha, plugins);
    }

    if (qec_mode == "css_demo") {
        return runQecCssDemo(opts, args, surface_mode);
    }
    if (qec_mode == "surface_stub") {
        return runQecSurfaceDemo("stub", surface_mode, gkp_cfg, demo_sweep, demo_d, demo_trials, demo_seed, demo_distances,
                                 demo_seed_per_distance, demo_sigma_by_d, demo_p_by_d, weight_mode, mwpm_graph, uf_weighted,
                                 neural_weights_path, neural_model_path, llr_p_data, llr_p_meas, llr_p_idle,
                                 llr_clamp_min, llr_clamp_max, mwpm_weight_scale, opts.mode, opts.alpha, plugins);
    }
    if (qec_mode == "surface_mwpm") {
        return runQecSurfaceDemo("mwpm", surface_mode, gkp_cfg, demo_sweep, demo_d, demo_trials, demo_seed, demo_distances,
                                 demo_seed_per_distance, demo_sigma_by_d, demo_p_by_d, weight_mode, mwpm_graph, uf_weighted,
                                 neural_weights_path, neural_model_path, llr_p_data, llr_p_meas, llr_p_idle,
                                 llr_clamp_min, llr_clamp_max, mwpm_weight_scale, opts.mode, opts.alpha, plugins);
    }
    if (qec_mode == "surface_uf") {
        return runQecSurfaceDemo("uf", surface_mode, gkp_cfg, demo_sweep, demo_d, demo_trials, demo_seed, demo_distances,
                                 demo_seed_per_distance, demo_sigma_by_d, demo_p_by_d, weight_mode, mwpm_graph, uf_weighted,
                                 neural_weights_path, neural_model_path, llr_p_data, llr_p_meas, llr_p_idle,
                                 llr_clamp_min, llr_clamp_max, mwpm_weight_scale, opts.mode, opts.alpha, plugins);
    }
    if (qec_mode == "surface_neural_mwpm") {
        return runQecSurfaceDemo("neural_mwpm", surface_mode, gkp_cfg, demo_sweep, demo_d, demo_trials, demo_seed, demo_distances,
                                 demo_seed_per_distance, demo_sigma_by_d, demo_p_by_d, weight_mode, mwpm_graph, uf_weighted,
                                 neural_weights_path, neural_model_path, llr_p_data, llr_p_meas, llr_p_idle,
                                 llr_clamp_min, llr_clamp_max, mwpm_weight_scale, opts.mode, opts.alpha, plugins);
    }

    if (engine_explicit && engine == QECEngine::CSS) {
        return runQecCssDemo(opts, args, surface_mode);
    }
    if (engine_explicit && engine == QECEngine::Surface) {
        return runQecSurfaceDemo("mwpm", surface_mode, gkp_cfg, demo_sweep, demo_d, demo_trials, demo_seed, demo_distances,
                                 demo_seed_per_distance, demo_sigma_by_d, demo_p_by_d, weight_mode, mwpm_graph, uf_weighted,
                                 neural_weights_path, neural_model_path, llr_p_data, llr_p_meas, llr_p_idle,
                                 llr_clamp_min, llr_clamp_max, mwpm_weight_scale, opts.mode, opts.alpha, plugins);
    }

    std::cout << "LiDMaS+ v0.6\n";
    std::cout << "Usage flags: --bp=nms | --bp=sum-product | --alpha=0.8 | --quiet-iter-log\n";

    const SweepConfig cfg_large{
        .m = 500,
        .n = 1000,
        .col_weight = 3,
        .trials = 200,
        .p_start = 0.01,
        .p_end = 0.10,
        .p_step = 0.01,
        .label = "R1/2-large-SP",
        .csv_file = "ldpc_curve_n1000.csv"
    };

    runSweep(cfg_large, opts);
    return 0;
}
