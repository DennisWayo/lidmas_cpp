#include "qec/CSSDecoder.h"
#include "qec/LogicalOperators.h"
#include <algorithm>
#include <cassert>
#include <stdexcept>

namespace {

bool paritySatisfied(const BinaryMatrix& H,
                     const std::vector<int>& e,
                     const std::vector<int>& s) {
    if ((int)s.size() != H.rows()) return false;
    const std::vector<int> s_hat = H.multiply(e);
    for (int i = 0; i < H.rows(); ++i) {
        if ((s_hat[i] & 1) != (s[i] & 1))
            return false;
    }
    return true;
}

bool anyOne(const std::vector<int>& bits) {
    return std::any_of(bits.begin(), bits.end(), [](int b) {
        return (b & 1) != 0;
    });
}

} // namespace

CSSDecoder::CSSDecoder(const CSSCode& code,
                       BeliefPropagationParams params)
    : code_(code),
      gx_(code.Hx()),
      gz_(code.Hz()),
      bpx_(gz_, params),
      bpz_(gx_, params)
{
    if (code.Hx().cols() != code.Hz().cols()) {
        throw std::invalid_argument("CSSDecoder requires HX and HZ with the same number of columns");
    }
}

CSSDecodeResult CSSDecoder::decode(const CSSSyndrome& syndrome,
                                   double px,
                                   double pz,
                                   const std::vector<int>& erasures)
{
    if (gx_.nVars() != gz_.nVars()) {
        throw std::runtime_error("Internal CSSDecoder error: X/Z graphs have different variable counts");
    }

    const int n = gx_.nVars();
    if ((int)syndrome.sx.size() != gx_.nChecks() || (int)syndrome.sz.size() != gz_.nChecks()) {
        throw std::invalid_argument("CSSDecoder decode expects sx/sz sized to Hx/Hz rows");
    }

    std::vector<int> erasures_local;
    if (erasures.empty()) {
        erasures_local.assign(n, 0);
    } else {
        if ((int)erasures.size() != n) {
            throw std::invalid_argument("CSSDecoder decode expects erasures sized to code length");
        }
        erasures_local = erasures;
    }

    CSSDecodeResult out;

    // Decode X errors using Hz and sz.
    out.eX = bpx_.decode(syndrome.sz, erasures_local, px);
    out.iters_X = bpx_.lastIterations();
    out.max_iter_hit_X = bpx_.lastHitMaxIters();

    // Decode Z errors using Hx and sx.
    out.eZ = bpz_.decode(syndrome.sx, erasures_local, pz);
    out.iters_Z = bpz_.lastIterations();
    out.max_iter_hit_Z = bpz_.lastHitMaxIters();

    out.parity_sat_X = paritySatisfied(code_.Hz(), out.eX, syndrome.sz);
    out.parity_sat_Z = paritySatisfied(code_.Hx(), out.eZ, syndrome.sx);

    if (code_.hasLogicals()) {
        out.has_logicals = true;
        out.logical_flip_X = ::apply(code_.logicalZ(), out.eX);
        out.logical_flip_Z = ::apply(code_.logicalX(), out.eZ);
        out.logical_fail = anyOne(out.logical_flip_X) || anyOne(out.logical_flip_Z);
    } else {
        out.has_logicals = false;
        out.logical_fail = false;
    }

    return out;
}

#ifdef CSS_SELF_TEST
namespace {

void run_css_self_test() {
    BinaryMatrix Hx(1, 3);
    Hx.set(0, 0, 1);
    Hx.set(0, 1, 1);
    Hx.set(0, 2, 0);

    BinaryMatrix Hz(1, 3);
    Hz.set(0, 0, 1);
    Hz.set(0, 1, 1);
    Hz.set(0, 2, 0);

    CSSCode code(Hx, Hz);
    assert(code.validateCSS());

    BeliefPropagationParams params;
    CSSDecoder decoder(code, params);

    CSSSyndrome s;
    s.sx = {0};
    s.sz = {0};

    CSSDecodeResult out = decoder.decode(s, 0.0, 0.0);
    assert(out.parity_sat_X);
    assert(out.parity_sat_Z);
}

struct CSSSelfTestRunner {
    CSSSelfTestRunner() { run_css_self_test(); }
};

CSSSelfTestRunner css_self_test_runner;

} // namespace
#endif
