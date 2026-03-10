#pragma once

#include "core/BinaryMatrix.h"
#include "qec/LogicalOperators.h"

class RepetitionCode {
public:
    static BinaryMatrix buildParityCheck(int n);
    static LogicalOperators buildLogicals(int n);
    static void buildCSS(int n, BinaryMatrix* hx, BinaryMatrix* hz, LogicalOperators* logicals);
};
