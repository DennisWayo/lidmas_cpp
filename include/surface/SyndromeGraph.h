#pragma once

#include <vector>

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
