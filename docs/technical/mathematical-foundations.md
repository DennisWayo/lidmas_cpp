# Mathematical Foundations

This page captures the minimum canonical equations used across LiDMaS+ workflows.
For extended derivations, see [LiDMaS+ Math Notes](../lidmas-math-lecture.md).

## Binary Field and Syndrome Map

All parity operations are over \( \mathbb{F}_2 \):

$$
a \oplus b = (a+b)\bmod 2
$$

For parity-check matrix \(H\) and error vector \(e\):

$$
s = H e \bmod 2
$$

Surface-code geometry used in `paper_04` generators:

$$
n = 2d(d-1), \quad m_X = d^2, \quad m_Z = (d-1)^2
$$

## Logical Failure Indicator

With residual error \(e^{res}=e \oplus c\), logical event indicators are evaluated on canonical logical supports:

$$
\mathcal{L} \in \{0,1\}
$$

and aggregated into logical-error statistics across trials.

## Noise Models

Pauli mode:

$$
\Pr(e_{X,i}=1)=p,\quad \Pr(e_{Z,i}=1)=p
$$

GKP displacement-to-bit mapping (simplified):

$$
\Delta q,\Delta p\sim \mathcal{N}(0,\sigma^2), \quad
n_q=\mathrm{round}(\Delta q/\sqrt{\pi}), \quad
n_p=\mathrm{round}(\Delta p/\sqrt{\pi})
$$

with parity extraction from integer bins.

## Statistical Estimators

For \(N\) trials and \(k\) failures:

$$
\widehat{\mathrm{LER}} = \frac{k}{N}
$$

Confidence intervals are computed and exported (Wilson/bootstrap depending on workflow stage).

## Threshold/Scaling Form

Finite-size scaling uses:

$$
x=(p-p_c)d^{1/\nu}
$$

with fit objective over binned variance/collapse quality.
