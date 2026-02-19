#pragma once
#include <vector>
#include "core/BinaryMatrix.h"

class LDPCGenerator {
public:
    // PEG-style regular LDPC
    static BinaryMatrix generatePEG(
        int m,           // number of checks
        int n,           // number of variables
        int col_weight,  // variable degree
        int seed = 42
    );
};