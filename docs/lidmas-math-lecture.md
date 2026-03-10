# LiDMaS+ Math Notes

This page is the docs-site version of the LiDMaS+ lecture/math derivation, aligned with the current implementation.

Primary source files:

- `math.tex`
- `lecture.tex`

## Lecture objective

LiDMaS+ follows one mathematical chain:

1. Noise model generates physical errors.
2. Parity-check algebra maps errors to syndrome.
3. Decoder solves an optimization/inference problem to produce correction.
4. Residual logical predicate produces Bernoulli trial outcome.
5. Monte Carlo aggregation estimates logical error rate and threshold behavior.

If any link in the chain changes, threshold curves change.

## 1) Binary algebra and surface-code maps

All parity operations are over \( \mathbb{F}_2 = \{0,1\} \), with XOR:

$$
a \oplus b = (a+b)\bmod 2.
$$

For parity-check matrix \(H\) and error vector \(e\):

$$
(He)_i = \sum_j H_{ij}e_j \bmod 2.
$$

For implemented planar surface code (odd distance \(d \ge 3\)):

$$
n = 2d(d-1), \qquad m_X = d^2, \qquad m_Z = (d-1)^2.
$$

With \(H_X, H_Z\), X/Z error sectors \(e_X,e_Z\), and syndromes \(s_X,s_Z\):

$$
s_Z = H_Z e_X \bmod 2, \qquad s_X = H_X e_Z \bmod 2.
$$

## 2) Logical failure variable

Let \(L_X,L_Z\) be canonical logical supports and

$$
\langle a,b \rangle = \sum_i a_i b_i \bmod 2.
$$

After correction \(c\), residual is \(e^{\mathrm{res}} = e \oplus c\).  
LiDMaS+ threshold accounting uses mode-specific logical indicators:

- Pauli/hybrid harness:

$$
\mathcal{L}_{\text{Pauli/hybrid}} =
\mathbf{1}\!\left[
\langle e_X \oplus c_X, L_X \rangle = 1
\;\lor\;
\langle e_X \oplus c_X, L_Z \rangle = 1
\right].
$$

- Native GKP harness:

$$
\mathcal{L}_{\text{GKP}} =
\mathbf{1}\!\left[
\langle e_X \oplus c_X, L_X \rangle = 1
\;\lor\;
\langle e_Z \oplus c_Z, L_Z \rangle = 1
\right].
$$

## 3) Noise models used in threshold runs

### Pauli mode

Independent Bernoulli draws per qubit:

$$
\Pr(e_{X,i}=1)=p, \qquad \Pr(e_{Z,i}=1)=p.
$$

### Hybrid CV-discrete mode

Legacy hybrid mode maps CV disturbances to discrete syndromes, then uses the same decoder/statistics path.

### Native GKP mode

Continuous displacements:

$$
\Delta q,\Delta p \sim \mathcal{N}(0,\sigma^2),
\quad \lambda=\sqrt{\pi}.
$$

Digitization:

$$
n_q=\mathrm{round}(\Delta q/\lambda), \qquad
n_p=\mathrm{round}(\Delta p/\lambda),
\\
x_{\mathrm{flip}}=|n_q|\bmod 2, \qquad
z_{\mathrm{flip}}=|n_p|\bmod 2.
$$

Additional gate/idle/measurement/loss channels are injected before logical evaluation.

## 4) Decoder objectives

### MWPM

Defect-pair base distance:

$$
d_{ij}=|x_i-x_j|+|y_i-y_j|.
$$

Uniform cost \(W_{ij}=d_{ij}\), or weighted:

$$
W_{ij}=\max\{1,\mathrm{round}(\lambda_w\,d_{ij}\,w(i,j))\}.
$$

Solve perfect matching objective:

$$
\min_{M\in\mathcal{M}}\sum_{(u,v)\in M} C_{uv}.
$$

Lift matches to correction \(c\), with syndrome consistency check \(Hc=s\bmod 2\).

### Union-Find + peeling

Operationally:

1. Initialize odd clusters at defects.
2. Grow and merge clusters.
3. Connect unresolved odd clusters to boundaries.
4. Build forest and peel leaves to select correction edges.

### BP (shared CSS/LDPC inference path)

For BSC \(p \in (0,1/2)\):

$$
L_0=\log\frac{1-p}{p}, \qquad
\ell_i^{\mathrm{ch}}=L_0(1-2y_i),
$$

with sum-product or normalized-min-sum check-node updates and posterior hard decisions.

### Neural-guided MWPM weights

Feature vector:

$$
\phi=(|\Delta x|,|\Delta y|,b).
$$

Scale model:

$$
s(\phi)=\mathrm{clip}(\beta_0+\beta_1 m+\beta_2|\Delta x|+\beta_3|\Delta y|+\beta_4 b,\ s_{\min},s_{\max}),
\\
\hat W = W\,s(\phi).
$$

## 5) Monte Carlo estimators and confidence intervals

At one sweep point with \(N\) trials and \(k\) logical failures:

$$
\widehat{\mathrm{LER}} = \frac{k}{N}.
$$

LiDMaS+ reports Wilson 95% interval (\(z=1.9599639845\)):

$$
\mathrm{denom}=1+\frac{z^2}{N},
\quad
\mathrm{center}=\frac{\hat p+z^2/(2N)}{\mathrm{denom}},
\quad
\mathrm{spread}=\frac{z}{\mathrm{denom}}\sqrt{\frac{\hat p(1-\hat p)+z^2/(4N)}{N}}.
$$

$$
\mathrm{CI}_{95\%}=
\left[
\max(0,\mathrm{center}-\mathrm{spread}),
\min(1,\mathrm{center}+\mathrm{spread})
\right].
$$

## 6) Threshold extraction

### Crossing estimates

- Hybrid sigma-grid nearest difference:

$$
\sigma_{\mathrm{cross}} \approx
\arg\min_{\sigma_i}
\left|
\widehat{\mathrm{LER}}_{d_1}(\sigma_i)-\widehat{\mathrm{LER}}_{d_2}(\sigma_i)
\right|.
$$

- Pauli sign-change interpolation:

$$
\Delta(p)=\widehat{\mathrm{LER}}_{d_1}(p)-\widehat{\mathrm{LER}}_{d_2}(p),
\\
p^*=p_k+(p_{k+1}-p_k)\frac{\Delta(p_k)}{\Delta(p_k)-\Delta(p_{k+1})}.
$$

### Finite-size scaling collapse

$$
x=(p-p_c)d^{1/\nu},
$$

with LiDMaS+ bin-variance objective:

$$
\mathcal{C}(p_c,\nu)=
\frac{\sum_b n_b\,\mathrm{Var}(y\mid b)}{\sum_b n_b},
\\
(\hat p_c,\hat\nu)=\arg\min_{p_c,\nu}\mathcal{C}(p_c,\nu).
$$

## 7) End-to-end trial in one line

$$
\text{Noise} \rightarrow \text{Syndrome} \rightarrow \text{Decode} \rightarrow \text{Logical event } \mathcal{L}
\rightarrow \widehat{\mathrm{LER}} \rightarrow \text{Threshold inference}.
$$

## Teaching tip for live demos

When presenting to graduate students, use this sequence:

1. Start from \(H e = s \bmod 2\) and explain parity detection.
2. Show how each decoder defines a surrogate inverse problem.
3. Explain that threshold plots are statistical estimators of logical failure probability, not direct physical constants.
4. End by contrasting Pauli and GKP/hybrid assumptions while keeping the same inference backbone.
