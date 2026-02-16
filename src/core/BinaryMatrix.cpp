#include <iostream>
#include <vector>
#include "core/BinaryMatrix.h"
#include "decoders/BeliefPropagation.h"

BinaryMatrix::BinaryMatrix(int rows, int cols) {
    data.resize(rows, std::vector<int>(cols, 0));
}

void BinaryMatrix::set(int row, int col, int value) {
    data[row][col] = value % 2;
}

int BinaryMatrix::get(int row, int col) const {
    return data[row][col];
}

int BinaryMatrix::rows() const {
    return data.size();
}

int BinaryMatrix::cols() const {
    return data[0].size();
}

void BinaryMatrix::print() const {
    for (const auto& row : data) {
        for (int val : row) {
            std::cout << val << " ";
        }
        std::cout << std::endl;
    }
}

std::vector<int> BinaryMatrix::multiply(const std::vector<int>& vec) const {

    std::vector<int> result(rows(), 0);

    for (int i = 0; i < rows(); ++i) {
        int sum = 0;
        for (int j = 0; j < cols(); ++j) {
            sum += data[i][j] * vec[j];
        }
        result[i] = sum % 2;
    }

    return result;
}
