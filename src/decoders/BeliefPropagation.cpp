#include "decoders/BeliefPropagation.h"
#include <cmath>
#include <limits>
#include <iostream>

double BeliefPropagation::clamp(double x, double lo, double hi) {
    if (x < lo) return lo;
    if (x > hi) return hi;
    return x;
}

BeliefPropagation::BeliefPropagation(
    const BinaryMatrix& H,
    int max_iters,
    double damping
) : H_(H),
    max_iters_(max_iters),
    damping_(damping)
{
    buildGraph_();
}

void BeliefPropagation::buildGraph_() {
    int m = H_.rows();
    int n = H_.cols();

    check_to_var_.assign(m, {});
    var_to_check_.assign(n, {});

    for (int i = 0; i < m; ++i) {
        for (int j = 0; j < n; ++j) {
            if (H_.get(i, j) == 1) {
                check_to_var_[i].push_back(j);
                var_to_check_[j].push_back(i);
            }
        }
    }
}

std::vector<int> BeliefPropagation::decodeErasureAware(
    const std::vector<int>& syndrome,
    const std::vector<int>& erasures,
    double p_error
) {
    const int m = H_.rows();
    const int n = H_.cols();

    if ((int)syndrome.size() != m) {
        throw std::runtime_error("Syndrome size != number of checks (rows of H).");
    }
    if ((int)erasures.size() != n) {
        throw std::runtime_error("Erasures size != number of variables (cols of H).");
    }
    if (!(p_error > 0.0 && p_error < 0.5)) {
        throw std::runtime_error("p_error must be in (0, 0.5) for meaningful LLR.");
    }

    // ---- 1) Channel priors (LLRs) ----
    // non-erased: strong bias toward e_i = 0
    // erased: no bias
    std::vector<double> llr0(n, 0.0);
    const double base_llr = std::log((1.0 - p_error) / p_error);
    for (int j = 0; j < n; ++j) {
        llr0[j] = (erasures[j] == 1) ? 0.0 : base_llr;
    }

    // ---- 2) Messages: var->check and check->var ----
    // store only on edges; easiest is full (m x n) but sparse is better.
    // For simplicity, full matrices (works for small demos)
    std::vector<std::vector<double>> v2c(m, std::vector<double>(n, 0.0));
    std::vector<std::vector<double>> c2v(m, std::vector<double>(n, 0.0));

    // init v->c with channel llr
    for (int i = 0; i < m; ++i) {
        for (int v : check_to_var_[i]) {
            v2c[i][v] = llr0[v];
        }
    }

    // helper: hard decision + syndrome check
    auto hard_decision = [&](const std::vector<double>& post_llr) {
        std::vector<int> e_hat(n, 0);
        for (int j = 0; j < n; ++j) e_hat[j] = (post_llr[j] < 0.0) ? 1 : 0;
        return e_hat;
    };

    auto syndrome_of = [&](const std::vector<int>& e) {
        return H_.multiply(e);  // mod2 multiply in your BinaryMatrix
    };

    // ---- 3) Iterations ----
    for (int it = 0; it < max_iters_; ++it) {
        last_iters_ = it + 1;

        // Check node update (min-sum with syndrome constraint)
        for (int i = 0; i < m; ++i) {
            const auto& nbrs = check_to_var_[i];

            for (int v : nbrs) {
                double min_abs = std::numeric_limits<double>::infinity();
                double sign_prod = 1.0;

                // compute product sign and min abs excluding v
                for (int u : nbrs) {
                    if (u == v) continue;
                    double msg = v2c[i][u];
                    sign_prod *= (msg >= 0.0) ? 1.0 : -1.0;
                    min_abs = std::min(min_abs, std::abs(msg));
                }

                // syndrome bit flips the parity constraint -> flips sign
                // if syndrome[i] == 1, multiply by -1
                double sgn = sign_prod * ((syndrome[i] == 1) ? -1.0 : 1.0);
                c2v[i][v] = sgn * min_abs;
            }
        }

        // Variable node update
        std::vector<double> post_llr(n, 0.0);

        for (int j = 0; j < n; ++j) {
            double sum = llr0[j];
            for (int ci : var_to_check_[j]) {
                sum += c2v[ci][j];
            }
            post_llr[j] = sum;

            // update outgoing v->c for each neighboring check
            for (int ci : var_to_check_[j]) {
                double out = llr0[j];
                for (int ck : var_to_check_[j]) {
                    if (ck == ci) continue;
                    out += c2v[ck][j];
                }
                v2c[ci][j] = clamp(out, -50.0, 50.0);
            }
        }

        // early stop if syndrome satisfied
        auto e_hat = hard_decision(post_llr);
        auto s_hat = syndrome_of(e_hat);
        if (s_hat == syndrome) {
            return e_hat;
        }
    }

    std::cout << "Max iterations reached\n";

    // final hard decision
    std::vector<double> final_llr(n, 0.0);
    for (int j = 0; j < n; ++j) {
        double sum = llr0[j];
        for (int ci : var_to_check_[j]) sum += c2v[ci][j];
        final_llr[j] = sum;
    }
    return hard_decision(final_llr);
}