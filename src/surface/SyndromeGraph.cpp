#include "surface/SyndromeGraph.h"

#include <algorithm>
#include <cstdlib>
#include <stdexcept>

std::vector<LatticeCoord> GetZDefects(const std::vector<int>& syndrome_sz, int d) {
    if (d < 2) {
        throw std::invalid_argument("GetZDefects requires d >= 2");
    }
    const int f = d - 1;
    if (static_cast<int>(syndrome_sz.size()) != f * f) {
        throw std::invalid_argument("GetZDefects syndrome size mismatch");
    }

    std::vector<LatticeCoord> out;
    out.reserve(syndrome_sz.size() / 4 + 1);
    for (int idx = 0; idx < static_cast<int>(syndrome_sz.size()); ++idx) {
        if ((syndrome_sz[idx] & 1) == 0) continue;
        out.push_back(LatticeCoord{idx / f, idx % f});
    }
    return out;
}

std::vector<LatticeCoord> GetXDefects(const std::vector<int>& syndrome_sx, int d) {
    if (d < 1) {
        throw std::invalid_argument("GetXDefects requires d >= 1");
    }
    if (static_cast<int>(syndrome_sx.size()) != d * d) {
        throw std::invalid_argument("GetXDefects syndrome size mismatch");
    }

    std::vector<LatticeCoord> out;
    out.reserve(syndrome_sx.size() / 4 + 1);
    for (int idx = 0; idx < static_cast<int>(syndrome_sx.size()); ++idx) {
        if ((syndrome_sx[idx] & 1) == 0) continue;
        out.push_back(LatticeCoord{idx / d, idx % d});
    }
    return out;
}

SyndromeGraph::SyndromeGraph(int width, int height)
    : width_(width),
      height_(height) {}

int SyndromeGraph::addNode(int x, int y, int t) {
    Node n;
    n.id = static_cast<int>(nodes_.size());
    n.x = x;
    n.y = y;
    n.t = t;
    nodes_.push_back(n);
    return n.id;
}

int SyndromeGraph::size() const {
    return static_cast<int>(nodes_.size());
}

const std::vector<SyndromeGraph::Node>& SyndromeGraph::nodes() const {
    return nodes_;
}

int SyndromeGraph::distance(int i, int j) const {
    if (i < 0 || j < 0 || i >= size() || j >= size()) {
        throw std::out_of_range("SyndromeGraph::distance index out of range");
    }
    const Node& a = nodes_[i];
    const Node& b = nodes_[j];
    return std::abs(a.x - b.x) + std::abs(a.y - b.y) + std::abs(a.t - b.t);
}

int SyndromeGraph::nearestBoundaryDistance(int i) const {
    if (i < 0 || i >= size()) {
        throw std::out_of_range("SyndromeGraph::nearestBoundaryDistance index out of range");
    }

    int width = width_;
    int height = height_;
    if (width <= 0 || height <= 0) {
        for (const Node& n : nodes_) {
            width = std::max(width, n.x + 1);
            height = std::max(height, n.y + 1);
        }
    }
    if (width <= 0 || height <= 0) return 0;

    const Node& n = nodes_[i];
    const int left = n.x;
    const int right = (width - 1) - n.x;
    const int bottom = n.y;
    const int top = (height - 1) - n.y;
    return std::min(std::min(left, right), std::min(bottom, top));
}
