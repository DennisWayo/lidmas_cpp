#pragma once

#include <string>
#include <vector>
#include "core/BinaryMatrix.h"

bool loadBinaryMatrixFromFile(const std::string& path,
                              BinaryMatrix* out,
                              std::string* error);

bool loadBinaryVectorFromFile(const std::string& path,
                              std::vector<int>* out,
                              std::string* error);

bool loadDoubleVectorFromFile(const std::string& path,
                              std::vector<double>* out,
                              std::string* error);
