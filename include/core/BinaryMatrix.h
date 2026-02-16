#pragma once

#include <vector>
#include <iostream>

class BinaryMatrix {

private:
    std::vector<std::vector<int>> data;

public:
    BinaryMatrix(int rows, int cols);

    void set(int row, int col, int value);
    int get(int row, int col) const;

    int rows() const;
    int cols() const;

    std::vector<int> multiply(const std::vector<int>& vec) const;

    void print() const;
};