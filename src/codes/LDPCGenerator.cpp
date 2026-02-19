#include "codes/LDPCGenerator.h"
#include <random>
#include <queue>
#include <limits>
#include <tuple>
#include <stdexcept>
#include "core/BinaryMatrix.h"

namespace {

int pickMinDegreeCheck(const std::vector<int>& candidates,
                       const std::vector<int>& check_degree,
                       std::mt19937& rng) {
    if (candidates.empty()) return -1;

    int min_degree = std::numeric_limits<int>::max();
    for (int c : candidates)
        min_degree = std::min(min_degree, check_degree[c]);

    std::vector<int> tied;
    tied.reserve(candidates.size());
    for (int c : candidates) {
        if (check_degree[c] == min_degree)
            tied.push_back(c);
    }

    if (tied.size() == 1) return tied[0];
    std::uniform_int_distribution<int> dist(0, static_cast<int>(tied.size()) - 1);
    return tied[dist(rng)];
}

struct BfsCheckInfo {
    std::vector<char> reached_checks;
    std::vector<int> check_distance;
};

BfsCheckInfo bfsFromVariable(
    int root_var,
    int max_depth,
    const std::vector<std::vector<int>>& var_to_checks,
    const std::vector<std::vector<int>>& check_to_vars
) {
    const int n = static_cast<int>(var_to_checks.size());
    const int m = static_cast<int>(check_to_vars.size());

    std::vector<char> visited_vars(n, 0);
    std::vector<char> visited_checks(m, 0);
    std::vector<int> check_dist(m, -1);

    // node tuple: (is_check_node, node_index, depth)
    std::queue<std::tuple<bool, int, int>> q;
    q.emplace(false, root_var, 0);
    visited_vars[root_var] = 1;

    while (!q.empty()) {
        auto [is_check, idx, depth] = q.front();
        q.pop();

        if (depth >= max_depth) continue;

        if (!is_check) {
            for (int c : var_to_checks[idx]) {
                if (visited_checks[c]) continue;
                visited_checks[c] = 1;
                check_dist[c] = depth + 1;
                q.emplace(true, c, depth + 1);
            }
        } else {
            for (int v : check_to_vars[idx]) {
                if (visited_vars[v]) continue;
                visited_vars[v] = 1;
                q.emplace(false, v, depth + 1);
            }
        }
    }

    return {std::move(visited_checks), std::move(check_dist)};
}

} // namespace

BinaryMatrix LDPCGenerator::generatePEG(
    int m,
    int n,
    int col_weight,
    int seed)
{
    if (m <= 0 || n <= 0) {
        throw std::invalid_argument("generatePEG requires m>0 and n>0");
    }
    if (col_weight <= 0 || col_weight > m) {
        throw std::invalid_argument("generatePEG requires 0 < col_weight <= m");
    }

    BinaryMatrix H(m, n);

    std::mt19937 rng(seed);

    std::vector<int> check_degree(m, 0);
    std::vector<std::vector<int>> var_to_checks(n);
    std::vector<std::vector<int>> check_to_vars(m);

    // BFS depth limit for local girth-aware PEG edge placement.
    const int max_bfs_depth = 6;

    for (int v = 0; v < n; ++v) {

        for (int edge = 0; edge < col_weight; ++edge) {

            std::vector<char> already_connected(m, 0);
            for (int c : var_to_checks[v])
                already_connected[c] = 1;

            int best_check = -1;

            if (edge == 0) {
                std::vector<int> candidates;
                candidates.reserve(m);
                for (int c = 0; c < m; ++c) {
                    if (!already_connected[c]) candidates.push_back(c);
                }
                best_check = pickMinDegreeCheck(candidates, check_degree, rng);
            } else {
                const auto bfs = bfsFromVariable(v, max_bfs_depth, var_to_checks, check_to_vars);

                // Prefer checks outside the BFS-expanded neighborhood
                // to avoid creating short cycles.
                std::vector<int> outside_tree;
                outside_tree.reserve(m);
                for (int c = 0; c < m; ++c) {
                    if (already_connected[c]) continue;
                    if (!bfs.reached_checks[c]) outside_tree.push_back(c);
                }

                if (!outside_tree.empty()) {
                    best_check = pickMinDegreeCheck(outside_tree, check_degree, rng);
                } else {
                    // If all checks are reachable, pick among the farthest checks
                    // (local girth maximization), then break ties by min degree.
                    int farthest = -1;
                    for (int c = 0; c < m; ++c) {
                        if (already_connected[c]) continue;
                        farthest = std::max(farthest, bfs.check_distance[c]);
                    }

                    std::vector<int> farthest_checks;
                    farthest_checks.reserve(m);
                    for (int c = 0; c < m; ++c) {
                        if (already_connected[c]) continue;
                        if (bfs.check_distance[c] == farthest)
                            farthest_checks.push_back(c);
                    }

                    best_check = pickMinDegreeCheck(farthest_checks, check_degree, rng);
                }
            }

            if (best_check < 0) {
                throw std::runtime_error("PEG construction failed to place an edge");
            }

            H.set(best_check, v, 1);
            check_degree[best_check]++;
            var_to_checks[v].push_back(best_check);
            check_to_vars[best_check].push_back(v);
        }
    }

    return H;
}
