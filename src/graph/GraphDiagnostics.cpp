#include "graph/GraphDiagnostics.h"
#include "graph/TannerGraph.h"
#include <iostream>
#include <limits>
#include <queue>
#include <vector>

namespace GraphDiagnostics {

DegreeDistribution variableDegreeDistribution(const TannerGraph& graph) {
    DegreeDistribution dist;
    for (int v = 0; v < graph.nVars(); ++v) {
        const int degree = static_cast<int>(graph.varNeighbors(v).size());
        dist[degree]++;
    }
    return dist;
}

DegreeDistribution checkDegreeDistribution(const TannerGraph& graph) {
    DegreeDistribution dist;
    for (int c = 0; c < graph.nChecks(); ++c) {
        const int degree = static_cast<int>(graph.checkNeighbors(c).size());
        dist[degree]++;
    }
    return dist;
}

static inline int toUnifiedCheckIndex(int n_vars, int check) {
    return n_vars + check;
}

static void addNeighbors(const TannerGraph& graph,
                         int node,
                         std::vector<int>& out) {
    out.clear();
    const int n = graph.nVars();
    if (node < n) {
        for (int c : graph.varNeighbors(node))
            out.push_back(toUnifiedCheckIndex(n, c));
    } else {
        const int c = node - n;
        for (int v : graph.checkNeighbors(c))
            out.push_back(v);
    }
}

int estimateGirthBounded(const TannerGraph& graph, int max_cycle_len) {
    if (max_cycle_len < 4) return -1;

    const int n = graph.nVars();
    const int m = graph.nChecks();
    const int total_nodes = n + m;

    if (total_nodes == 0) return -1;

    int best = std::numeric_limits<int>::max();

    std::vector<int> dist(total_nodes, -1);
    std::vector<int> parent(total_nodes, -1);
    std::vector<int> neighbors;

    for (int start = 0; start < total_nodes; ++start) {
        std::fill(dist.begin(), dist.end(), -1);
        std::fill(parent.begin(), parent.end(), -1);

        std::queue<int> q;
        q.push(start);
        dist[start] = 0;

        while (!q.empty()) {
            const int u = q.front();
            q.pop();

            if (dist[u] >= max_cycle_len - 1) continue;

            addNeighbors(graph, u, neighbors);
            for (int v : neighbors) {
                if (dist[v] == -1) {
                    dist[v] = dist[u] + 1;
                    parent[v] = u;
                    q.push(v);
                } else if (parent[u] != v && parent[v] != u) {
                    const int cycle_len = dist[u] + dist[v] + 1;
                    if ((cycle_len % 2) == 0 && cycle_len >= 4 && cycle_len <= max_cycle_len) {
                        best = std::min(best, cycle_len);
                        if (best == 4) return 4;
                    }
                }
            }
        }
    }

    return (best == std::numeric_limits<int>::max()) ? -1 : best;
}

void printDegreeDistribution(const DegreeDistribution& dist,
                             const std::string& label) {
    std::cout << label << " degree distribution:";
    if (dist.empty()) {
        std::cout << " (empty)\n";
        return;
    }

    bool first = true;
    for (const auto& [degree, count] : dist) {
        if (!first) std::cout << ",";
        std::cout << " d=" << degree << "->" << count;
        first = false;
    }
    std::cout << "\n";
}

} // namespace GraphDiagnostics

