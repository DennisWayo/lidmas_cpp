#include "surface/ScalingAnalysis.h"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <limits>
#include <map>
#include <numeric>
#include <random>
#include <set>
#include <sstream>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

constexpr double kEps = 1e-12;

struct CurveData {
    int d = 0;
    std::vector<double> p;
    std::vector<double> y;
    std::vector<double> lo;
    std::vector<double> hi;
};

double clamp01(double x) {
    if (x < 0.0) return 0.0;
    if (x > 1.0) return 1.0;
    return x;
}

double percentile(std::vector<double> vals, double q) {
    if (vals.empty()) return std::numeric_limits<double>::quiet_NaN();
    q = std::clamp(q, 0.0, 1.0);
    std::sort(vals.begin(), vals.end());
    const double idx = q * static_cast<double>(vals.size() - 1);
    const size_t lo = static_cast<size_t>(std::floor(idx));
    const size_t hi = static_cast<size_t>(std::ceil(idx));
    if (lo == hi) return vals[lo];
    const double t = idx - static_cast<double>(lo);
    return vals[lo] * (1.0 - t) + vals[hi] * t;
}

std::vector<double> isotonic_non_decreasing(const std::vector<double>& y, double eps) {
    if (y.empty()) return {};
    const size_t n = y.size();
    eps = std::max(0.0, eps);

    // Shift trick: enforce z(i)=y(i)-eps*i non-decreasing with exact PAV.
    std::vector<double> z(n, 0.0);
    for (size_t i = 0; i < n; ++i) {
        z[i] = y[i] - eps * static_cast<double>(i);
    }

    std::vector<double> level;
    std::vector<int> count;
    level.reserve(n);
    count.reserve(n);

    for (size_t i = 0; i < n; ++i) {
        level.push_back(z[i]);
        count.push_back(1);
        while (level.size() >= 2) {
            const size_t m = level.size();
            if (level[m - 2] <= level[m - 1]) break;
            const double c1 = static_cast<double>(count[m - 2]);
            const double c2 = static_cast<double>(count[m - 1]);
            const double merged = (level[m - 2] * c1 + level[m - 1] * c2) / (c1 + c2);
            level[m - 2] = merged;
            count[m - 2] += count[m - 1];
            level.pop_back();
            count.pop_back();
        }
    }

    std::vector<double> out;
    out.reserve(n);
    for (size_t b = 0; b < level.size(); ++b) {
        for (int c = 0; c < count[b]; ++c) {
            out.push_back(level[b]);
        }
    }
    if (out.size() != n) return y;

    for (size_t i = 0; i < n; ++i) {
        out[i] += eps * static_cast<double>(i);
        out[i] = clamp01(out[i]);
    }
    // Keep final tolerance guarantee after clamping.
    for (size_t i = 1; i < n; ++i) {
        const double min_allowed = out[i - 1] - eps;
        if (out[i] < min_allowed) out[i] = min_allowed;
        out[i] = clamp01(out[i]);
    }
    return out;
}

std::map<int, CurveData> prepare_curves(const std::vector<SweepPoint>& pts,
                                        bool monotonic_smooth,
                                        double ler_smooth_eps) {
    std::map<int, std::vector<SweepPoint>> grouped;
    for (const auto& pt : pts) {
        if (pt.d <= 0) continue;
        grouped[pt.d].push_back(pt);
    }

    std::map<int, CurveData> curves;
    for (auto& kv : grouped) {
        auto& vec = kv.second;
        std::sort(vec.begin(), vec.end(), [](const SweepPoint& a, const SweepPoint& b) {
            if (a.p != b.p) return a.p < b.p;
            return a.trials > b.trials;
        });

        CurveData c;
        c.d = kv.first;
        c.p.reserve(vec.size());
        c.y.reserve(vec.size());
        c.lo.reserve(vec.size());
        c.hi.reserve(vec.size());

        for (const auto& pt : vec) {
            c.p.push_back(pt.p);
            c.y.push_back(clamp01(pt.ler));
            c.lo.push_back(clamp01(pt.ci_low));
            c.hi.push_back(clamp01(pt.ci_high));
        }

        if (monotonic_smooth) {
            c.y = isotonic_non_decreasing(c.y, ler_smooth_eps);
        }

        curves[c.d] = std::move(c);
    }
    return curves;
}

double interp_linear(const std::vector<double>& xs, const std::vector<double>& ys, double x) {
    if (xs.empty() || ys.empty() || xs.size() != ys.size()) return std::numeric_limits<double>::quiet_NaN();
    if (x <= xs.front()) return ys.front();
    if (x >= xs.back()) return ys.back();
    const auto it = std::upper_bound(xs.begin(), xs.end(), x);
    const size_t hi = static_cast<size_t>(std::distance(xs.begin(), it));
    if (hi == 0) return ys.front();
    const size_t lo = hi - 1;
    const double x0 = xs[lo], x1 = xs[hi];
    const double y0 = ys[lo], y1 = ys[hi];
    const double t = (x - x0) / (x1 - x0);
    return y0 * (1.0 - t) + y1 * t;
}

double curve_value(const CurveData& c, double p) {
    return interp_linear(c.p, c.y, p);
}

double curve_ci_lo(const CurveData& c, double p) {
    return interp_linear(c.p, c.lo, p);
}

double curve_ci_hi(const CurveData& c, double p) {
    return interp_linear(c.p, c.hi, p);
}

std::vector<CrossingEstimate> find_crossings_for_pair(const CurveData& a, const CurveData& b) {
    std::vector<CrossingEstimate> out;
    if (a.p.empty() || b.p.empty()) return out;

    const double lo = std::max(a.p.front(), b.p.front());
    const double hi = std::min(a.p.back(), b.p.back());
    if (!(hi > lo)) return out;

    std::vector<double> knots;
    knots.reserve(a.p.size() + b.p.size() + 2);
    knots.push_back(lo);
    knots.push_back(hi);
    for (double p : a.p) if (p >= lo - kEps && p <= hi + kEps) knots.push_back(p);
    for (double p : b.p) if (p >= lo - kEps && p <= hi + kEps) knots.push_back(p);
    std::sort(knots.begin(), knots.end());
    knots.erase(std::unique(knots.begin(), knots.end(), [](double x, double y) {
        return std::abs(x - y) <= 1e-15;
    }), knots.end());
    if (knots.size() < 2) return out;

    const double span = hi - lo;
    for (size_t i = 0; i + 1 < knots.size(); ++i) {
        const double p0 = knots[i];
        const double p1 = knots[i + 1];
        if (!(p1 > p0)) continue;

        auto diff = [&](double p) { return curve_value(a, p) - curve_value(b, p); };
        double d0 = diff(p0);
        double d1 = diff(p1);

        bool sign_change = (d0 == 0.0) || (d1 == 0.0) || ((d0 > 0.0) != (d1 > 0.0));
        if (!sign_change) continue;

        double left = p0;
        double right = p1;
        double fl = d0;
        double fr = d1;
        if (std::abs(fl) <= 1e-16) right = left;
        else if (std::abs(fr) > 1e-16) {
            for (int it = 0; it < 40; ++it) {
                const double mid = 0.5 * (left + right);
                const double fm = diff(mid);
                if ((fl > 0.0) == (fm > 0.0)) {
                    left = mid;
                    fl = fm;
                } else {
                    right = mid;
                    fr = fm;
                }
            }
        }
        const double pc = 0.5 * (left + right);

        const double a_lo = curve_ci_lo(a, pc);
        const double a_hi = curve_ci_hi(a, pc);
        const double b_lo = curve_ci_lo(b, pc);
        const double b_hi = curve_ci_hi(b, pc);
        const double overlap = std::max(0.0, std::min(a_hi, b_hi) - std::max(a_lo, b_lo));
        const double union_span = std::max(a_hi, b_hi) - std::min(a_lo, b_lo);
        const double overlap_ratio = (union_span > kEps) ? (overlap / union_span) : 0.0;

        const bool interior = (pc > lo + 0.05 * span) && (pc < hi - 0.05 * span);
        const double slope_mag = std::abs(d1 - d0) / std::max(1e-9, p1 - p0);
        double quality = 0.5;
        if (interior) quality += 0.25;
        quality += 0.20 * std::clamp(overlap_ratio, 0.0, 1.0);
        if (slope_mag < 1e-3) quality -= 0.15;
        quality = std::clamp(quality, 0.0, 1.0);

        CrossingEstimate c;
        c.d1 = std::min(a.d, b.d);
        c.d2 = std::max(a.d, b.d);
        c.pc = pc;
        c.pc_low = pc;
        c.pc_high = pc;
        c.quality = quality;
        out.push_back(c);
    }
    return out;
}

std::vector<CrossingEstimate> dedup_best_crossings(std::vector<CrossingEstimate> all) {
    std::map<std::pair<int, int>, CrossingEstimate> best;
    for (const auto& c : all) {
        const auto key = std::make_pair(c.d1, c.d2);
        auto it = best.find(key);
        if (it == best.end() || c.quality > it->second.quality) {
            best[key] = c;
        }
    }
    std::vector<CrossingEstimate> out;
    out.reserve(best.size());
    for (const auto& kv : best) out.push_back(kv.second);
    std::sort(out.begin(), out.end(), [](const CrossingEstimate& a, const CrossingEstimate& b) {
        if (a.d1 != b.d1) return a.d1 < b.d1;
        return a.d2 < b.d2;
    });
    return out;
}

std::vector<SweepPoint> bootstrap_resample_points(const std::vector<SweepPoint>& pts, std::mt19937_64& rng) {
    std::vector<SweepPoint> out = pts;
    for (auto& pt : out) {
        const int n = std::max(1, pt.trials);
        const long long k0 = std::llround(clamp01(pt.ler) * static_cast<double>(n));
        const double p0 = std::clamp(static_cast<double>(k0) / static_cast<double>(n), 0.0, 1.0);
        std::binomial_distribution<int> binom(n, p0);
        const int k = binom(rng);
        pt.ler = static_cast<double>(k) / static_cast<double>(n);
    }
    return out;
}

void bootstrap_crossing_intervals(std::vector<CrossingEstimate>& crossings,
                                  const std::vector<SweepPoint>& pts,
                                  bool monotonic_smooth,
                                  double ler_smooth_eps,
                                  int bootstrap_samples,
                                  uint64_t seed) {
    if (crossings.empty() || bootstrap_samples <= 0) return;
    std::mt19937_64 rng(seed);

    std::map<std::pair<int, int>, std::vector<double>> sampled;
    for (int b = 0; b < bootstrap_samples; ++b) {
        std::vector<SweepPoint> rs = bootstrap_resample_points(pts, rng);
        auto cb = ScalingAnalysis::estimate_crossings(rs, monotonic_smooth, ler_smooth_eps, 1);
        std::map<std::pair<int, int>, CrossingEstimate> by_pair;
        for (const auto& c : cb) {
            by_pair[{c.d1, c.d2}] = c;
        }
        for (const auto& base : crossings) {
            const auto key = std::make_pair(base.d1, base.d2);
            auto it = by_pair.find(key);
            if (it != by_pair.end()) sampled[key].push_back(it->second.pc);
        }
    }

    for (auto& c : crossings) {
        const auto key = std::make_pair(c.d1, c.d2);
        auto it = sampled.find(key);
        if (it == sampled.end() || it->second.size() < 8) {
            c.pc_low = c.pc;
            c.pc_high = c.pc;
            continue;
        }
        c.pc_low = percentile(it->second, 0.025);
        c.pc_high = percentile(it->second, 0.975);
    }
}

double collapse_cost(const std::vector<SweepPoint>& pts, double pc, double nu, int bins) {
    if (pts.empty() || nu <= 0.0 || bins < 2) return std::numeric_limits<double>::infinity();

    std::vector<double> xs;
    xs.reserve(pts.size());
    std::vector<double> ys;
    ys.reserve(pts.size());
    double x_min = std::numeric_limits<double>::infinity();
    double x_max = -std::numeric_limits<double>::infinity();
    for (const auto& pt : pts) {
        if (pt.d <= 0) continue;
        const double x = (pt.p - pc) * std::pow(static_cast<double>(pt.d), 1.0 / nu);
        xs.push_back(x);
        ys.push_back(clamp01(pt.ler));
        x_min = std::min(x_min, x);
        x_max = std::max(x_max, x);
    }
    if (xs.size() < 4 || !(x_max > x_min)) return std::numeric_limits<double>::infinity();

    struct Bin {
        int n = 0;
        double sum = 0.0;
        double sumsq = 0.0;
    };
    std::vector<Bin> acc(static_cast<size_t>(bins));
    for (size_t i = 0; i < xs.size(); ++i) {
        const double pos = (xs[i] - x_min) / (x_max - x_min);
        int bi = static_cast<int>(std::floor(pos * bins));
        if (bi < 0) bi = 0;
        if (bi >= bins) bi = bins - 1;
        Bin& b = acc[static_cast<size_t>(bi)];
        b.n += 1;
        b.sum += ys[i];
        b.sumsq += ys[i] * ys[i];
    }

    double numer = 0.0;
    double denom = 0.0;
    for (const auto& b : acc) {
        if (b.n < 2) continue;
        const double n = static_cast<double>(b.n);
        const double mean = b.sum / n;
        double var = (b.sumsq - n * mean * mean) / std::max(1.0, n - 1.0);
        if (var < 0.0) var = 0.0;
        numer += var * n;
        denom += n;
    }
    if (denom <= 0.0) return std::numeric_limits<double>::infinity();
    return numer / denom;
}

CollapseFitResult fit_single_grid(const std::vector<SweepPoint>& pts,
                                  double pc_init,
                                  double nu_init,
                                  double pc_min,
                                  double pc_max,
                                  double nu_min,
                                  double nu_max,
                                  int grid_pc,
                                  int grid_nu,
                                  bool refine) {
    CollapseFitResult best;
    best.cost = std::numeric_limits<double>::infinity();
    grid_pc = std::max(2, grid_pc);
    grid_nu = std::max(2, grid_nu);
    if (!(pc_max > pc_min) || !(nu_max > nu_min)) return best;

    auto eval = [&](double pc, double nu) {
        return collapse_cost(pts, pc, nu, 30);
    };

    for (int ip = 0; ip < grid_pc; ++ip) {
        const double tpc = static_cast<double>(ip) / static_cast<double>(grid_pc - 1);
        const double pc = pc_min + tpc * (pc_max - pc_min);
        for (int in = 0; in < grid_nu; ++in) {
            const double tnu = static_cast<double>(in) / static_cast<double>(grid_nu - 1);
            const double nu = nu_min + tnu * (nu_max - nu_min);
            const double c = eval(pc, nu);
            if (c < best.cost) {
                best.pc = pc;
                best.nu = nu;
                best.cost = c;
            }
        }
    }

    if (pc_init >= pc_min && pc_init <= pc_max && nu_init >= nu_min && nu_init <= nu_max) {
        const double c0 = eval(pc_init, nu_init);
        if (c0 < best.cost) {
            best.pc = pc_init;
            best.nu = nu_init;
            best.cost = c0;
        }
    }

    if (refine) {
        double dpc = (pc_max - pc_min) / static_cast<double>(grid_pc - 1);
        double dnu = (nu_max - nu_min) / static_cast<double>(grid_nu - 1);
        for (int it = 0; it < 8; ++it) {
            bool improved = false;
            for (int sp : {-1, 0, 1}) {
                for (int sn : {-1, 0, 1}) {
                    if (sp == 0 && sn == 0) continue;
                    const double npc = std::clamp(best.pc + sp * dpc, pc_min, pc_max);
                    const double nnu = std::clamp(best.nu + sn * dnu, nu_min, nu_max);
                    const double c = eval(npc, nnu);
                    if (c + 1e-15 < best.cost) {
                        best.pc = npc;
                        best.nu = nnu;
                        best.cost = c;
                        improved = true;
                    }
                }
            }
            if (!improved) {
                dpc *= 0.5;
                dnu *= 0.5;
            }
            if (dpc < 1e-5 && dnu < 1e-4) break;
        }
    }

    return best;
}

std::pair<double, double> crossing_median_and_ci(const std::vector<CrossingEstimate>& crossings) {
    std::vector<double> pcs;
    std::vector<double> lows;
    std::vector<double> highs;
    for (const auto& c : crossings) {
        if (c.quality < 0.5) continue;
        pcs.push_back(c.pc);
        lows.push_back(c.pc_low);
        highs.push_back(c.pc_high);
    }
    if (pcs.empty()) {
        for (const auto& c : crossings) {
            pcs.push_back(c.pc);
            lows.push_back(c.pc_low);
            highs.push_back(c.pc_high);
        }
    }
    if (pcs.empty()) return {std::numeric_limits<double>::quiet_NaN(),
                             std::numeric_limits<double>::quiet_NaN()};
    const double med = percentile(pcs, 0.5);
    const double lo = percentile(lows, 0.5);
    const double hi = percentile(highs, 0.5);
    (void)hi;
    return {med, lo};
}

std::string make_report_md(const std::vector<SweepPoint>& pts,
                           const std::vector<CrossingEstimate>& crossings,
                           const CollapseFitResult& collapse,
                           bool collapse_valid) {
    std::set<int> dset;
    for (const auto& pt : pts) dset.insert(pt.d);

    std::ostringstream oss;
    oss << "# LiDMaS+ v0.9 Scaling Report\n\n";
    oss << "## Distances\n\n";
    oss << "- d values: ";
    bool first = true;
    for (int d : dset) {
        if (!first) oss << ", ";
        first = false;
        oss << d;
    }
    oss << "\n\n";

    oss << "## Crossing Estimates\n\n";
    if (crossings.empty()) {
        oss << "No valid crossings detected.\n\n";
    } else {
        oss << "| d1 | d2 | p_c | p_c_low | p_c_high | quality |\n";
        oss << "|---:|---:|---:|---:|---:|---:|\n";
        for (const auto& c : crossings) {
            oss << "|" << c.d1
                << "|" << c.d2
                << "|" << std::fixed << std::setprecision(6) << c.pc
                << "|" << c.pc_low
                << "|" << c.pc_high
                << "|" << std::setprecision(3) << c.quality << "|\n";
        }
        std::vector<double> pcs;
        for (const auto& c : crossings) if (c.quality >= 0.5) pcs.push_back(c.pc);
        if (pcs.empty()) for (const auto& c : crossings) pcs.push_back(c.pc);
        if (!pcs.empty()) {
            const double med = percentile(pcs, 0.5);
            const double lo = percentile(pcs, 0.025);
            const double hi = percentile(pcs, 0.975);
            oss << "\nAggregate crossing median p_c = "
                << std::setprecision(6) << med
                << " [" << lo << ", " << hi << "]\n\n";
        }
    }

    oss << "## Collapse Fit\n\n";
    if (!collapse_valid || !std::isfinite(collapse.cost)) {
        oss << "Collapse fit unavailable.\n";
    } else {
        oss << "- Best p_c: " << std::fixed << std::setprecision(6) << collapse.pc
            << " [" << collapse.pc_low << ", " << collapse.pc_high << "]\n";
        oss << "- Best nu: " << collapse.nu
            << " [" << collapse.nu_low << ", " << collapse.nu_high << "]\n";
        oss << "- Collapse cost: " << std::setprecision(8) << collapse.cost << "\n";
        oss << "- Bootstrap samples: " << collapse.bootstrap_samples << "\n";
    }
    return oss.str();
}

std::string make_summary_json(const std::vector<CrossingEstimate>& crossings,
                              const CollapseFitResult& collapse,
                              bool collapse_valid,
                              uint64_t seed) {
    std::ostringstream oss;
    oss << "{\n";
    oss << "  \"seed\": " << seed << ",\n";
    oss << "  \"crossings\": [\n";
    for (size_t i = 0; i < crossings.size(); ++i) {
        const auto& c = crossings[i];
        oss << "    {\"d1\": " << c.d1
            << ", \"d2\": " << c.d2
            << ", \"pc\": " << std::setprecision(12) << c.pc
            << ", \"pc_low\": " << c.pc_low
            << ", \"pc_high\": " << c.pc_high
            << ", \"quality\": " << c.quality
            << "}";
        if (i + 1 < crossings.size()) oss << ",";
        oss << "\n";
    }
    oss << "  ],\n";
    oss << "  \"collapse\": {\n";
    oss << "    \"valid\": " << (collapse_valid ? "true" : "false") << ",\n";
    oss << "    \"pc\": " << collapse.pc << ",\n";
    oss << "    \"nu\": " << collapse.nu << ",\n";
    oss << "    \"cost\": " << collapse.cost << ",\n";
    oss << "    \"pc_low\": " << collapse.pc_low << ",\n";
    oss << "    \"pc_high\": " << collapse.pc_high << ",\n";
    oss << "    \"nu_low\": " << collapse.nu_low << ",\n";
    oss << "    \"nu_high\": " << collapse.nu_high << ",\n";
    oss << "    \"bootstrap_samples\": " << collapse.bootstrap_samples << "\n";
    oss << "  }\n";
    oss << "}\n";
    return oss.str();
}

} // namespace

std::vector<CrossingEstimate>
ScalingAnalysis::estimate_crossings(const std::vector<SweepPoint>& pts,
                                    bool monotonic_smooth,
                                    double ler_smooth_eps,
                                    int min_pairs_required) {
    auto curves = prepare_curves(pts, monotonic_smooth, ler_smooth_eps);
    std::vector<CrossingEstimate> all;
    if (curves.size() < 2) return {};

    std::vector<int> ds;
    ds.reserve(curves.size());
    for (const auto& kv : curves) ds.push_back(kv.first);
    std::sort(ds.begin(), ds.end());

    for (size_t i = 0; i < ds.size(); ++i) {
        for (size_t j = i + 1; j < ds.size(); ++j) {
            const auto& c1 = curves[ds[i]];
            const auto& c2 = curves[ds[j]];
            auto pair_crossings = find_crossings_for_pair(c1, c2);
            all.insert(all.end(), pair_crossings.begin(), pair_crossings.end());
        }
    }

    std::vector<CrossingEstimate> best = dedup_best_crossings(std::move(all));
    if (static_cast<int>(best.size()) < std::max(0, min_pairs_required)) return {};
    return best;
}

CollapseFitResult
ScalingAnalysis::fit_collapse(const std::vector<SweepPoint>& pts,
                              bool monotonic_smooth,
                              double ler_smooth_eps,
                              double pc_init,
                              double nu_init,
                              double pc_min,
                              double pc_max,
                              double nu_min,
                              double nu_max,
                              int grid_pc,
                              int grid_nu,
                              int bootstrap_samples,
                              uint64_t seed) {
    CollapseFitResult out;
    if (pts.empty()) return out;
    std::set<int> dset;
    for (const auto& pt : pts) if (pt.d > 0) dset.insert(pt.d);
    if (dset.size() < 2) {
        out.bootstrap_samples = std::max(0, bootstrap_samples);
        return out;
    }
    auto curves = prepare_curves(pts, monotonic_smooth, ler_smooth_eps);
    std::vector<SweepPoint> use_pts;
    use_pts.reserve(pts.size());
    for (const auto& kv : curves) {
        const auto& c = kv.second;
        for (size_t i = 0; i < c.p.size(); ++i) {
            SweepPoint sp;
            sp.d = c.d;
            sp.p = c.p[i];
            sp.trials = 1;
            sp.ler = c.y[i];
            sp.ci_low = c.lo[i];
            sp.ci_high = c.hi[i];
            use_pts.push_back(sp);
        }
    }

    CollapseFitResult best = fit_single_grid(
        use_pts, pc_init, nu_init, pc_min, pc_max, nu_min, nu_max, grid_pc, grid_nu, true);
    if (!std::isfinite(best.cost)) return out;

    best.bootstrap_samples = std::max(0, bootstrap_samples);
    std::vector<double> pc_samples;
    std::vector<double> nu_samples;
    if (bootstrap_samples > 0) {
        std::mt19937_64 rng(seed);
        for (int b = 0; b < bootstrap_samples; ++b) {
            std::vector<SweepPoint> rs = bootstrap_resample_points(pts, rng);
            auto rs_curves = prepare_curves(rs, monotonic_smooth, ler_smooth_eps);
            std::vector<SweepPoint> rs_pts;
            rs_pts.reserve(rs.size());
            for (const auto& kv : rs_curves) {
                const auto& c = kv.second;
                for (size_t i = 0; i < c.p.size(); ++i) {
                    SweepPoint sp;
                    sp.d = c.d;
                    sp.p = c.p[i];
                    sp.trials = 1;
                    sp.ler = c.y[i];
                    rs_pts.push_back(sp);
                }
            }
            CollapseFitResult fb = fit_single_grid(
                rs_pts, best.pc, best.nu, pc_min, pc_max, nu_min, nu_max, grid_pc, grid_nu, false);
            if (!std::isfinite(fb.cost)) continue;
            pc_samples.push_back(fb.pc);
            nu_samples.push_back(fb.nu);
        }
    }

    if (pc_samples.size() >= 8) {
        best.pc_low = percentile(pc_samples, 0.025);
        best.pc_high = percentile(pc_samples, 0.975);
    } else {
        best.pc_low = best.pc;
        best.pc_high = best.pc;
    }
    if (nu_samples.size() >= 8) {
        best.nu_low = percentile(nu_samples, 0.025);
        best.nu_high = percentile(nu_samples, 0.975);
    } else {
        best.nu_low = best.nu;
        best.nu_high = best.nu;
    }
    return best;
}

ScalingOutputs
ScalingAnalysis::run_all(const std::vector<SweepPoint>& pts,
                         bool do_crossings,
                         bool do_collapse,
                         bool monotonic_smooth,
                         double ler_smooth_eps,
                         int bootstrap_samples,
                         uint64_t seed) {
    ScalingOutputs out;

    if (do_crossings) {
        out.crossings = estimate_crossings(pts, monotonic_smooth, ler_smooth_eps, 1);
        bootstrap_crossing_intervals(
            out.crossings, pts, monotonic_smooth, ler_smooth_eps, bootstrap_samples, seed);
    }

    bool collapse_valid = false;
    if (do_collapse) {
        double p_min = std::numeric_limits<double>::infinity();
        double p_max = -std::numeric_limits<double>::infinity();
        for (const auto& pt : pts) {
            p_min = std::min(p_min, pt.p);
            p_max = std::max(p_max, pt.p);
        }
        if (!(p_max > p_min)) {
            p_min = 0.01;
            p_max = 0.2;
        }
        double pc_init = 0.5 * (p_min + p_max);
        std::vector<double> pcs;
        for (const auto& c : out.crossings) if (c.quality >= 0.5) pcs.push_back(c.pc);
        if (pcs.empty()) for (const auto& c : out.crossings) pcs.push_back(c.pc);
        if (!pcs.empty()) pc_init = percentile(pcs, 0.5);

        out.collapse = fit_collapse(
            pts,
            monotonic_smooth,
            ler_smooth_eps,
            pc_init,
            1.0,
            p_min,
            p_max,
            0.5,
            3.0,
            61,
            51,
            bootstrap_samples,
            seed);
        collapse_valid = std::isfinite(out.collapse.cost);
    }

    out.report_md = make_report_md(pts, out.crossings, out.collapse, collapse_valid);
    out.summary_json = make_summary_json(out.crossings, out.collapse, collapse_valid, seed);
    return out;
}
