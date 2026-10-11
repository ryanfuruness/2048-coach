// The simulated human player of the personal odds (personal v5, workstream hm3): the human move model (src/human.h)
// at value skill s = -ln(100 k) and structure skill min(s, 0.4) for a model key k, plus CARE IN DANGER: on a board
// with at most `de` empty cells, with probability q(k) = clip((ln 0.02 - ln k) / (ln 0.02 - ln 0.015), 0, 1), the best
// depth-2 move among those that keep the largest tile in its corner (when it is in one). Exactly build/messy's policy
// "human:th=s:ths=min(s,0.4):dq=q:de=2:dm=2" (scripts/hm3_personal.sh), whose games the personal-odds model was fitted
// on and whose keys real players are mapped to (weights/calib/personal.txt: pskillmap, pthetat; outcomes checked on
// real games). Workstream yc (your chance, 2026-10-10): the policy as a distribution, for rollouts and for TD
// evaluation of the player's own chances.
#pragma once
#include <cmath>

#include "engine.h"
#include "human.h"

namespace hp {

struct Player {
  double key = 0.016;
  double theta = 0, theta_s = 0, dq = 0;
  int de = 2;
  explicit Player(double k = 0.016, double plan_lo = 0.02, double plan_hi = 0.015) { set(k, plan_lo, plan_hi); }
  void set(double k, double plan_lo = 0.02, double plan_hi = 0.015) {
    key = k;
    theta = -std::log(100.0 * k);
    theta_s = std::min(theta, 0.4);
    double q = (std::log(plan_lo) - std::log(k)) / (std::log(plan_lo) - std::log(plan_hi));
    dq = q < 0 ? 0 : q > 1 ? 1 : q;
  }
};

static inline bool max_in_corner(board_t x) {
  int m = bb::max_rank(x);
  return bb::cell(x, 0) == m || bb::cell(x, 3) == m || bb::cell(x, 12) == m || bb::cell(x, 15) == m;
}

// The careful move of messy's dm 2: the best depth-2 move that keeps the largest tile in its corner (if it is in one
// now; otherwise, or if no move keeps it, the best depth-2 move). -1 without a legal move.
static inline int careful_move(EngineThread& T, board_t b) {
  float mv[4];
  board_t vb = T.E.view(b);
  T.search->move_values(vb, 2, mv, T.E.params(vb));
  bool keep = max_in_corner(b);
  double bq = -1e300;
  int bk = -1;
  for (int pass = 0; pass < 2 && bk < 0; pass++)
    for (int d = 0; d < 4; d++) {
      board_t a = bb::move(b, d);
      if (a == b) continue;
      if (pass == 0 && keep && !max_in_corner(a)) continue;
      double q = std::isnan(mv[d]) ? -1e299 : mv[d];
      if (q > bq) bq = q, bk = d;
    }
  return bk;
}

// The player's move probabilities on board b (p[d] = 0 for illegal moves); returns the number of legal moves.
static inline int probs(EngineThread& T, const hm::Model& M, const Player& P, board_t b, const hm::History& hist,
                        double p[4]) {
  int n = hm::probs(T.E, M, b, hist, P.theta, p, P.theta_s);
  if (n && P.dq > 0 && bb::count_empty(b) <= P.de) {
    int c = careful_move(T, b);
    if (c >= 0)
      for (int d = 0; d < 4; d++) p[d] = (1 - P.dq) * p[d] + (d == c ? P.dq : 0.0);
  }
  return n;
}

// Draws the player's move (-1: no legal move).
static inline int move(EngineThread& T, const hm::Model& M, const Player& P, board_t b, const hm::History& hist,
                       bb::Rng& rng) {
  double p[4];
  if (!probs(T, M, P, b, hist, p)) return -1;
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

// The milestone a position plays for: 2048 first, then each doubling of the largest tile (rank).
static inline int milestone_rank(board_t b) { return std::max(11, bb::max_rank(b) + 1); }

// The chance after a move from its afterstate's value v: times the share of new tiles that do not end the game. The
// networks see the afterstate only and under-rate that danger (afterstates where most new tiles kill are rare in the
// player's games: on a nearly full board a game-ending move read 15% where the engine knew it ends the game).
static inline double with_survival(double v, board_t after) { return v * (1.0 - hm::death_share(after)); }

}  // namespace hp
