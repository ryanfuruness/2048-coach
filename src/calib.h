// Calibrated odds from the engine's values (model fitted by scripts/fit_calib.py on positions whose future the engine
// played): for target tile T, logit P(reach T) = a_T(s) + b_T(s) * u with s = log2(tile sum), u = value / vbar(s) - 1,
// a, b, vbar piecewise linear in s; calibrated expected future points = ratio(s) * value.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <map>
#include <sstream>
#include <string>
#include <vector>

struct Calib {
  static constexpr double kUClip = 0.3;  // the value's relative deviation is clipped to +-0.3 (fit_calib.py UCLIP)
  std::vector<double> knots, vbar, ratio;
  int umode = 0;  // value term: 0 = ratio - 1 clipped to +-kUClip, 1 = log(ratio) (ratio floored at 1%)
  std::map<int, std::vector<double>> target;  // T -> a (n) followed by b (n)
  std::vector<double> lossmap;                  // x1 y1 x2 y2 ...: relative value loss -> relative real loss
  std::vector<double> lossmap_late;             // the same for positions with a tile of 2048 or more (repair less)
  std::vector<double> lossmap_top;              // positions with a tile of 16384 or more (when present; else late)
  // table-decided positions: x = (p_ref - p_move) / p_ref from the exact tables' success probabilities -> real loss
  // (the sub-goal's failure is partly repaired: 29% -> ~20%, 66% -> ~39%; scripts/fit_lossmap_table.py)
  std::vector<double> lossmap_table;
  // Odds correction for odd formations (workstream anypos, 2026-10-07; "ocorr NAME c_1 .. c_n" per knot): z_T +=
  // sum_j B(s).ocorr_j * x_j for every target T (the chain rule's base ratios unchanged), x from the board the odds are
  // read from (analyze: shape_shift()). Zero for positions in the range real games occupy.
  std::map<std::string, std::vector<double>> ocorr;
  // the same for a player's OWN move in a review (when present; else lossmap_table): fitted on played moves, which
  // players repair better than the engine's continuation suggests (workstream cal7, the scorecard's game-level check)
  std::vector<double> lossmap_table_played;
  // for the move a player actually chose in a position with a tile of 16384 or more: expert disputes showed the engine
  // undervalues such choices (claimed 10-20% value loss -> -1% real, 20-40% -> 4%, 40%+ -> 15%)
  std::vector<double> lossmap_played_expert;
  // "your cost": the share of a human-like player's OWN chances of the next milestone (the next doubling of the largest
  // tile) that a move costs against the engine's move, by relative value loss, per phase (0: largest real tile <= 512,
  // 1: 1024-2048, 2: 4096-8192; scripts/fit_owncost.py on the coach workstream's playouts); lines "lossmap_own PHASE ..."
  std::map<int, std::vector<double>> lossmap_own;
  // the same by skill band (workstream cal8, the review study's 256-playout player-level truth): players whose
  // human-model skill theta is below own_split (novices: costs ~3x the phase map) and the rest (~0 for small losses);
  // lines "own_split X", "lossmap_own_lo PHASE ...", "lossmap_own_hi PHASE ..."; a band without a map for the phase,
  // or an unknown skill, uses the phase map
  double own_split = NAN;
  std::map<int, std::vector<double>> lossmap_own_lo, lossmap_own_hi;
  // warn thresholds per phase (0-3, phase 3 = 16384+): relative value loss at which an app should warn before the move
  // is committed (the coach study: warnings beat hints; ~0.15 early, 0.05 later). Line "warn T0 T1 T2 T3".
  std::vector<double> warn = {0.15, 0.05, 0.05, 0.30};

  bool load(const std::string& path) {
    FILE* f = fopen(path.c_str(), "r");
    if (!f) return false;
    char buf[1 << 16];
    while (fgets(buf, sizeof buf, f)) {
      std::istringstream in(buf);
      std::string key;
      in >> key;
      std::vector<double> xs;
      int t = 0;
      std::string oname;
      if (key == "target") in >> t;
      if (key == "ocorr") in >> oname;
      double x;
      while (in >> x) xs.push_back(x);
      if (key == "knots") knots = xs;
      else if (key == "vbar") vbar = xs;
      else if (key == "ratio") ratio = xs;
      else if (key == "target") target[t] = xs;
      else if (key == "lossmap") lossmap = xs;
      else if (key == "umode" && !xs.empty()) umode = (int)xs[0];
      else if (key == "lossmap_late") lossmap_late = xs;
      else if (key == "lossmap_top") lossmap_top = xs;
      else if (key == "lossmap_table") lossmap_table = xs;
      else if (key == "lossmap_table_played") lossmap_table_played = xs;
      else if (key == "lossmap_played_expert") lossmap_played_expert = xs;
      else if (key == "lossmap_own" && xs.size() >= 5) lossmap_own[(int)xs[0]].assign(xs.begin() + 1, xs.end());
      else if (key == "own_split" && !xs.empty()) own_split = xs[0];
      else if (key == "lossmap_own_lo" && xs.size() >= 5) lossmap_own_lo[(int)xs[0]].assign(xs.begin() + 1, xs.end());
      else if (key == "lossmap_own_hi" && xs.size() >= 5) lossmap_own_hi[(int)xs[0]].assign(xs.begin() + 1, xs.end());
      else if (key == "warn" && xs.size() == 4) warn = xs;
      else if (key == "ocorr" && !oname.empty() && xs.size() == knots.size()) ocorr[oname] = xs;
    }
    fclose(f);
    return !knots.empty() && vbar.size() == knots.size() && ratio.size() == knots.size();
  }
  bool ok() const { return !knots.empty(); }
  bool has_lossmap() const { return lossmap.size() >= 4; }
  // Real relative loss of a move whose relative value loss is x (piecewise linear; flat beyond the last knot).
  // stage: 0 = largest real tile <= 1024, 1 = 2048 or more, 2 = 16384 or more (maps missing from the model fall back
  // to the previous stage's).
  double real_loss(double x, int stage = 0, bool played_expert = false) const {
    if (!has_lossmap()) return x;
    const std::vector<double>& m = played_expert && lossmap_played_expert.size() >= 4 ? lossmap_played_expert
                                   : stage >= 2 && lossmap_top.size() >= 4             ? lossmap_top
                                   : stage >= 1 && lossmap_late.size() >= 4            ? lossmap_late
                                                                                        : lossmap;
    return interp_map(m, x);
  }
  // Real loss of a move in a table-decided position from the exact success probabilities (-1 without a table map)
  double table_real_loss(double p_ref, double p_move, bool played = false) const {
    const std::vector<double>& m = played && lossmap_table_played.size() >= 4 ? lossmap_table_played : lossmap_table;
    if (m.size() < 4 || p_ref <= 0 || p_move < 0) return -1;
    return interp_map(m, std::max(0.0, (p_ref - p_move) / p_ref));
  }
  // Share of a human-like player's own chances of the next milestone that a move with relative value loss x costs,
  // in phase 0-2 (-1: no map for the phase, e.g. 16384+, where the coach study had no players)
  double own_cost(double x, int phase, double theta = NAN) const {
    if (!std::isnan(theta) && !std::isnan(own_split)) {
      const auto& band = theta < own_split ? lossmap_own_lo : lossmap_own_hi;
      auto b = band.find(phase);
      if (b != band.end() && b->second.size() >= 4) return interp_map(b->second, x);
    }
    auto it = lossmap_own.find(phase);
    if (it == lossmap_own.end() || it->second.size() < 4) return -1;
    return interp_map(it->second, x);
  }
  // piecewise linear through the knots x1 y1 x2 y2 ...; beyond the last knot proportional, capped at 1
  static double interp_map(const std::vector<double>& m, double x) {
    size_t n = m.size() / 2;
    if (x <= m[0]) return m[1];
    for (size_t k = 0; k + 1 < n; k++) {
      double x0 = m[2 * k], y0 = m[2 * k + 1], x1 = m[2 * k + 2], y1 = m[2 * k + 3];
      if (x <= x1) return y0 + (y1 - y0) * (x - x0) / std::max(1e-12, x1 - x0);
    }
    return std::min(1.0, m[2 * n - 1] * x / std::max(1e-12, m[2 * n - 2]));
  }
  // hat-function weights at log2 sum s
  void hats(double s, std::vector<double>& B) const {
    size_t n = knots.size();
    B.assign(n, 0.0);
    if (s <= knots[0]) { B[0] = 1; return; }
    if (s >= knots[n - 1]) { B[n - 1] = 1; return; }
    for (size_t k = 0; k + 1 < n; k++)
      if (s >= knots[k] && s < knots[k + 1]) {
        double w = (s - knots[k]) / (knots[k + 1] - knots[k]);
        B[k] = 1 - w, B[k + 1] = w;
        return;
      }
  }
  static double dot(const std::vector<double>& B, const std::vector<double>& c, size_t off = 0) {
    double r = 0;
    for (size_t k = 0; k < B.size(); k++) r += B[k] * c[off + k];
    return r;
  }
  // Expected future points: c(s) x value, c clamped at 0 (the fitted ratio can dip below 0 at the last knot, where
  // hardly any data exists) and the result never negative.
  double future(double tile_sum, double value) const {
    std::vector<double> B;
    hats(std::log2(std::max(tile_sum, 2.0)), B);
    return std::max(0.0, std::max(0.0, dot(B, ratio)) * value);
  }
  // P(reach T) for every target T above `max_tile`, made consistent by the chain rule: a bigger tile needs the
  // smaller ones first, so P(T_k) <= P(T_k-1) x the base conditional P(T_k | T_k-1) at this tile sum (the models at the
  // average value). Danger that the model of a smaller target sees (e.g. a nearly dead board) thus caps the bigger
  // targets, whose own value slope is weak (their outcomes are mostly luck).
  // The formation correction's logit shift at this tile sum for features x (name -> value; names without an ocorr
  // line count 0).
  double shape_shift(double tile_sum, const std::vector<std::pair<std::string, double>>& x) const {
    if (ocorr.empty()) return 0;
    std::vector<double> B;
    hats(std::log2(std::max(tile_sum, 2.0)), B);
    double d = 0;
    for (auto& kv : x) {
      auto it = ocorr.find(kv.first);
      if (it != ocorr.end() && kv.second != 0) d += dot(B, it->second) * kv.second;
    }
    return d;
  }
  std::map<int, double> odds(int max_tile, double tile_sum, double value, double shift = 0) const {
    std::map<int, double> out;
    std::vector<double> B;
    hats(std::log2(std::max(tile_sum, 2.0)), B);
    double avg = std::max(1.0, dot(B, vbar));
    double prev = -1, prev_base = -1;
    for (auto& t : target) {
      if (t.first <= max_tile) continue;
      double p = prob(t.first, tile_sum, value, shift), base = prob(t.first, tile_sum, avg);
      if (prev >= 0 && prev_base > 0) p = std::min(p, prev * std::min(1.0, base / prev_base));
      if (prev >= 0) p = std::min(p, prev);
      out[t.first] = p;
      prev = p, prev_base = base;
    }
    return out;
  }
  // P(reach tile T) for a position with this tile sum and value; -1 if the model has no such target
  double prob(int T, double tile_sum, double value, double shift = 0) const {
    auto it = target.find(T);
    if (it == target.end()) return -1;
    std::vector<double> B;
    hats(std::log2(std::max(tile_sum, 2.0)), B);
    double vb = std::max(1.0, dot(B, vbar));
    double ratio = value / vb;  // value term as scripts/fit_calib.py (umode)
    double u = umode == 1 ? std::log(std::max(ratio, 0.01)) : std::max(-kUClip, std::min(kUClip, ratio - 1.0));
    double z = dot(B, it->second, 0) + dot(B, it->second, knots.size()) * u + shift;
    return 1.0 / (1.0 + std::exp(-std::max(-30.0, std::min(30.0, z))));
  }
};

// Personal odds model (scripts/fit_personal.py): for softmax players of temperature t, logit P(reach T) =
// a_{t,T}(s) + b_{t,T} * u with the player's own vbar_t(s); between fitted temperatures, linear in log t.
struct PersonalModel {
  std::vector<double> knots;
  std::map<double, std::vector<double>> vbar;                 // t -> vbar at knots
  std::map<double, std::map<int, std::vector<double>>> coef;  // t -> T -> a (n) + b (1)
  std::map<double, std::vector<double>> lossmap;              // t -> x1 y1 x2 y2 ...: value loss -> real loss at skill t
  // phase (0: largest tile <= 512, 1: 1024-2048, 2: 4096-8192, 3: 16384+) -> t_soft1 t_fit1 t_soft2 t_fit2 ...: the
  // skill a game review fits (softmax over search values) to games of the soft:t_soft player (softmax over 1-ply
  // network values) - the two scales differ (soft 0.01 reviews as ~0.014-0.022), so a reviewed skill is converted
  std::map<int, std::vector<double>> skillmap;
  // The simulated player the model was fitted on ("player soft" or "player human"; default soft). For "human", a
  // model key k is the human move model's skill s = -ln(100 k) (src/human.h; personal v3, workstream hm).
  std::string player = "soft";
  // Care in danger (personal v5, workstream hm3; "pplan LO HI DE DM"): the simulated player of key k, on a board with
  // at most DE empty cells, plays with probability q(k) = clip((ln LO - ln k) / (ln LO - ln HI), 0, 1) the move DM
  // (2: the best depth-2 move that keeps the largest tile in its corner) instead of the move model's sample.
  double plan_lo = 0, plan_hi = 0;
  int plan_e = 2, plan_m = 2;
  double plan_q(double k) const {
    if (!(plan_lo > 0) || !(plan_hi > 0) || !(k > 0) || plan_lo == plan_hi) return 0;
    double q = (std::log(plan_lo) - std::log(k)) / (std::log(plan_lo) - std::log(plan_hi));
    return q < 0 ? 0 : q > 1 ? 1 : q;
  }
  // phase -> key1 theta1 key2 theta2 ...: the human-model skill theta (maximum likelihood of the moves under the human
  // move model, src/human.h, as a game review fits it) of the games of the key-k simulated players ("pthetamap" lines,
  // workstream hm2): a player's own fitted theta -> the key whose simulated players move like them, without the
  // softmax review statistic in between
  std::map<int, std::vector<double>> thetamap;
  // phase -> a b c d: real players' softmax review skill t vs their human-model skill theta (per player and phase,
  // scripts/hm_skill_real.py): log t = a + b theta and theta = c + d log t ("pthetat" lines; a phase without a line
  // uses the nearest lower phase's). A real player's theta reaches the personal model through t and the skill map:
  // the direct theta map above is far too pessimistic for real players (the simulated players with a player's theta
  // compound their errors; real players repair them), so it serves only simulations of the key-k players (coach)
  std::map<int, std::vector<double>> thetat;
  // phase -> threshold of the position's error risk (expected share of the player's own chances lost at their skill)
  // above which an app shows a hint before the player moves ("phint" line; negative: no hints in that phase)
  double hint[4] = {-1, -1, -1, -1};

  bool load(const std::string& path) {
    FILE* f = fopen(path.c_str(), "r");
    if (!f) return false;
    char buf[1 << 16];
    while (fgets(buf, sizeof buf, f)) {
      std::istringstream in(buf);
      std::string key;
      in >> key;
      double t = 0;
      int T = 0, ph = -1;
      if (key == "pvbar" || key == "personal" || key == "plossmap") in >> t;
      if (key == "pskillmap") in >> ph;
      if (key == "personal") in >> T;
      std::vector<double> xs;
      double x;
      while (in >> x) xs.push_back(x);
      if (key == "phint") {
        std::istringstream again(buf);
        std::string k2;
        again >> k2;
        for (int ph = 0; ph < 4; ph++)
          if (!(again >> hint[ph])) break;
        continue;
      }
      if (key == "pthetat") {
        std::istringstream again(buf);
        std::string k2;
        int ph2 = -1;
        again >> k2 >> ph2;
        std::vector<double> ys;
        double y;
        while (again >> y) ys.push_back(y);
        if (ph2 >= 0 && ys.size() >= 4) thetat[ph2] = ys;
        continue;
      }
      if (key == "pthetamap") {
        std::istringstream again(buf);
        std::string k2;
        int ph2 = -1;
        again >> k2 >> ph2;
        std::vector<double> ys;
        double y;
        while (again >> y) ys.push_back(y);
        if (ph2 >= 0 && ys.size() >= 4) thetamap[ph2] = ys;
        continue;
      }
      if (key == "pplan") {
        std::istringstream again(buf);
        std::string k2;
        double lo = 0, hi = 0;
        int e = 2, m = 2;
        again >> k2 >> lo >> hi >> e >> m;
        plan_lo = lo, plan_hi = hi, plan_e = e, plan_m = m;
        continue;
      }
      if (key == "player") {
        std::istringstream again(buf);
        std::string k2, v;
        again >> k2 >> v;
        if (!v.empty()) player = v;
        continue;
      }
      if (key == "pknots") knots = xs;
      else if (key == "pvbar") vbar[t] = xs;
      else if (key == "personal") coef[t][T] = xs;
      else if (key == "plossmap") lossmap[t] = xs;
      else if (key == "pskillmap" && ph >= 0 && xs.size() >= 4) skillmap[ph] = xs;
    }
    fclose(f);
    return !knots.empty() && !coef.empty();
  }
  bool ok() const { return !knots.empty() && !coef.empty(); }
  bool has_lossmap() const { return !lossmap.empty(); }
  // The soft player's temperature for a player whose reviewed skill in phase ph is t_fit (log-log interpolation of the
  // phase's skill map, or of the nearest lower phase that has one; proportional beyond its ends; t_fit itself without
  // a map).
  double soft_t(double t_fit, int ph) const {
    if (skillmap.empty() || t_fit <= 0) return t_fit;
    auto it = skillmap.upper_bound(ph);
    if (it == skillmap.begin()) return t_fit;
    const std::vector<double>& m = std::prev(it)->second;
    size_t n = m.size() / 2;
    if (t_fit <= m[1]) return m[0] * t_fit / m[1];
    for (size_t k = 0; k + 1 < n; k++)
      if (t_fit <= m[2 * k + 3]) {
        double w = (std::log(t_fit) - std::log(m[2 * k + 1])) / std::max(1e-12, std::log(m[2 * k + 3]) - std::log(m[2 * k + 1]));
        return std::exp((1 - w) * std::log(m[2 * k]) + w * std::log(m[2 * k + 2]));
      }
    return m[2 * n - 2] * t_fit / m[2 * n - 1];
  }
  // The phase's theta map (or the nearest lower phase's), as (theta, log key) points sorted by theta; empty without one.
  std::vector<std::pair<double, double>> theta_points(int ph) const {
    std::vector<std::pair<double, double>> pts;
    if (thetamap.empty()) return pts;
    auto it = thetamap.upper_bound(ph);  // the first phase above ph: the map of ph or the nearest lower phase, else
    const std::vector<double>& m = it == thetamap.begin() ? it->second : std::prev(it)->second;  // the lowest phase's
    for (size_t k = 0; k + 1 < m.size(); k += 2)
      if (m[k] > 0) pts.push_back({m[k + 1], std::log(m[k])});
    std::sort(pts.begin(), pts.end());
    return pts;
  }
  bool has_thetamap() const { return !thetamap.empty(); }
  // A real player's skill theta -> the personal model's key (through t and the skill map when there are pthetat
  // lines, else the direct theta map); NaN when neither exists.
  bool has_theta_skill() const { return !thetat.empty() || !thetamap.empty(); }
  const std::vector<double>* thetat_at(int ph) const {
    if (thetat.empty()) return nullptr;
    auto it = thetat.upper_bound(ph);
    return it == thetat.begin() ? &it->second : &std::prev(it)->second;
  }
  double t_of_theta(double theta, int ph) const {
    const std::vector<double>* c = thetat_at(ph);
    return c && !std::isnan(theta) ? std::exp((*c)[0] + (*c)[1] * theta) : NAN;
  }
  double theta_of_t(double t, int ph) const {
    const std::vector<double>* c = thetat_at(ph);
    return c && t > 0 ? (*c)[2] + (*c)[3] * std::log(t) : NAN;
  }
  double key_of_theta(double theta, int ph) const {
    if (!thetat.empty()) return soft_t(t_of_theta(theta, ph), ph);
    return key_of_theta_direct(theta, ph);
  }
  // The model key whose simulated players' games review at human-model skill theta in phase ph (log key linear in
  // theta between the map's points, clamped to its ends: the model has no players beyond them); NaN without a map.
  double key_of_theta_direct(double theta, int ph) const {
    auto pts = theta_points(ph);
    if (pts.size() < 2 || std::isnan(theta)) return NAN;
    if (theta <= pts.front().first) return std::exp(pts.front().second);
    if (theta >= pts.back().first) return std::exp(pts.back().second);
    for (size_t k = 0; k + 1 < pts.size(); k++)
      if (theta <= pts[k + 1].first) {
        double w = (theta - pts[k].first) / std::max(1e-12, pts[k + 1].first - pts[k].first);
        return std::exp((1 - w) * pts[k].second + w * pts[k + 1].second);
      }
    return std::exp(pts.back().second);
  }
  // The inverse: the human-model skill of the key-k simulated players in phase ph (NaN without a map).
  double theta_of_key(double key, int ph) const {
    auto pts = theta_points(ph);
    if (pts.size() < 2 || !(key > 0)) return NAN;
    std::sort(pts.begin(), pts.end(), [](auto& a, auto& b) { return a.second < b.second; });  // by log key
    double lk = std::log(key);
    if (lk <= pts.front().second) return pts.front().first;
    if (lk >= pts.back().second) return pts.back().first;
    for (size_t k = 0; k + 1 < pts.size(); k++)
      if (lk <= pts[k + 1].second) {
        double w = (lk - pts[k].second) / std::max(1e-12, pts[k + 1].second - pts[k].second);
        return (1 - w) * pts[k].first + w * pts[k + 1].first;
      }
    return pts.back().first;
  }
  // Real loss at skill t of a move whose relative value loss is x (the maps of the nearest temperatures, linear in log t)
  double real_loss(double t, double x) const {
    if (lossmap.empty()) return -1;
    auto at = [&](const std::vector<double>& m) {
      size_t n = m.size() / 2;
      if (n < 2) return x;
      if (x <= m[0]) return m[1];
      for (size_t k = 0; k + 1 < n; k++)
        if (x <= m[2 * k + 2]) return m[2 * k + 1] + (m[2 * k + 3] - m[2 * k + 1]) * (x - m[2 * k]) / std::max(1e-12, m[2 * k + 2] - m[2 * k]);
      return std::min(1.0, m[2 * n - 1] * x / std::max(1e-12, m[2 * n - 2]));
    };
    auto hi = lossmap.lower_bound(t);
    if (hi == lossmap.end()) return at(std::prev(hi)->second);
    if (hi == lossmap.begin() || hi->first == t) return at(hi->second);
    auto lo = std::prev(hi);
    double w = (std::log(t) - std::log(lo->first)) / (std::log(hi->first) - std::log(lo->first));
    return (1 - w) * at(lo->second) + w * at(hi->second);
  }
  double prob_at(double t, int T, double tile_sum, double value) const {
    auto it = coef.find(t);
    if (it == coef.end()) return -1;
    auto jt = it->second.find(T);
    if (jt == it->second.end()) return -1;
    Calib c;  // reuse the hat functions
    c.knots = knots;
    std::vector<double> B;
    c.hats(std::log2(std::max(tile_sum, 2.0)), B);
    double vb = std::max(1.0, Calib::dot(B, vbar.at(t)));
    double u = value / vb - 1.0;
    const auto& w = jt->second;
    double z = Calib::dot(B, w) + w[knots.size()] * u;
    return 1.0 / (1.0 + std::exp(-std::max(-30.0, std::min(30.0, z))));
  }
  // P for temperature t (interpolated in log t between the two nearest fitted temperatures), every target above
  // max_tile that both have; made non-increasing in T.
  std::map<int, double> odds(double t, int max_tile, double tile_sum, double value) const {
    std::map<int, double> out;
    if (!ok()) return out;
    auto hi = coef.lower_bound(t);
    auto lo = hi;
    if (hi == coef.end()) lo = hi = std::prev(coef.end());
    else if (hi != coef.begin() && hi->first != t) lo = std::prev(hi);
    double w = (lo == hi) ? 0.0 : (std::log(t) - std::log(lo->first)) / (std::log(hi->first) - std::log(lo->first));
    w = std::max(0.0, std::min(1.0, w));
    for (auto& kv : lo->second) {
      int T = kv.first;
      if (T <= max_tile) continue;
      double pl = prob_at(lo->first, T, tile_sum, value), ph = prob_at(hi->first, T, tile_sum, value);
      if (pl < 0 || ph < 0) continue;
      // interpolate in logit space
      auto lg = [](double p) { p = std::min(1 - 1e-6, std::max(1e-6, p)); return std::log(p / (1 - p)); };
      double z = (1 - w) * lg(pl) + w * lg(ph);
      out[T] = 1.0 / (1.0 + std::exp(-z));
    }
    double run = 1.0;
    for (auto& kv : out) run = kv.second = std::min(kv.second, run);
    return out;
  }
};
