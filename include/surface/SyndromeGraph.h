#pragma once

#include <vector>

struct LatticeCoord {
    int r = 0;
    int c = 0;
};

std::vector<LatticeCoord> GetZDefects(const std::vector<int>& syndrome_sz, int d);
std::vector<LatticeCoord> GetXDefects(const std::vector<int>& syndrome_sx, int d);

class SyndromeGraph {
public:
    struct Node {
        int id = 0;
        int x = 0;
        int y = 0;
        int t = 0;
    };

    SyndromeGraph(int width = 0, int height = 0);

    int addNode(int x, int y, int t = 0);
    int size() const;
    const std::vector<Node>& nodes() const;

    int distance(int i, int j) const;
    int nearestBoundaryDistance(int i) const;

private:
    int width_ = 0;
    int height_ = 0;
    std::vector<Node> nodes_;
};
