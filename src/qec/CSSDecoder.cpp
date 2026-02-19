#include "qec/CSSDecoder.h"
#include <stdexcept>

CSSDecoder::CSSDecoder(const BinaryMatrix& hx,
                       const BinaryMatrix& hz,
                       BeliefPropagation::Params x_params,
                       BeliefPropagation::Params z_params)
    : gx_(hx),
      gz_(hz),
      bpx_(gx_, x_params),
      bpz_(gz_, z_params)
{
    if (hx.cols() != hz.cols()) {
        throw std::invalid_argument("CSSDecoder requires HX and HZ with the same number of columns");
    }
}

CSSDecodeResult CSSDecoder::decode(
    const std::vector<int>& sx,
    const std::vector<int>& sz,
    const std::vector<int>& rx,
    const std::vector<int>& rz,
    const std::vector<int>& erasures,
    double px,
    double pz)
{
    if (gx_.nVars() != gz_.nVars()) {
        throw std::runtime_error("Internal CSSDecoder error: X/Z graphs have different variable counts");
    }

    const int n = gx_.nVars();
    if ((int)rx.size() != n || (int)rz.size() != n || (int)erasures.size() != n) {
        throw std::invalid_argument("CSSDecoder decode expects rx/rz/erasures sized to HX/HZ columns");
    }

    CSSDecodeResult out;

    out.ex_hat = bpx_.decode(sx, erasures, px);
    out.ez_hat = bpz_.decode(sz, erasures, pz);

    out.x_corrected.resize(n, 0);
    out.z_corrected.resize(n, 0);
    out.corrected_codeword.resize(2 * n, 0);

    for (int i = 0; i < n; ++i) {
        out.x_corrected[i] = rx[i] ^ out.ex_hat[i];
        out.z_corrected[i] = rz[i] ^ out.ez_hat[i];
        out.corrected_codeword[i] = out.x_corrected[i];
        out.corrected_codeword[n + i] = out.z_corrected[i];
    }

    return out;
}
