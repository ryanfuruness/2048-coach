// Human move model (workstream hm, 2026-10-07): a policy that plays like the human players of the curated data set.
//
// P(d) = (1 - eps) * softmax_d( s * V(d) + g(s) * S(d) + H(d) ) + eps / n_legal, with skill theta:
//   s = exp(theta)                  the value part's weight (inverse temperature)
//   g(s) = exp(ga + gb * theta)     the structure part's weight (tied to the same skill)
//   V(d) = -sum_k wv_k * max(0, loss1(d) - k)   hinge basis of the relative 1-ply loss, soft_move's scale:
//          loss1 = (best - q) / max(1, |best|), q = reward + network value of the afterstate's view
//   S(d) = concept features of the afterstate (explain.h) and the move's direction relative to the biggest tile's
//          corner and wall line (perp_toward = the base class, line_toward, line_away, perp_away)
//   H(d) = habits: the same move as the previous one, alternation with the one before that, the move's share among
//          the player's last 20 moves, and "unused" (no such move in the last 20, with at least 10 known): players
//          settle into three directions and almost never press the fourth (median share 0.0-0.3% for
//          intermediate, strong and expert players although it is legal in 99% of positions)
// Fitted by maximum likelihood (scripts/hm_fit.py, model full_tied_death_recent, 114,970 clean decisions of 80
// players); the weights below are scripts/hm_export.py's output (results/hm/human_model_v2.txt, copied here by
// scripts/hm_sync_header.py). Held-out (5 folds by player, skill fitted on the first half of each test player's
// decisions): 0.764 nats per decision vs 1.010 for the softmax player (results/hm/report.txt).
// As a generative player (playouts) the move-level skill is too weak (errors compound on its own trajectory): the
// personal-odds family plays at value skill s and structure skill min(s, 0.4) (scripts/hm_personal.sh).
// Typical skills (median theta per tier): novice -0.82, intermediate -0.22, strong -0.22, expert -0.44 (experts look
// noisier because the 1-ply value is a weaker guide in the late game).
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>

#include "board.h"
#include "engine.h"
#include "explain.h"

namespace hm {

enum Feat {
  kCorner, kCornerLost, kChainLen, kChainDrop, kExposed, kTrapped, kBigOffEdge, kCornerDist, kMergesNext, kEmpty,
  kMoved, kMerge, kMergeSize, kDeath, kLineToward, kLineAway, kPerpAway, kNumFeat
};
inline constexpr const char* kFeatName[kNumFeat] = {
    "corner", "corner_lost", "chain_len", "chain_drop", "exposed", "trapped", "big_off_edge", "corner_dist",
    "merges_next", "empty", "moved", "merge", "merge_size", "death", "line_toward", "line_away", "perp_away"};

struct Model {
  double knots[6] = {0.0, 0.003, 0.01, 0.03, 0.1, 0.3};
  double wv[6] = {6.355390, 3.674898, 0.739957, -2.688477, -2.972242, -5.109217};
  double ws[kNumFeat] = {0.600259, -1.702783, 0.707696, 0.264493, -0.088831, -0.750851, -1.229347, 0.455514, 0.243504, 0.297022, -0.607714, -0.859779, 4.055399, -4.826227, -0.740552, -0.505759, -1.477619};
  double w_repeat = -0.100968, w_alternate = 0.270290, w_recent_share = 0.653707, w_unused = -1.447716;
  double eps = 0.000679239;
  double ga = 0.410815, gb = 2.588824;
  // Late game (workstream hm2): positions with a tile sum >= 20480 are valued by a hinge on the engine's SEARCH losses
  // (analyze's scale) where the caller has them (the analysis; playouts keep the 1-ply hinge): experts look deeper
  // than one move. Refit on best_v6b values with every other weight fixed (scripts/hm_late_refit.py --late-search):
  // held-out players' log-loss at tile sums >= 20480 0.799 -> 0.769 nats per decision (results/hm2/report.txt).
  double wv_late[6] = {40.189, 15.307, -11.579, -32.492, -6.709, 2.796};
  bool has_late = true;

  // Reads a file written by scripts/hm_export.py (unknown keys ignored); false if it cannot be read.
  bool load(const std::string& path) {
    FILE* f = fopen(path.c_str(), "r");
    if (!f) return false;
    char buf[1024], name[256];
    while (fgets(buf, sizeof buf, f)) {
      double a, b;
      if (!strncmp(buf, "wv ", 3)) {
        char* p = buf + 3;
        for (int k = 0; k < 6; k++) {
          int used = 0;
          if (sscanf(p, "%lf %lf%n", &a, &b, &used) != 2) break;
          knots[k] = a, wv[k] = b, p += used;
        }
      } else if (sscanf(buf, "ws %255s %lf", name, &a) == 2) {
        for (int j = 0; j < kNumFeat; j++)
          if (!strcmp(name, kFeatName[j])) ws[j] = a;
      } else if (sscanf(buf, "wh %255s %lf", name, &a) == 2) {
        if (!strcmp(name, "repeat")) w_repeat = a;
        if (!strcmp(name, "alternate")) w_alternate = a;
        if (!strcmp(name, "recent_share")) w_recent_share = a;
        if (!strcmp(name, "unused")) w_unused = a;
      } else if (sscanf(buf, "eps %lf", &a) == 1) {
        eps = a;
      } else if (sscanf(buf, "gab %lf %lf", &a, &b) == 2) {
        ga = a, gb = b;
      } else if (!strncmp(buf, "wv_late ", 8)) {
        char* p = buf + 8;
        for (int k = 0; k < 6; k++) {
          int used = 0;
          if (sscanf(p, "%lf %lf%n", &a, &b, &used) != 2) break;
          wv_late[k] = b, p += used;
        }
        has_late = true;
      }
    }
    fclose(f);
    return true;
  }
};

// The player's recent moves (the habit features): the last kLen moves of the current game.
struct History {
  static constexpr int kLen = 20;
  int buf[kLen] = {};
  int n = 0;  // moves recorded so far (all of them; the window holds the last kLen)
  int count[4] = {};
  void clear() { *this = History(); }
  void push(int d) {
    if (n >= kLen) count[buf[n % kLen]]--;
    buf[n % kLen] = d;
    count[d]++;
    n++;
  }
  int len() const { return n < kLen ? n : kLen; }
  int prev(int k) const { return n >= k ? buf[(n - k) % kLen] : -1; }  // k = 1: the last move
};

// Share of the spawns after afterstate a (2: 0.9, 4: 0.1, uniform over the empty cells) that leave no legal move.
static inline double death_share(board_t a) {
  double dead = 0;
  int ne = 0;
  for (int c = 0; c < 16; c++) {
    if (bb::cell(a, c)) continue;
    ne++;
    for (int k = 1; k <= 2; k++) {
      board_t s = bb::set_cell(a, c, k);
      bool any = false;
      for (int d = 0; d < 4 && !any; d++) any = bb::move(s, d) != s;
      if (!any) dead += k == 1 ? 0.9 : 0.1;
    }
  }
  return ne ? dead / ne : 0.0;
}

// Direction class of each move relative to the biggest tile (the copy nearest a corner) and its wall line (its row if
// the row's tiles sum to at least its column's, else its column): 0 perp_toward (presses the line against its wall),
// 1 line_toward (along the line into the corner), 2 line_away, 3 perp_away (pulls the line off its wall).
static inline void dir_classes(board_t b, int cls[4]) {
  int mx = bb::max_rank(b), mcell = -1, md = 99;
  for (int c = 0; c < 16; c++) {
    if (bb::cell(b, c) != mx) continue;
    int r = c / 4, k = c % 4, dist = std::min(r, 3 - r) + std::min(k, 3 - k);
    if (dist < md) md = dist, mcell = c;
  }
  int r = mcell / 4, k = mcell % 4;
  int vt = r < 2 ? 0 : 2, ht = k < 2 ? 3 : 1;  // up/down, left/right toward the corner
  double rowsum = 0, colsum = 0;
  for (int j = 0; j < 4; j++) {
    int a = bb::cell(b, r * 4 + j), c2 = bb::cell(b, j * 4 + k);
    rowsum += a ? std::ldexp(1.0, a) : 0;
    colsum += c2 ? std::ldexp(1.0, c2) : 0;
  }
  bool horiz = rowsum >= colsum;
  int perp_t = horiz ? vt : ht, line_t = horiz ? ht : vt;
  for (int d = 0; d < 4; d++)
    cls[d] = d == perp_t ? 0 : d == line_t ? 1 : d == (line_t + 2) % 4 ? 2 : 3;
}

// The skill-independent parts of the model's move scores for one position (workstream hm2): per legal move d the value
// part V(d) (weighted by exp(theta)), the structure part S(d) (weighted by g) and the habit part H(d), so that a
// player's skill can be fitted over many positions without re-evaluating them (probs = terms + probs_from_terms).
struct Terms {
  double v[4] = {}, st[4] = {}, h[4] = {};
  bool legal[4] = {};
  int n = 0;  // legal moves
};

// The model's move probabilities from the terms at skill theta (theta_s: see probs).
static inline int probs_from_terms(const Model& M, const Terms& T, double theta, double p[4], double theta_s = NAN) {
  for (int d = 0; d < 4; d++) p[d] = 0;
  if (!T.n) return 0;
  double s = std::exp(theta), g = std::exp(M.ga + M.gb * (std::isnan(theta_s) ? theta : theta_s));
  double z[4], zmax = -1e300;
  for (int d = 0; d < 4; d++) {
    if (!T.legal[d]) continue;
    z[d] = s * T.v[d] + g * T.st[d] + T.h[d];
    zmax = std::max(zmax, z[d]);
  }
  double tot = 0;
  for (int d = 0; d < 4; d++)
    if (T.legal[d]) tot += p[d] = std::exp(z[d] - zmax);
  for (int d = 0; d < 4; d++)
    if (T.legal[d]) p[d] = (1 - M.eps) * p[d] / tot + M.eps / T.n;
  return T.n;
}

// The terms of board b (engine encoding) given the player's recent moves. Returns the number of legal moves.
// search_loss (late positions in the analysis: tile sum >= 20480): the engine's relative search loss of each move,
// valued by the late hinge instead of the 1-ply loss.
static inline int terms(const Engine& E, const Model& M, board_t b, const History& hist, Terms& T,
                        const double* search_loss = nullptr) {
  int prev1 = hist.prev(1), prev2 = prev1 >= 0 ? hist.prev(2) : -1, hl = hist.len();
  double q[4], f[4][kNumFeat];
  uint32_t rw[4];
  bool legal[4];
  int n = 0;
  double best = -1e300;
  ex::Features f0 = ex::features(b);
  int cls[4];
  dir_classes(b, cls);
  for (int d = 0; d < 4; d++) {
    board_t a = bb::move(b, d, rw[d]);
    legal[d] = a != b;
    if (!legal[d]) continue;
    n++;
    q[d] = rw[d] + E.ev(E.view(a));
    best = std::max(best, q[d]);
    ex::Features fa = ex::features(a);
    int moved = 0;
    for (int c = 0; c < 16; c++) moved += bb::cell(a, c) != bb::cell(b, c);
    double* x = f[d];
    x[kCorner] = fa.corner;
    x[kCornerLost] = f0.corner && !fa.corner;
    x[kChainLen] = fa.chain_len;
    x[kChainDrop] = std::max(0, f0.chain_len - fa.chain_len);
    x[kExposed] = fa.exposed;
    x[kTrapped] = fa.trapped;
    x[kBigOffEdge] = fa.big_off_edge;
    x[kCornerDist] = fa.corner_dist;
    x[kMergesNext] = fa.merges;
    x[kEmpty] = fa.empty;
    x[kMoved] = moved / 16.0;
    x[kMerge] = rw[d] > 0;
    x[kMergeSize] = std::log2(1.0 + rw[d]) / 10.0;
    x[kDeath] = death_share(a);
    x[kLineToward] = cls[d] == 1;
    x[kLineAway] = cls[d] == 2;
    x[kPerpAway] = cls[d] == 3;
  }
  T = Terms();
  T.n = n;
  if (!n) return 0;
  for (int d = 0; d < 4; d++) {
    T.legal[d] = legal[d];
    if (!legal[d]) continue;
    double loss = (best - q[d]) / std::max(1.0, std::fabs(best)), v = 0, st = 0;
    if (search_loss && M.has_late && !std::isnan(search_loss[d]))
      for (int k = 0; k < 6; k++) v -= M.wv_late[k] * std::max(0.0, search_loss[d] - M.knots[k]);
    else
      for (int k = 0; k < 6; k++) v -= M.wv[k] * std::max(0.0, loss - M.knots[k]);
    for (int j = 0; j < kNumFeat; j++) st += M.ws[j] * f[d][j];
    T.v[d] = v, T.st[d] = st;
    T.h[d] = (d == prev1 ? M.w_repeat : 0.0) + (prev2 >= 0 && d == prev2 && d != prev1 ? M.w_alternate : 0.0) +
             M.w_recent_share * hist.count[d] / std::max(1, hl) + (hl >= 10 && hist.count[d] == 0 ? M.w_unused : 0.0);
  }
  return n;
}

// The model's move probabilities for board b (engine encoding) given the player's recent moves and skill theta;
// p[d] = 0 for illegal moves. Returns the number of legal moves. theta_s (if not NaN) replaces theta in the structure
// weight g (an untied player: value skill theta, structure skill theta_s).
static inline int probs(const Engine& E, const Model& M, board_t b, const History& hist, double theta, double p[4],
                        double theta_s = NAN) {
  Terms T;
  terms(E, M, b, hist, T);
  return probs_from_terms(M, T, theta, p, theta_s);
}

// Log-likelihood of the played move d under the terms at skill theta (the tied model: structure skill = theta).
static inline double loglik(const Model& M, const Terms& T, int d, double theta) {
  double p[4];
  if (!probs_from_terms(M, T, theta, p) || d < 0 || d > 3 || !T.legal[d]) return 0.0;
  return std::log(std::max(1e-300, p[d]));
}

// Draws the model's move (-1: no legal move).
static inline int move(const Engine& E, const Model& M, board_t b, const History& hist, double theta, bb::Rng& rng,
                       double theta_s = NAN) {
  double p[4];
  if (!probs(E, M, b, hist, theta, p, theta_s)) return -1;
  double u = rng.uniform(), acc = 0;
  int last = -1;
  for (int d = 0; d < 4; d++) {
    if (p[d] <= 0) continue;
    last = d;
    acc += p[d];
    if (u < acc) return d;
  }
  return last;
}

}  // namespace hm
