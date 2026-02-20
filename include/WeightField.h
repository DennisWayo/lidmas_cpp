#pragma once

class WeightField {
public:
    virtual ~WeightField() = default;

    // Return an edge weight for graph edge (u, v).
    virtual double edge_weight(int u, int v) const = 0;
};
