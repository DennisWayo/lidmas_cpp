#pragma once

#include "core/BinaryMatrix.h"
#include "qec/LogicalOperators.h"

class ShorCode {
public:
    static void buildCSS(BinaryMatrix* hx, BinaryMatrix* hz, LogicalOperators* logicals);
};
