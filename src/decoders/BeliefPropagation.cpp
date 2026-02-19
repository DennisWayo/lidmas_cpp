// ================================
// FILE: src/decoders/BeliefPropagation.cpp
// ================================

#include "decoders/BeliefPropagation.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>

BeliefPropagation::BeliefPropagation(const TannerGraph& graph, Params params)
    : graph_(graph), params_(params) {}

namespace {

double damp(double old_msg, double new_msg, double damping) {
    const double d = std::clamp(damping, 0.0, 0.999999);
    return (1.0 - d) * new_msg + d * old_msg;
}

double clipLlr(double x, double llr_max) {
    return std::clamp(x, -llr_max, llr_max);
}

double computeCheckMessage(
    const TannerGraph& graph,
    const std::vector<std::vector<double>>& v2c,
    int check,
    int var,
    BeliefPropagation::Mode mode,
    double alpha,
    double eps
) {
    const auto& nbrs = graph.checkNeighbors(check);

    if (mode == BeliefPropagation::Mode::SUM_PRODUCT) {
        double prod = 1.0;
        for (int u : nbrs) {
            if (u == var) continue;
            prod *= std::tanh(v2c[check][u] / 2.0);
        }

        prod = std::clamp(prod, -1.0 + eps, 1.0 - eps);
        return 2.0 * std::atanh(prod);
    }

    double sign_prod = 1.0;
    double min_abs = std::numeric_limits<double>::infinity();
    for (int u : nbrs) {
        if (u == var) continue;
        const double msg = v2c[check][u];
        sign_prod *= (msg < 0.0) ? -1.0 : 1.0;
        min_abs = std::min(min_abs, std::abs(msg));
    }

    if (!std::isfinite(min_abs))
        min_abs = 0.0;

    return alpha * sign_prod * min_abs;
}

double fractionSatisfiedChecksForCodeword(const TannerGraph& graph,
                                          const std::vector<int>& codeword) {
    const int m = graph.nChecks();
    if (m == 0) return 1.0;
    int satisfied = 0;
    for (int c = 0; c < m; ++c) {
        int parity = 0;
        for (int v : graph.checkNeighbors(c))
            parity ^= (codeword[v] & 1);
        if (parity == 0) satisfied++;
    }
    return static_cast<double>(satisfied) / m;
}

double fractionSatisfiedChecksForSyndrome(const TannerGraph& graph,
                                          const std::vector<int>& error,
                                          const std::vector<int>& syndrome) {
    const int m = graph.nChecks();
    if (m == 0) return 1.0;
    int satisfied = 0;
    for (int c = 0; c < m; ++c) {
        int parity = 0;
        for (int v : graph.checkNeighbors(c))
            parity ^= (error[v] & 1);
        if (parity == (syndrome[c] & 1)) satisfied++;
    }
    return static_cast<double>(satisfied) / m;
}

void printLlrBreakdown(const TannerGraph& graph,
                       const std::vector<double>& channel_llr,
                       const std::vector<std::vector<double>>& c2v,
                       const std::vector<double>& final_llr,
                       int max_vars_to_print) {
    const int n = graph.nVars();
    const int count = std::clamp(max_vars_to_print, 0, n);
    for (int v = 0; v < count; ++v) {
        double sum_check_msgs = 0.0;
        for (int c : graph.varNeighbors(v))
            sum_check_msgs += c2v[c][v];

        std::cout << "    v=" << v
                  << " channel_llr=" << channel_llr[v]
                  << " sum_check_msgs=" << sum_check_msgs
                  << " final_llr=" << final_llr[v]
                  << "\n";
    }
}

void printEdgeDebug(const TannerGraph& graph,
                    const std::vector<double>& channel_llr,
                    const std::vector<std::vector<double>>& v2c,
                    const std::vector<std::vector<double>>& c2v,
                    int debug_var,
                    bool syndrome_mode) {
    (void)syndrome_mode;
    const int n = graph.nVars();
    if (debug_var < 0 || debug_var >= n) return;
    const auto& neighbors = graph.varNeighbors(debug_var);
    if (neighbors.empty()) return;

    const int debug_check = neighbors.front();
    double total_incoming = 0.0;
    for (int c : neighbors)
        total_incoming += c2v[c][debug_var];

    const double incoming_from_c = c2v[debug_check][debug_var];
    const double outgoing_raw = channel_llr[debug_var] + total_incoming - incoming_from_c;
    const double outgoing_sent = v2c[debug_check][debug_var];

    std::cout << "    edge_debug v=" << debug_var
              << " c=" << debug_check
              << " incoming_from_c=" << incoming_from_c
              << " total_incoming=" << total_incoming
              << " outgoing_to_c_raw=" << outgoing_raw
              << " outgoing_to_c_sent=" << outgoing_sent
              << "\n";
}

} // namespace

BeliefPropagation::DecodeResult BeliefPropagation::decodeFromLLR(
    const std::vector<int>& syndrome,
    const std::vector<double>& channel_llr_input,
    const std::vector<int>& erasures
) {
    const int n = graph_.nVars();
    const int m = graph_.nChecks();

    DecodeResult result;
    result.estimate.assign(n, 0);

    last_iters_ = 0;
    last_hit_max_iters_ = false;
    last_satisfied_check_fractions_.clear();

    if ((int)channel_llr_input.size() != n) return result;
    if ((int)erasures.size() != n) return result;

    const bool syndrome_mode = !syndrome.empty();
    if (syndrome_mode && (int)syndrome.size() != m) return result;

    (void)erasures;

    const double eps = 1e-12;
    const double alpha = std::max(params_.alpha, 0.0);
    const double llr_max = std::max(params_.llr_max, 1.0);
    const std::vector<double> channel_llr = channel_llr_input;

    std::vector<std::vector<double>> v2c(m, std::vector<double>(n, 0.0));
    std::vector<std::vector<double>> c2v(m, std::vector<double>(n, 0.0));

    for (int c = 0; c < m; ++c)
        for (int v : graph_.checkNeighbors(c))
            v2c[c][v] = channel_llr[v];

    std::vector<double> llr_post(n, 0.0);
    std::vector<double> prev_llr_post = channel_llr;

    int iters_done = 0;
    for (int it = 0; it < params_.max_iters; ++it) {
        iters_done = it + 1;

        // ----- Check update -----
        for (int c = 0; c < m; ++c) {
            const auto& nbrs = graph_.checkNeighbors(c);
            for (int v : nbrs) {
                double msg = computeCheckMessage(
                    graph_, v2c, c, v, params_.mode, alpha, eps
                );
                if (syndrome_mode && (syndrome[c] & 1)) msg = -msg;
                msg = clipLlr(msg, llr_max);
                c2v[c][v] = clipLlr(damp(c2v[c][v], msg, params_.damping), llr_max);
            }
        }

        // ----- Variable update -----
        double max_change = 0.0;
        for (int v = 0; v < n; ++v) {
            double sum_check_msgs = 0.0;
            for (int c : graph_.varNeighbors(v))
                sum_check_msgs += c2v[c][v];

            const double final_llr = clipLlr(channel_llr[v] + sum_check_msgs, llr_max);
            llr_post[v] = final_llr;
            max_change = std::max(max_change, std::abs(llr_post[v] - prev_llr_post[v]));

            for (int c : graph_.varNeighbors(v)) {
                const double incoming_from_c = c2v[c][v];
                const double raw_msg = channel_llr[v] + sum_check_msgs - incoming_from_c;
                v2c[c][v] = clipLlr(damp(v2c[c][v], raw_msg, params_.damping), llr_max);
            }
        }

        if (params_.log_edge_debug) {
            printEdgeDebug(graph_, channel_llr, v2c, c2v, params_.edge_debug_var, syndrome_mode);
        }

        if (params_.log_llr_breakdown) {
            printLlrBreakdown(
                graph_, channel_llr, c2v, llr_post, params_.llr_breakdown_vars
            );
        }

        for (int v = 0; v < n; ++v)
            result.estimate[v] = (llr_post[v] < 0.0) ? 1 : 0;

        const double satisfied_fraction = syndrome_mode
            ? fractionSatisfiedChecksForSyndrome(graph_, result.estimate, syndrome)
            : fractionSatisfiedChecksForCodeword(graph_, result.estimate);
        last_satisfied_check_fractions_.push_back(satisfied_fraction);

        if (params_.log_iteration_stats) {
            std::cout << "  iter=" << iters_done
                      << " satisfied_checks=" << satisfied_fraction
                      << "\n";
        }

        bool satisfied = true;
        for (int c = 0; c < m; ++c) {
            int parity = 0;
            for (int v : graph_.checkNeighbors(c))
                parity ^= (result.estimate[v] & 1);

            const int target = syndrome_mode ? (syndrome[c] & 1) : 0;
            if (parity != target) {
                satisfied = false;
                break;
            }
        }

        if (satisfied) {
            last_iters_ = iters_done;
            last_hit_max_iters_ = false;

            result.syndrome_satisfied = true;
            result.hit_max_iters = false;
            result.iterations = last_iters_;
            result.final_satisfied_fraction = satisfied_fraction;
            return result;
        }

        prev_llr_post = llr_post;
        if (max_change < params_.convergence_tol)
            break;
    }

    last_iters_ = iters_done;
    last_hit_max_iters_ = (iters_done >= params_.max_iters);

    result.syndrome_satisfied = false;
    result.hit_max_iters = last_hit_max_iters_;
    result.iterations = last_iters_;
    if (!last_satisfied_check_fractions_.empty())
        result.final_satisfied_fraction = last_satisfied_check_fractions_.back();
    return result;
}

// ============================================================
// (A) Channel decode: thin wrapper (BSC channel model -> BP core)
// ============================================================
std::vector<int> BeliefPropagation::decode(
    const std::vector<int>& syndrome,
    const std::vector<int>& received,
    const std::vector<int>& erasures,
    double p_error
) {
    const int n = graph_.nVars();
    const int m = graph_.nChecks();

    last_iters_ = 0;
    last_hit_max_iters_ = false;
    last_satisfied_check_fractions_.clear();

    if ((int)received.size() != n) return std::vector<int>(n, 0);
    if ((int)erasures.size() != n) return std::vector<int>(n, 0);
    if (!syndrome.empty() && (int)syndrome.size() != m) return std::vector<int>(n, 0);

    const double eps = 1e-12;
    p_error = std::clamp(p_error, eps, 0.5 - eps);
    const double L0 = std::log((1.0 - p_error) / p_error);

    std::vector<double> channel_llr(n, 0.0);
    for (int i = 0; i < n; ++i) {
        // BSC channel model: LLR(y) = log((1-p)/p) * (1 - 2y).
        channel_llr[i] = L0 * (1.0 - 2.0 * received[i]);
        if (erasures[i]) channel_llr[i] = 0.0;
    }

    const std::vector<int> no_syndrome;
    return decodeFromLLR(no_syndrome, channel_llr, erasures).estimate;
}

// ============================================================
// (B) Syndrome-only wrapper: thin wrapper (prior model -> BP core)
// ============================================================
std::vector<int> BeliefPropagation::decode(
    const std::vector<int>& syndrome,
    const std::vector<int>& erasures,
    double p_error
) {
    const int n = graph_.nVars();
    const int m = graph_.nChecks();

    last_iters_ = 0;
    last_hit_max_iters_ = false;
    last_satisfied_check_fractions_.clear();

    if ((int)syndrome.size() != m) return std::vector<int>(n, 0);
    if ((int)erasures.size() != n) return std::vector<int>(n, 0);

    const double eps = 1e-12;
    p_error = std::clamp(p_error, eps, 0.5 - eps);
    const double L0 = std::log((1.0 - p_error) / p_error);

    std::vector<double> channel_llr(n, 0.0);
    for (int i = 0; i < n; ++i)
        channel_llr[i] = erasures[i] ? 0.0 : +L0;

    return decodeFromLLR(syndrome, channel_llr, erasures).estimate;
}
