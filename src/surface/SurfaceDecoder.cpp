#include "surface/SurfaceDecoder.h"
#include "graph/TannerGraph.h"
#include "qec/LogicalOperators.h"
#include <stdexcept>

namespace {

std::vector<int> xorBinary(const std::vector<int>& a, const std::vector<int>& b) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("xorBinary requires equal-sized vectors");
    }
    std::vector<int> out(a.size(), 0);
    for (size_t i = 0; i < a.size(); ++i) {
        out[i] = (a[i] ^ b[i]) & 1;
    }
    return out;
}

} // namespace

SurfaceDecoder::SurfaceDecoder(BeliefPropagation::Params params)
    : params_(params) {}

SurfaceDecoder::DecodeResult SurfaceDecoder::decode(const SurfaceCode& code,
                                                    const SurfaceSyndrome& s,
                                                    double px,
                                                    double pz) const {
    const int n = code.n();
    if ((int)s.ex.size() != n || (int)s.ez.size() != n) {
        throw std::invalid_argument("SurfaceDecoder expects ex/ez sized to code.n()");
    }
    if ((int)s.sx.size() != code.mx() || (int)s.sz.size() != code.mz()) {
        throw std::invalid_argument("SurfaceDecoder expects sx/sz sized to Hx/Hz rows");
    }

    TannerGraph gx(code.Hx());
    TannerGraph gz(code.Hz());
    BeliefPropagation bpz(gx, params_);  // decode Z errors from sx using Hx.
    BeliefPropagation bpx(gz, params_);  // decode X errors from sz using Hz.

    const std::vector<int> erasures(n, 0);

    DecodeResult out;
    out.cz = bpz.decode(s.sx, erasures, pz);
    out.cx = bpx.decode(s.sz, erasures, px);

    out.itersZ = bpz.lastIterations();
    out.itersX = bpx.lastIterations();
    out.max_iter_hit_Z = bpz.lastHitMaxIters();
    out.max_iter_hit_X = bpx.lastHitMaxIters();

    const std::vector<int> residual_ex = xorBinary(s.ex, out.cx);
    const std::vector<int> residual_ez = xorBinary(s.ez, out.cz);

    out.logicalXFail = (dot_mod2(residual_ex, code.logicalXSupport()) != 0);
    out.logicalZFail = (dot_mod2(residual_ez, code.logicalZSupport()) != 0);
    out.logicalFail = out.logicalXFail || out.logicalZFail;

    return out;
}
