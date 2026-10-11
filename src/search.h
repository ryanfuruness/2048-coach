// Expectimax search over 4-bit boards with an n-tuple network at the leaves.
//
//   max node   (state s,     depth d): max_a  r(s,a) + chance(afterstate(s,a), d-1)
//   chance node(afterstate a, depth d): d == 0 ? V(a) : E_spawn[ max(a + spawn, d) ]
//
// depth 1 is the greedy 1-ply policy used in training. A transposition table caches
// chance-node values per (afterstate, depth). Iterative deepening under a budget of
// leaf evaluations lets tight positions (few empty cells, small branching) be
// searched much deeper than open ones at the same cost.
#pragma once
#include <cmath>
#include <algorithm>
#include <cstring>
#include <string>
#include <vector>
#include "board.h"
#include "ntuple.h"
#include "wpack.h"

// Chooses the weight stage of a board.
//
// Two kinds of spec:
//  * "sum:T1,T2,..."  stage = number of thresholds <= the sum of all tiles. The tile
//    sum never decreases during a game (merges keep it, spawns add 2 or 4), so
//    stages only ever advance - every stage boundary is crossed exactly once.
//  * rank conditions: comma-separated conditions, each an '&'-list of terms
//    ("r" = a tile of rank r is present, "r+" = a tile of rank >= r is present);
//    the stage is the (1-based) index of the last satisfied condition, 0 if none.
static inline uint32_t tile_sum(board_t b) {
  uint32_t s = 0;
  for (int i = 0; i < 16; i++, b >>= 4) {
    unsigned r = b & 0xF;
    s += r ? 1u << r : 0;
  }
  return s;
}

struct StageFn {
  struct Cond {
    uint32_t exact = 0;  // ranks that must be present
    int min_rank = 0;    // some rank >= min_rank must be present (0 = no constraint)
  };
  std::vector<Cond> conds;
  std::vector<uint32_t> sums;  // sum thresholds (sum mode)
  // sum mode, "S/R": the threshold also counts as passed once a tile of rank >= R exists
  // (0 = no alternative); e.g. "sum:20480/14,..." starts stage 1 as soon as a 16384 forms
  std::vector<int> sum_or_rank;
  int count() const { return (int)(sums.empty() ? conds.size() : sums.size()) + 1; }
  static uint32_t ranks_present(board_t b) {
    uint32_t m = 0;
    for (int i = 0; i < 16; i++, b >>= 4) m |= 1u << (b & 0xF);
    return m;
  }
  static bool holds(const Cond& c, uint32_t m) {
    return (m & c.exact) == c.exact && (c.min_rank == 0 || (m >> c.min_rank) != 0);
  }
  int of(board_t b) const {
    if (!sums.empty()) {
      uint32_t s = tile_sum(b);
      int st = 0, mr = -1;
      while (st < (int)sums.size()) {
        if (s >= sums[st]) { st++; continue; }
        if (!sum_or_rank[st]) break;
        if (mr < 0) mr = bb::max_rank(b);
        if (mr < sum_or_rank[st]) break;
        st++;
      }
      return st;
    }
    if (conds.empty()) return 0;
    uint32_t m = ranks_present(b);
    int st = 0;
    for (size_t k = 0; k < conds.size(); k++)
      if (holds(conds[k], m)) st = (int)k + 1;
    return st;
  }
  // true iff the last condition holds (used for position collection)
  bool last_holds(board_t b) const {
    if (!sums.empty()) return of(b) >= (int)sums.size();
    return !conds.empty() && holds(conds.back(), ranks_present(b));
  }
  static StageFn parse(const std::string& spec) {
    StageFn f;
    std::string s = spec;
    if (s.rfind("sum:", 0) == 0) {
      s = s.substr(4);
      size_t i = 0;
      while (i < s.size()) {
        size_t j = s.find(',', i);
        if (j == std::string::npos) j = s.size();
        std::string t = s.substr(i, j - i);
        size_t sl = t.find('/');
        f.sums.push_back((uint32_t)std::stoul(t.substr(0, sl)));
        f.sum_or_rank.push_back(sl == std::string::npos ? 0 : std::stoi(t.substr(sl + 1)));
        i = j + 1;
      }
      return f;
    }
    size_t i = 0;
    while (i < s.size()) {
      size_t j = s.find(',', i);
      if (j == std::string::npos) j = s.size();
      std::string t = s.substr(i, j - i);
      Cond c;
      size_t a = 0;
      while (a < t.size()) {
        size_t b = t.find('&', a);
        if (b == std::string::npos) b = t.size();
        std::string term = t.substr(a, b - a);
        if (!term.empty() && term.back() == '+') c.min_rank = std::stoi(term.substr(0, term.size() - 1));
        else c.exact |= 1u << std::stoi(term);
        a = b + 1;
      }
      f.conds.push_back(c);
      i = j + 1;
    }
    return f;
  }
};

// Tile downgrading for evaluation: if the board holds a 32768 (rank 15), lower
// every rank above the largest absent rank g in [min_gap, 14] by one, so the
// network sees the board as if the big tiles were one rank smaller.
static inline board_t eval_view(board_t b, int min_gap = 10) {
  uint64_t x = b & (b >> 1) & (b >> 2) & (b >> 3) & 0x1111111111111111ULL;
  if (!x) return b;
  uint32_t m = StageFn::ranks_present(b);
  int gap = -1;
  for (int k = 14; k >= min_gap; k--)
    if (!(m >> k & 1)) { gap = k; break; }
  if (gap < 0) return b;
  board_t r = 0;
  for (int i = 0; i < 16; i++) {
    int v = (b >> (4 * i)) & 0xF;
    if (v > gap) v--;
    r |= (board_t)v << (4 * i);
  }
  return r;
}

// Root downgrading (generalises eval_view): while the board holds a tile of rank >= top,
// find the largest absent rank g >= min_gap below the largest tile and lower every rank
// above g by one. Equal tiles stay equal and order is preserved, so the board plays the
// same; the network then sees e.g. a 16384-phase board as the familiar 8192 phase.
static inline board_t downgrade_view(board_t b, int top, int min_gap) {
  for (;;) {
    int mx = bb::max_rank(b);
    if (mx < top) return b;
    uint32_t m = StageFn::ranks_present(b);
    int gap = -1;
    for (int k = mx - 1; k >= min_gap; k--)
      if (!(m >> k & 1)) { gap = k; break; }
    if (gap < 0) return b;
    board_t r = 0;
    for (int i = 0; i < 16; i++) {
      int v = (b >> (4 * i)) & 0xF;
      if (v > gap) v--;
      r |= (board_t)v << (4 * i);
    }
    b = r;
  }
}

// Like downgrade_view (one step, for boards holding a tile of rank >= top), but the gap g must also
// have at most one tile of rank g-1: two of them could merge into g within a few moves, and in a view
// lowered at g that merge would look like it joins the (real g+1) tile above, which it never does.
static inline board_t downgrade_view_safe(board_t b, int top, int min_gap) {
  int mx = bb::max_rank(b);
  if (mx < top) return b;
  int cnt[16] = {0};
  for (int i = 0; i < 16; i++) cnt[(b >> (4 * i)) & 0xF]++;
  int gap = -1;
  for (int k = mx - 1; k >= min_gap; k--)
    if (!cnt[k] && cnt[k - 1] <= 1) { gap = k; break; }
  if (gap < 0) return b;
  board_t r = 0;
  for (int i = 0; i < 16; i++) {
    int v = (b >> (4 * i)) & 0xF;
    if (v > gap) v--;
    r |= (board_t)v << (4 * i);
  }
  return r;
}

// downgrade_view with safe gaps (the root view of `--root-view-safe`, workstream late 2026-10-07): while the board
// holds a tile of rank >= top, lower every rank above a gap g, preferring gaps whose rank g-1 holds at most one tile
// (else the largest absent rank, as downgrade_view). With 16384 . 16384 . / ... 65536 the plain view lowers both
// 16384s next to the lowered 65536, so their merge looks like it joins it (fuzz workstream).
static inline board_t downgrade_view_safe_all(board_t b, int top, int min_gap) {
  for (;;) {
    int mx = bb::max_rank(b);
    if (mx < top) return b;
    int cnt[16] = {0};
    for (int i = 0; i < 16; i++) cnt[(b >> (4 * i)) & 0xF]++;
    int gap = -1;
    for (int k = mx - 1; k >= min_gap; k--)
      if (!cnt[k] && cnt[k - 1] <= 1) { gap = k; break; }
    if (gap < 0)
      for (int k = mx - 1; k >= min_gap; k--)
        if (!cnt[k]) { gap = k; break; }
    if (gap < 0) return b;
    board_t r = 0;
    for (int i = 0; i < 16; i++) {
      int v = (b >> (4 * i)) & 0xF;
      if (v > gap) v--;
      r |= (board_t)v << (4 * i);
    }
    b = r;
  }
}

// Snake heuristic: tile values weighted by rho^k along a snake path from a corner (k = 0 at
// the corner), maximised over the 8 symmetries. Rewards the biggest tiles lined up in order.
static inline float snake_value(board_t b, float rho) {
  static const int path[16] = {0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12};
  board_t s[8];
  bb::symmetries(b, s);
  float best = 0;
  for (int k = 0; k < 8; k++) {
    float v = 0, w = 1;
    for (int j = 0; j < 16; j++, w *= rho) {
      int r = bb::cell(s[k], path[j]);
      if (r) v += w * (float)(1u << r);
    }
    best = v > best ? v : best;
  }
  return best;
}

// Gradient line heuristic (the idea of macroxue/2048-ai's evaluation, reimplemented): a line read in its "descending"
// direction scores t(a0) + sum over neighbours of (t(a) + t(b) if a >= b else 12 * (t(a) - t(b))) + (t(a) if a == b),
// with t(r) = r * 2^r. Board value: max over the 8 symmetries of the sum over rows (left to right; with snake = true,
// odd rows right to left, as a snake path) and columns (top to bottom).
struct LineScore {
  float desc[65536];  // line packed as cells 0..3 in nibbles 0..3 (cell 0 = the line's start)
  LineScore() {
    auto t = [](int r) { return r ? (double)r * (double)(1u << r) : 0.0; };
    for (unsigned x = 0; x < 65536; x++) {
      int l[4] = {(int)(x & 15), (int)(x >> 4 & 15), (int)(x >> 8 & 15), (int)(x >> 12 & 15)};
      double sc = t(l[0]);
      for (int i = 0; i < 3; i++) {
        double a = t(l[i]), b = t(l[i + 1]);
        sc += a >= b ? a + b : (a - b) * 12;
        if (l[i] == l[i + 1]) sc += a;
      }
      desc[x] = (float)sc;
    }
  }
};
static inline float gradient_value(board_t b, bool snake, bool fixed = false) {
  static const LineScore L;
  board_t sy[8];
  bb::symmetries(b, sy);
  float best = -1e30f;
  for (int k = 0; k < (fixed ? 1 : 8); k++) {  // fixed: the top-left corner only
    board_t s = sy[k], t = bb::transpose(s);
    float v = 0;
    for (int r = 0; r < 4; r++) {
      unsigned row = (unsigned)(s >> (16 * r)) & 0xFFFF;
      if (snake && (r & 1)) row = ((row & 0xF) << 12) | ((row & 0xF0) << 4) | ((row >> 4) & 0xF0) | (row >> 12);
      v += L.desc[row];
      v += L.desc[(unsigned)(t >> (16 * r)) & 0xFFFF];  // column r, top to bottom
    }
    best = v > best ? v : best;
  }
  return best;
}

// Snake-order penalty (macroxue's line score along our snake): in the orientation that puts the largest tile at cell 0
// (the better of the two snakes from that corner), sum T(b) - T(a) over consecutive path cells (a then b) of the first k
// path cells whenever T(b) > T(a), with T(r) = r * 2^r (empty = 0). Zero for a strictly decreasing, gap-free chain; large
// when a small tile or a hole sits between big tiles. Boards whose largest tile is in no corner get the k = 16 maximum.
static inline float snake_break(board_t b, int k) {
  static const int path[16] = {0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12};
  board_t s[8];
  bb::symmetries(b, s);
  int mx = bb::max_rank(b);
  float best = -1;
  for (int j = 0; j < 8; j++) {
    if (bb::cell(s[j], 0) != mx) continue;
    float pen = 0;
    int a = mx;
    for (int i = 1; i < k; i++) {
      int c = bb::cell(s[j], path[i]);
      float ta = a ? (float)a * (float)(1u << a) : 0.0f, tc = c ? (float)c * (float)(1u << c) : 0.0f;
      if (tc > ta) pen += tc - ta;
      a = c;
    }
    if (best < 0 || pen < best) best = pen;
  }
  return best < 0 ? (float)mx * (float)(1u << mx) : best;
}

// Empty cells next to a big tile (rank >= max(6, max rank - 3)): where a new small tile would get stuck.
static inline int exposed_cells(board_t b) {
  int big = std::max(6, bb::max_rank(b) - 3), n = 0;
  uint64_t em = bb::empty_mask(b);
  for (uint64_t m = em; m; m &= m - 1) {
    int c = __builtin_ctzll(m) / 4, r = c / 4, k = c % 4;
    if ((k > 0 && bb::cell(b, c - 1) >= big) || (k < 3 && bb::cell(b, c + 1) >= big) ||
        (r > 0 && bb::cell(b, c - 4) >= big) || (r < 3 && bb::cell(b, c + 4) >= big))
      n++;
  }
  return n;
}

struct Evaluator {
  const nt::Net<float>* net = nullptr;
  const nt::Net<int16_t>* qnet = nullptr;  // quantized alternative
  const wpack::PackedNet* pnet = nullptr;  // packed alternative for serving (wpack.h; EngineConfig --packed)
  StageFn stages;
  bool downgrade = true;
  int min_gap = 10;
  float shaping = 0;  // value = network + shaping * heuristic (a shaping potential used in training)
  bool heuristic_only = false;
  float snake_rho = 0;  // >0: the heuristic is snake_value(rho) instead of nneonneo's
  // optional second network (own patterns and stages), combined by mean or min
  const nt::Net<int16_t>* qnet2 = nullptr;
  StageFn stages2;
  int ens_mode = 0;       // 0: none, 1: mean, 2: min, 3: replace (the second network alone)
  int ens_from_stage = 0; // combine only where the first network's stage is >= this
  // >0: leaves holding a tile of rank >= view_top are evaluated in their downgraded view
  // (downgrade_view(a, view_top, view_gap)), e.g. 14 lets the early-game network value 16384-phase
  // boards as the 8192-phase boards they mirror. The search itself runs on the real boards.
  int gradient = 0;           // >0: leaves below grad_max_sum use the gradient heuristic (1 rows L->R, 2 snake rows)
  uint32_t grad_max_sum = 0;  //     instead of the network (0: everywhere)
  int view_top = 0, view_gap = 10;
  uint32_t view_max_sum = 0;  // >0: only leaves whose tile sum is below this
  bool view_safe = false;     // choose gaps with downgrade_view_safe
  float snake_pen = 0;        // >0: leaves (view tile sum in [pen_lo, pen_hi)) lose snake_pen * snake_break(v, pen_k)
  int pen_k = 8;
  uint32_t pen_lo = 0, pen_hi = 0;
  // >0: leaves (view tile sum in [exp_lo, exp_hi)) lose exposed_pen per empty cell next to a big tile (rank >=
  // max(6, max rank - 3)): the concept experts keep low where they beat the engine (NOTES 2026-10-06)
  float exposed_pen = 0;
  uint32_t exp_lo = 0, exp_hi = 0;
  inline float operator()(board_t a) const {
    board_t v = downgrade ? eval_view(a, min_gap) : a;
    if (view_top && (!view_max_sum || tile_sum(v) < view_max_sum))
      v = view_safe ? downgrade_view_safe(v, view_top, view_gap) : downgrade_view(v, view_top, view_gap);
    float h = shaping != 0 ? shaping * (snake_rho > 0 ? snake_value(v, snake_rho) : bb::heuristic(v)) : 0;
    if (heuristic_only) return h;
    if (gradient && (!grad_max_sum || tile_sum(v) < grad_max_sum)) return gradient_value(v, gradient == 2, gradient == 3);
    int st = stages.of(v);
    float x = pnet ? pnet->eval(v, st) : qnet ? qnet->eval(v, st) : net->eval(v, st);
    if (qnet2 && st >= ens_from_stage) {
      float y = qnet2->eval(v, stages2.of(v));
      x = ens_mode == 3 ? y : ens_mode == 2 ? (x < y ? x : y) : 0.5f * (x + y);
    }
    if (snake_pen > 0) {
      uint32_t ts = tile_sum(v);
      if (ts >= pen_lo && ts < pen_hi) x -= snake_pen * snake_break(v, pen_k);
    }
    if (exposed_pen > 0) {
      uint32_t ts = tile_sum(v);
      if (ts >= exp_lo && ts < exp_hi) x -= exposed_pen * (float)exposed_cells(v);
    }
    return h + x;
  }
  int nstages() const { return pnet ? pnet->nstages : qnet ? qnet->nstages : net->nstages; }
  std::string patterns() const { return nt::pattern_string(pnet ? pnet->pats : qnet ? qnet->pats : net->pats); }

  // Per-cell attribution of the network value of afterstate a (same view and stage as operator()): every pattern
  // instance (pattern p on symmetry k) contributes its weight, split equally over the real cells it reads. The 16
  // cells sum to the network part of the value (the heuristic/shaping/penalty terms are not attributed).
  void attribute(board_t a, float out[16]) const {
    for (int i = 0; i < 16; i++) out[i] = 0;
    board_t v = downgrade ? eval_view(a, min_gap) : a;
    if (view_top && (!view_max_sum || tile_sum(v) < view_max_sum))
      v = view_safe ? downgrade_view_safe(v, view_top, view_gap) : downgrade_view(v, view_top, view_gap);
    int st = stages.of(v);
    // inv[k][c]: the real cell that cell c of symmetry k of the board came from (board with cell i holding i)
    static int inv[8][16];
    static bool init = [] {
      board_t id = 0;
      for (int i = 0; i < 16; i++) id |= (board_t)i << (4 * i);
      board_t sy[8];
      bb::symmetries(id, sy);
      for (int k = 0; k < 8; k++)
        for (int c = 0; c < 16; c++) inv[k][c] = bb::cell(sy[k], c);
      return true;
    }();
    (void)init;
    board_t sy[8];
    bb::symmetries(v, sy);
    const auto& pats = pnet ? pnet->pats : qnet ? qnet->pats : net->pats;
    for (size_t p = 0; p < pats.size(); p++) {
      size_t off = pnet ? 0 : (qnet ? qnet->offset[p] : net->offset[p]) + (size_t)st * (qnet ? qnet->stage_size : net->stage_size);
      float n = (float)pats[p].cells.size();
      for (int k = 0; k < 8; k++) {
        uint64_t idx = bb::pext_nib(sy[k], pats[p].mask);
        float w = pnet ? pnet->weight(st, p, idx) : qnet ? (float)qnet->w[off + idx] * qnet->scale[st] : net->w[off + idx];
        for (int c : pats[p].cells) out[inv[k][c]] += w / n;
      }
    }
  }
};

struct SearchParams {
  int min_depth = 1;
  int max_depth = 3;
  long budget = 0;        // leaf-eval budget for iterative deepening (0 = fixed max_depth)
  float prob_cut = 0.0f;  // prune chance outcomes whose path probability is below this
  int beam = 0;           // >0: at interior max nodes (depth >= 2) expand only the best `beam`
                          // moves by 1-ply value r + V(afterstate)
  long budget_hi = 0;     // larger budget for close calls: when iterative deepening would stop
  float close = 0.0f;     // and the two best moves differ by less than close * |best value|
  int corner_lock = 0;    // >0: when a tile of the max rank (>= this) sits in a corner, moves that
                          // leave no such tile in a corner are skipped (unless every move does)
  int chain_lock = 0;     // >0: when the board holds a snake chain of at least this many tiles (see
                          // chain_cells), moves that take a chain tile out of its cell are skipped
                          // (unless every move does); merges into the chain are fine
  int chain_min_rank = 10;  // only tiles of at least this rank count as chain (1024)
  float vprune = 0.0f;    // >0: forward pruning - an interior chance node whose afterstate's network value is below
                          // vprune * (the root's best afterstate value) is not expanded (treated as a leaf), so the
                          // budget goes to plausible lines and they are searched deeper
};

// Snake chain: in the orientation where the max tile is in the corner of the snake path (row 0
// left to right, row 1 right to left, ...), the longest strictly decreasing run of tiles from
// that corner. Returns a mask with 0xF over each chain cell (real frame) of the longest chain of
// at least kmin tiles over the 8 orientations, or 0.
static inline uint64_t chain_cells(board_t s, int kmin, int min_rank = 10) {
  static const int path[16] = {0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12};
  // cell index of path position p under orientation j (applied to the canonical frame)
  static int cellmap[8][16];
  static bool init = [] {
    for (int j = 0; j < 8; j++)
      for (int p = 0; p < 16; p++) {
        int c = path[p], r = c / 4, col = c % 4;
        // orientation j maps canonical (r, col) to the real cell: transpose for j >= 4, then
        // flips (bit 0: columns, bit 1: rows), inverse of eg::sym's board transform
        int rr = r, cc = col;
        if (j & 1) cc = 3 - cc;
        if (j & 2) rr = 3 - rr;
        if (j >= 4) std::swap(rr, cc);
        cellmap[j][p] = rr * 4 + cc;
      }
    return true;
  }();
  (void)init;
  int m = bb::max_rank(s), bestk = 0, bestj = -1;
  for (int j = 0; j < 8; j++) {
    int prev = bb::cell(s, cellmap[j][0]);
    if (prev != m || m == 0) continue;
    int k = 1;
    while (k < 16) {
      int v = bb::cell(s, cellmap[j][k]);
      if (v < min_rank || v >= prev) break;
      prev = v;
      k++;
    }
    if (k > bestk) bestk = k, bestj = j;
  }
  if (bestk < kmin) return 0;
  uint64_t mask = 0;
  for (int p = 0; p < bestk; p++) mask |= 0xFULL << (4 * cellmap[bestj][p]);
  return mask;
}
// true iff afterstate a keeps every chain cell of s occupied by a tile at least as big
static inline bool keeps_chain(board_t s, board_t a, uint64_t mask) {
  for (uint64_t m = mask; m; m &= ~(0xFULL << (__builtin_ctzll(m) & ~3))) {
    int sh = __builtin_ctzll(m) & ~3;
    if (((a >> sh) & 0xF) < ((s >> sh) & 0xF)) return false;
  }
  return true;
}

// Corner lock: the rank that must stay in a corner after a move from s (0: no constraint).
static inline int corner_max(board_t b) {
  int a = (int)(b & 0xF), c = (int)((b >> 12) & 0xF), d = (int)((b >> 48) & 0xF), e = (int)(b >> 60);
  return std::max(std::max(a, c), std::max(d, e));
}
static inline int lock_rank(board_t s, int lock) {
  if (!lock) return 0;
  int m = bb::max_rank(s);
  return m >= lock && corner_max(s) == m ? m : 0;
}
// Drops the afterstates that break the corner lock, unless all of them do; returns the new count.
template <class... Extra>
static inline int corner_filter(board_t s, int lock, int n, board_t* as, Extra*... extra) {
  int lr = lock_rank(s, lock);
  if (!lr) return n;
  int ok = 0;
  for (int i = 0; i < n; i++) ok += corner_max(as[i]) >= lr;
  if (ok == 0 || ok == n) return n;
  int k = 0;
  for (int i = 0; i < n; i++)
    if (corner_max(as[i]) >= lr) {
      as[k] = as[i];
      ((extra[k] = extra[i]), ...);
      k++;
    }
  return k;
}
// The chain lock (SearchParams::chain_lock), same contract as corner_filter.
template <class... Extra>
static inline int chain_filter(board_t s, int kmin, int min_rank, int n, board_t* as, Extra*... extra) {
  if (!kmin || n < 2) return n;
  uint64_t mask = chain_cells(s, kmin, min_rank);
  if (!mask) return n;
  bool keep[4];
  int ok = 0;
  for (int i = 0; i < n; i++) ok += keep[i] = keeps_chain(s, as[i], mask);
  if (ok == 0 || ok == n) return n;
  int k = 0;
  for (int i = 0; i < n; i++)
    if (keep[i]) {
      as[k] = as[i];
      ((extra[k] = extra[i]), ...);
      k++;
    }
  return k;
}

struct SearchStats {
  long evals = 0, nodes = 0;
  int depth = 0;
  long escalations = 0;  // moves that switched to the close-call budget
};

class Searcher {
 public:
  explicit Searcher(const Evaluator& ev, int tt_bits = 20) : ev_(ev), bits_(tt_bits) {
    tt_.assign(1ULL << bits_, Entry{~0ULL, 0.0f, 0});
  }
  // The root afterstates of the last search iteration and their searched values (expected future reward), for
  // search-bootstrapped training (play --dump-train).
  board_t last_after[4];
  float last_value[4];
  uint32_t last_reward[4];
  int last_dir[4];
  int last_n = 0;
  // TreeStrap-style samples: interior chance nodes (afterstate, searched value), each kept with probability
  // tree_rate / 65536 (a hash of the board decides, so revisits are not double-counted). Drained by the caller.
  uint32_t tree_rate = 0;
  std::vector<std::pair<board_t, float>> tree_samples;
  // Optional leaf oracle: returns true and sets *v to replace the network's value of afterstate a.
  bool (*leaf_oracle)(board_t a, float* v) = nullptr;

  // Returns the best direction (or -1 if no legal move) for state s.
  // With p.budget > 0: iterative deepening from min_depth, stopping before an
  // iteration whose predicted number of leaf evaluations exceeds the budget.
  // Otherwise a single search at max_depth.
  int best_move(board_t s, const SearchParams& p, SearchStats* st = nullptr, float* value = nullptr) {
    evals_ = nodes_ = 0;
    int best = -1, depth_done = 0;
    float bestv = 0, second = -1e30f;
    int start = p.budget > 0 ? p.min_depth : p.max_depth;
    long prev = 0, prev2 = 0, budget = p.budget;
    bool escalated = false;
    for (int d = start; d <= p.max_depth; d++) {
      if (budget > 0 && d > start) {
        double growth = prev2 > 0 ? (double)prev / prev2 : 6.0 * (bb::count_empty(s) + 1);
        if (growth < 1.5) growth = 1.5;
        if (prev * growth > budget) {
          // close call between the two best moves: allow a deeper look once
          bool close = second > -1e29f && bestv - second < p.close * fabsf(bestv);
          if (escalated || p.budget_hi <= budget || !close) break;
          budget = p.budget_hi;
          escalated = true;
          if (prev * growth > budget) break;
        }
      }
      long before = evals_;
      best = root(s, d, p, &bestv, &second);
      depth_done = d;
      prev2 = prev;
      prev = std::max(1L, evals_ - before);
      if (best < 0) break;
    }
    if (st) {
      st->evals += evals_;
      st->nodes += nodes_;
      st->depth = depth_done;
      st->escalations += escalated;
    }
    if (value) *value = bestv;
    return best;
  }

  // Value of each move at fixed depth (for analysis / UI). NaN for illegal moves.
  void move_values(board_t s, int depth, float out[4], const SearchParams& p) {
    for (int d = 0; d < 4; d++) {
      uint32_t r;
      board_t a = bb::move(s, d, r);
      out[d] = a == s ? NAN : r + chance(a, depth - 1, 1.0f, p);
    }
  }

 private:
  // Values depend only on (afterstate, depth), so entries stay valid across moves.
  struct Entry {
    board_t key;
    float value;
    int32_t depth;
  };
  const Evaluator& ev_;
  int bits_;
  std::vector<Entry> tt_;
  long evals_ = 0, nodes_ = 0;

  static inline uint64_t hash(board_t b) {
    b ^= b >> 33;
    b *= 0xff51afd7ed558ccdULL;
    b ^= b >> 33;
    return b;
  }

  int root(board_t s, int depth, const SearchParams& p, float* value, float* second) {
    int best = -1;
    float bestv = -1e30f, sec = -1e30f;
    board_t as[4];
    uint32_t rw[4];
    int dir[4], n = 0;
    for (int d = 0; d < 4; d++) {
      board_t a = bb::move(s, d, rw[n]);
      if (a == s) continue;
      as[n] = a, dir[n] = d, n++;
    }
    n = corner_filter(s, p.corner_lock, n, as, rw, dir);
    n = chain_filter(s, p.chain_lock, p.chain_min_rank, n, as, rw, dir);
    if (p.vprune > 0) {
      prune_ref_ = -1e30f;
      for (int i = 0; i < n; i++) prune_ref_ = std::max(prune_ref_, leaf_value(as[i]));
      prune_ref_ *= p.vprune;
    }
    last_n = 0;
    for (int i = 0; i < n; i++) {
      float c = chance(as[i], depth - 1, 1.0f, p);
      float v = rw[i] + c;
      last_after[last_n] = as[i], last_value[last_n] = c, last_reward[last_n] = rw[i], last_dir[last_n] = dir[i];
      last_n++;  // searched value of each root afterstate
      if (v > bestv) sec = bestv, bestv = v, best = dir[i];
      else if (v > sec) sec = v;
    }
    *value = best >= 0 ? bestv : 0;
    *second = sec;
    return best;
  }

  float max_node(board_t s, int depth, float prob, const SearchParams& p) {
    nodes_++;
    float best = 0;  // no legal move: game over, no further reward
    bool any = false;
    if (p.beam > 0 && depth >= 2) {
      board_t as[4];
      uint32_t rw[4];
      float q[4];
      int n = 0;
      for (int d = 0; d < 4; d++) {
        board_t a = bb::move(s, d, rw[n]);
        if (a == s) continue;
        as[n] = a;
        n++;
      }
      if (n == 0) return 0;
      n = corner_filter(s, p.corner_lock, n, as, rw);
      n = chain_filter(s, p.chain_lock, p.chain_min_rank, n, as, rw);
      for (int i = 0; i < n; i++) q[i] = rw[i] + chance(as[i], 0, prob, p);
      // keep the `beam` best by q (tiny n: selection by repeated max)
      int keep = n < p.beam ? n : p.beam;
      for (int k = 0; k < keep; k++) {
        int bi = k;
        for (int j = k + 1; j < n; j++)
          if (q[j] > q[bi]) bi = j;
        std::swap(as[k], as[bi]);
        std::swap(rw[k], rw[bi]);
        std::swap(q[k], q[bi]);
        float v = rw[k] + chance(as[k], depth - 1, prob, p);
        if (!any || v > best) best = v, any = true;
      }
      return best;
    }
    if (p.corner_lock || p.chain_lock) {
      board_t as[4];
      uint32_t rw[4];
      int n = 0;
      for (int d = 0; d < 4; d++) {
        board_t a = bb::move(s, d, rw[n]);
        if (a != s) as[n++] = a;
      }
      n = corner_filter(s, p.corner_lock, n, as, rw);
      n = chain_filter(s, p.chain_lock, p.chain_min_rank, n, as, rw);
      for (int i = 0; i < n; i++) {
        float v = rw[i] + chance(as[i], depth - 1, prob, p);
        if (!any || v > best) best = v, any = true;
      }
      return best;
    }
    for (int d = 0; d < 4; d++) {
      uint32_t r;
      board_t a = bb::move(s, d, r);
      if (a == s) continue;
      float v = r + chance(a, depth - 1, prob, p);
      if (!any || v > best) best = v, any = true;
    }
    return best;
  }

  float prune_ref_ = -1e30f;
  // network value of afterstate a, through the transposition table
  float leaf_value(board_t a) {
    Entry& e = tt_[hash(a) >> (64 - bits_)];
    if (e.key == a) return e.value;  // a leaf value or a deeper search: both fine
    evals_++;
    float v;
    if (!leaf_oracle || !leaf_oracle(a, &v)) v = ev_(a);
    e = Entry{a, v, 0};
    return v;
  }
  float chance(board_t a, int depth, float prob, const SearchParams& p) {
    if (depth <= 0 || prob < p.prob_cut) return leaf_value(a);
    if (p.vprune > 0) {
      float v0 = leaf_value(a);
      if (v0 < prune_ref_) return v0;  // clearly worse than the root's best: do not expand
    }
    Entry& e = tt_[hash(a ^ ((uint64_t)depth * 0x9E3779B97F4A7C15ULL)) >> (64 - bits_)];
    if (e.key == a && e.depth == depth) return e.value;
    nodes_++;
    uint64_t em = bb::empty_mask(a);
    int n = __builtin_popcountll(em);
    float sum = 0;
    float p2 = prob * 0.9f / n, p4 = prob * 0.1f / n;
    for (uint64_t m = em; m; m &= m - 1) {
      uint64_t bit = m & -m;
      sum += 0.9f * max_node(a | bit, depth, p2, p);
      sum += 0.1f * max_node(a | (bit << 1), depth, p4, p);
    }
    float v = sum / n;
    e = Entry{a, v, depth};
    if (tree_rate && (uint32_t)(hash(a ^ 0x5bd1e995ULL) >> 48) < tree_rate) tree_samples.emplace_back(a, v);
    return v;
  }
};
