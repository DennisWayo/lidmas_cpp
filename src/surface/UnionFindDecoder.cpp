#include "surface/UnionFindDecoder.h"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <deque>
#include <limits>
#include <numeric>
#include <queue>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

namespace {

struct UFDSU {
    std::vector<int> parent;
    std::vector<int> sz;
    std::vector<int> parity;
    std::vector<char> touches_boundary;

    explicit UFDSU(int n)
        : parent(n),
          sz(n, 1),
          parity(n, 0),
          touches_boundary(n, 0) {
        std::iota(parent.begin(), parent.end(), 0);
    }

    int find(int x) {
        while (parent[x] != x) {
            parent[x] = parent[parent[x]];
            x = parent[x];
        }
        return x;
    }

    int unite(int a, int b) {
        a = find(a);
        b = find(b);
        if (a == b) return a;
        if (sz[a] < sz[b]) std::swap(a, b);
        parent[b] = a;
        sz[a] += sz[b];
        parity[a] ^= parity[b];
        touches_boundary[a] = static_cast<char>(touches_boundary[a] || touches_boundary[b]);
        return a;
    }
};

struct ErasureEdge {
    int u = -1;
    int v = -1;
    bool boundary = false;
    int boundary_side = -1;  // 0=left,1=right,2=bottom,3=top
};

uint64_t regularEdgeKey(int u, int v) {
    if (u > v) std::swap(u, v);
    return (static_cast<uint64_t>(u) << 32) | static_cast<uint32_t>(v);
}

uint64_t boundaryEdgeKey(int v, int side) {
    return (1ULL << 63) | (static_cast<uint64_t>(v) << 8) | static_cast<uint64_t>(side & 0xFF);
}

int argmin4(int a, int b, int c, int d) {
    int idx = 0;
    int best = a;
    if (b < best) {
        best = b;
        idx = 1;
    }
    if (c < best) {
        best = c;
        idx = 2;
    }
    if (d < best) {
        idx = 3;
    }
    return idx;
}

} // namespace

UnionFindDecoder::UnionFindDecoder(const SurfaceCode& code)
    : code_(code),
      d_(code.lattice().distance()) {}

std::vector<int> UnionFindDecoder::decode(const SurfaceSyndrome& syn) {
    std::vector<int> corr(code_.n(), 0);

    if (!syn.sz.empty()) {
        const std::vector<int> part = decodeSyndromeUF(syn.sz, true);
        for (int i = 0; i < code_.n(); ++i) corr[i] ^= (part[i] & 1);
    }
    if (!syn.sx.empty()) {
        const std::vector<int> part = decodeSyndromeUF(syn.sx, false);
        for (int i = 0; i < code_.n(); ++i) corr[i] ^= (part[i] & 1);
    }

    return corr;
}

int UnionFindDecoder::hIndex(int x, int y) const {
    if (x < 0 || x >= d_ - 1 || y < 0 || y >= d_) {
        throw std::out_of_range("UnionFindDecoder::hIndex out of range");
    }
    return y * (d_ - 1) + x;
}

int UnionFindDecoder::vIndex(int x, int y) const {
    if (x < 0 || x >= d_ || y < 0 || y >= d_ - 1) {
        throw std::out_of_range("UnionFindDecoder::vIndex out of range");
    }
    const int h_count = d_ * (d_ - 1);
    return h_count + y * d_ + x;
}

void UnionFindDecoder::toggleH(int x, int y, std::vector<int>& corr) const {
    corr[hIndex(x, y)] ^= 1;
}

void UnionFindDecoder::toggleV(int x, int y, std::vector<int>& corr) const {
    corr[vIndex(x, y)] ^= 1;
}

std::vector<int> UnionFindDecoder::decodeSyndromeUF(const std::vector<int>& syndrome,
                                                    bool plaquette_mode) const {
    const int width = plaquette_mode ? (d_ - 1) : d_;
    const int height = plaquette_mode ? (d_ - 1) : d_;
    const int num_vertices = width * height;
    const int boundary_node = num_vertices;

    if (width <= 0 || height <= 0) {
        throw std::invalid_argument("UnionFindDecoder invalid lattice dimensions");
    }
    if (static_cast<int>(syndrome.size()) != num_vertices) {
        throw std::invalid_argument("UnionFindDecoder syndrome size mismatch");
    }

    auto vertexId = [width](int x, int y) { return y * width + x; };
    auto xOf = [width](int v) { return v % width; };
    auto yOf = [width](int v) { return v / width; };
    auto isBoundaryVertex = [width, height](int x, int y) {
        return x == 0 || y == 0 || x == width - 1 || y == height - 1;
    };
    auto nearestBoundarySide = [plaquette_mode, width, height](int x, int y) {
        if (plaquette_mode) {
            const int left = x + 1;
            const int right = width - x;
            const int bottom = y + 1;
            const int top = height - y;
            return argmin4(left, right, bottom, top);
        }
        const int left = x;
        const int right = (width - 1) - x;
        const int bottom = y;
        const int top = (height - 1) - y;
        return argmin4(left, right, bottom, top);
    };

    std::vector<Defect> defects;
    defects.reserve(syndrome.size());
    for (int r = 0; r < static_cast<int>(syndrome.size()); ++r) {
        if ((syndrome[r] & 1) == 0) continue;
        Defect d;
        d.id = static_cast<int>(defects.size());
        d.x = r % width;
        d.y = r / width;
        d.vertex = r;
        d.boundary_flag = isBoundaryVertex(d.x, d.y);
        defects.push_back(d);
    }

    std::vector<int> corr(code_.n(), 0);
    if (defects.empty()) return corr;

    UFDSU clusters(static_cast<int>(defects.size()) + 1);
    const int boundary_cluster = static_cast<int>(defects.size());
    clusters.parity[boundary_cluster] = 0;
    clusters.touches_boundary[boundary_cluster] = 1;

    std::vector<int> owner(num_vertices, -1);        // vertex -> initial defect id
    std::vector<int> parent_vertex(num_vertices, -1); // BFS tree parent per claimed vertex
    std::queue<int> frontier;

    std::vector<ErasureEdge> erasure_edges;
    std::unordered_map<uint64_t, int> edge_index;
    std::unordered_map<uint64_t, int> claimed_edge_owner;

    auto addRegularEdge = [&](int u, int v) {
        if (u == v) return;
        const uint64_t key = regularEdgeKey(u, v);
        if (edge_index.find(key) != edge_index.end()) return;
        edge_index[key] = static_cast<int>(erasure_edges.size());
        erasure_edges.push_back(ErasureEdge{u, v, false, -1});
    };

    auto addBoundaryEdge = [&](int v, int side) {
        const uint64_t key = boundaryEdgeKey(v, side);
        if (edge_index.find(key) != edge_index.end()) return;
        edge_index[key] = static_cast<int>(erasure_edges.size());
        erasure_edges.push_back(ErasureEdge{v, boundary_node, true, side});
    };

    auto addPathToSource = [&](int v) {
        while (v >= 0 && parent_vertex[v] != -1) {
            addRegularEdge(v, parent_vertex[v]);
            v = parent_vertex[v];
        }
    };

    auto unionClustersViaCollision = [&](int owner_a, int va, int owner_b, int vb) {
        int ra = clusters.find(owner_a);
        int rb = clusters.find(owner_b);
        if (ra == rb) return;
        addPathToSource(va);
        addPathToSource(vb);
        addRegularEdge(va, vb);
        clusters.unite(ra, rb);
    };

    // Initialize one cluster per defect (odd parity), with boundary touch metadata.
    for (int i = 0; i < static_cast<int>(defects.size()); ++i) {
        clusters.parity[i] = 1;
        // Keep boundary neutralization deferred to post-growth fallback.
        // This avoids degenerate "one boundary edge per defect" recoveries.
        clusters.touches_boundary[i] = 0;

        const int src = defects[i].vertex;
        if (owner[src] == -1) {
            owner[src] = i;
            frontier.push(src);
        }

    }

    // Union-find growth over lattice edges.
    // Queue entries are implicit (owned frontier vertex + outgoing edge expansion).
    while (!frontier.empty()) {
        const int v = frontier.front();
        frontier.pop();

        const int own = owner[v];
        if (own < 0) continue;

        const int r = clusters.find(own);
        const bool active_odd = ((clusters.parity[r] & 1) != 0) && !clusters.touches_boundary[r];
        if (!active_odd) continue;

        const int vx = xOf(v);
        const int vy = yOf(v);
        const int dx[4] = {1, -1, 0, 0};
        const int dy[4] = {0, 0, 1, -1};
        for (int k = 0; k < 4; ++k) {
            const int nx = vx + dx[k];
            const int ny = vy + dy[k];
            if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
            const int u = vertexId(nx, ny);

            const uint64_t ek = regularEdgeKey(v, u);
            auto ce = claimed_edge_owner.find(ek);
            if (ce == claimed_edge_owner.end()) {
                claimed_edge_owner[ek] = own;
            } else if (ce->second != own) {
                unionClustersViaCollision(own, v, ce->second, u);
            }

            if (owner[u] == -1) {
                owner[u] = own;
                parent_vertex[u] = v;
                frontier.push(u);
            } else if (owner[u] != own) {
                unionClustersViaCollision(own, v, owner[u], u);
            }
        }
    }

    // Safety fallback: if any odd cluster remains unneutralized, connect one representative to boundary.
    std::unordered_set<int> processed_roots;
    for (int i = 0; i < static_cast<int>(defects.size()); ++i) {
        const int root = clusters.find(i);
        if (!processed_roots.insert(root).second) continue;
        const bool active_odd = ((clusters.parity[root] & 1) != 0) && !clusters.touches_boundary[root];
        if (!active_odd) continue;

        int x = defects[i].x;
        int y = defects[i].y;
        int v = defects[i].vertex;
        const int side = nearestBoundarySide(x, y);
        if (side == 0) {
            while (x > 0) {
                const int u = vertexId(x - 1, y);
                addRegularEdge(v, u);
                v = u;
                --x;
            }
        } else if (side == 1) {
            while (x < width - 1) {
                const int u = vertexId(x + 1, y);
                addRegularEdge(v, u);
                v = u;
                ++x;
            }
        } else if (side == 2) {
            while (y > 0) {
                const int u = vertexId(x, y - 1);
                addRegularEdge(v, u);
                v = u;
                --y;
            }
        } else {
            while (y < height - 1) {
                const int u = vertexId(x, y + 1);
                addRegularEdge(v, u);
                v = u;
                ++y;
            }
        }
        addBoundaryEdge(v, side);
        clusters.unite(root, boundary_cluster);
    }

    // Build a forest from erasure edges for peeling.
    UFDSU forest(num_vertices + 1);
    std::vector<ErasureEdge> forest_edges;
    forest_edges.reserve(erasure_edges.size());
    for (const auto& e : erasure_edges) {
        if (forest.find(e.u) != forest.find(e.v)) {
            forest.unite(e.u, e.v);
            forest_edges.push_back(e);
        }
    }

    // Leaf peeling to select correction edges.
    const int node_count = num_vertices + 1;
    std::vector<int> node_parity(node_count, 0);
    for (const auto& d : defects) {
        node_parity[d.vertex] ^= 1;
    }

    std::vector<std::vector<int>> adj(node_count);
    for (int ei = 0; ei < static_cast<int>(forest_edges.size()); ++ei) {
        adj[forest_edges[ei].u].push_back(ei);
        adj[forest_edges[ei].v].push_back(ei);
    }

    std::vector<int> degree(node_count, 0);
    for (int v = 0; v < node_count; ++v) degree[v] = static_cast<int>(adj[v].size());
    std::vector<char> removed(forest_edges.size(), 0);
    std::vector<char> selected(forest_edges.size(), 0);

    std::deque<int> leaves;
    for (int v = 0; v < node_count; ++v) {
        if (v == boundary_node) continue;
        if (degree[v] <= 1) leaves.push_back(v);
    }

    while (!leaves.empty()) {
        const int v = leaves.front();
        leaves.pop_front();

        if (degree[v] == 0) continue;
        int eidx = -1;
        for (int ei : adj[v]) {
            if (!removed[ei]) {
                eidx = ei;
                break;
            }
        }
        if (eidx < 0) {
            degree[v] = 0;
            continue;
        }

        const int u = (forest_edges[eidx].u == v) ? forest_edges[eidx].v : forest_edges[eidx].u;
        if ((node_parity[v] & 1) != 0) {
            selected[eidx] = 1;
            node_parity[u] ^= 1;
        }

        removed[eidx] = 1;
        degree[v]--;
        degree[u]--;
        if (u != boundary_node && degree[u] == 1) {
            leaves.push_back(u);
        }
    }

    // Convert selected erasure edges into data-qubit corrections.
    for (int ei = 0; ei < static_cast<int>(forest_edges.size()); ++ei) {
        if (!selected[ei]) continue;
        const ErasureEdge& e = forest_edges[ei];

        if (e.boundary) {
            if (!plaquette_mode) {
                // For star syndrome, boundary termination is represented by no extra edge.
                continue;
            }
            const int x = xOf(e.u);
            const int y = yOf(e.u);
            switch (e.boundary_side) {
                case 0: toggleV(0, y, corr); break;        // left
                case 1: toggleV(width, y, corr); break;    // right
                case 2: toggleH(x, 0, corr); break;        // bottom
                default: toggleH(x, height, corr); break;  // top
            }
            continue;
        }

        const int x1 = xOf(e.u);
        const int y1 = yOf(e.u);
        const int x2 = xOf(e.v);
        const int y2 = yOf(e.v);

        if (std::abs(x1 - x2) + std::abs(y1 - y2) != 1) {
            continue;
        }

        if (x1 != x2) {
            if (plaquette_mode) {
                toggleV(std::max(x1, x2), y1, corr);
            } else {
                toggleH(std::min(x1, x2), y1, corr);
            }
        } else {
            if (plaquette_mode) {
                toggleH(x1, std::max(y1, y2), corr);
            } else {
                toggleV(x1, std::min(y1, y2), corr);
            }
        }
    }

#ifndef NDEBUG
    const BinaryMatrix& H = plaquette_mode ? code_.Hz() : code_.Hx();
    if (!syndromeMatches(H, corr, syndrome)) {
        throw std::runtime_error("UnionFindDecoder UF+peeling sanity check failed");
    }
#endif

    return corr;
}

bool UnionFindDecoder::syndromeMatches(const BinaryMatrix& H,
                                       const std::vector<int>& corr,
                                       const std::vector<int>& target) const {
    if (target.empty()) return true;
    std::vector<int> syn = H.multiply(corr);
    if (syn.size() != target.size()) return false;
    for (size_t i = 0; i < syn.size(); ++i) {
        if ((syn[i] & 1) != (target[i] & 1)) return false;
    }
    return true;
}
