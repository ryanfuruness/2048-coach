// Layered exact DP for endgame sub-games too large for the memoised tables of endgame.h.
//
// Same sub-game as eg::Table: locked cells hold a chain that must not move; the free cells hold
// tiles capped per cell; the goal is a goal-rank tile in a goal cell right after a move. The
// free cells' tile sum never changes in a move and grows by 2 or 4 with every spawn, so the
// states can be solved one tile-sum layer at a time, from the largest sum down, with only the
// two layers above in memory. Every configuration within the caps is solved (no reachability
// search) and written to disk, one uint16 per state (14-bit probability, 2-bit move) in
// combinatorial rank order inside each layer. Lookups read single entries with pread, so a
// table of tens of GB costs no RAM at play time.
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <fcntl.h>
#include <unistd.h>

#include <memory>

#include "board.h"
#include "endgame.h"

namespace lt {

struct Spec {
  int n = 0;            // free cells
  int cells[16] = {};   // free cell of index digit i
  int cap[16] = {};     // largest rank of index digit i
  board_t chain = 0;    // tiles of the locked cells (all other cells empty)
  uint64_t lock_mask = 0;
  uint16_t goal = 0;    // bit c: a goal-rank tile in cell c after a move wins
  int goal_rank = 0;
};

// Units of 2: u(r) = tile value / 2.
static inline int unit(int r) { return r ? 1 << (r - 1) : 0; }

class Index {
 public:
  explicit Index(const Spec& s) : sp_(s) {
    smax_ = 0;
    for (int i = 0; i < s.n; i++) smax_ += unit(s.cap[i]);
    // C[i][t]: configurations of digits i..n-1 with sum t
    C_.assign((size_t)(s.n + 1) * (smax_ + 1), 0);
    C(s.n, 0) = 1;
    for (int i = s.n - 1; i >= 0; i--)
      for (int t = 0; t <= smax_; t++) {
        uint64_t c = 0;
        for (int r = 0; r <= s.cap[i] && unit(r) <= t; r++) c += C(i + 1, t - unit(r));
        C(i, t) = c;
      }
    // PR[i][t][r] = configurations with digit i < r (same prefix, same remaining sum t)
    PR_.assign((size_t)s.n * (smax_ + 1) * 16, 0);
    for (int i = 0; i < s.n; i++)
      for (int t = 0; t <= smax_; t++) {
        uint64_t acc = 0;
        for (int r = 0; r < 16; r++) {
          PR(i, t, r) = acc;
          if (r <= s.cap[i] && unit(r) <= t) acc += C(i + 1, t - unit(r));
        }
      }
    base_.assign(smax_ + 2, 0);
    for (int t = 0; t <= smax_; t++) base_[t + 1] = base_[t] + C(0, t);
  }
  const Spec& spec() const { return sp_; }
  int smax() const { return smax_; }
  uint64_t layer_size(int t) const { return C(0, t); }
  uint64_t base(int t) const { return base_[t]; }
  uint64_t total() const { return base_[smax_ + 1]; }

  // Sum (units) of b's free cells, or -1 if a free cell is above its cap.
  int sum(board_t b) const {
    int t = 0;
    for (int i = 0; i < sp_.n; i++) {
      int r = bb::cell(b, sp_.cells[i]);
      if (r > sp_.cap[i]) return -1;
      t += unit(r);
    }
    return t;
  }
  // Rank of b's free configuration inside layer t (t = sum(b)).
  uint64_t rank(board_t b, int t) const {
    uint64_t idx = 0;
    for (int i = 0; i < sp_.n; i++) {
      int r = bb::cell(b, sp_.cells[i]);
      idx += PR(i, t, r);
      t -= unit(r);
    }
    return idx;
  }
  // The board (chain + free cells) of entry idx of layer t.
  board_t unrank(uint64_t idx, int t) const {
    board_t b = sp_.chain;
    for (int i = 0; i < sp_.n; i++) {
      int r = 0;
      // largest r with PR <= idx and a non-empty block
      for (int q = sp_.cap[i]; q >= 0; q--)
        if (unit(q) <= t && PR(i, t, q) <= idx && C(i + 1, t - unit(q)) > 0) { r = q; break; }
      idx -= PR(i, t, r);
      t -= unit(r);
      b |= (board_t)r << (4 * sp_.cells[i]);
    }
    return b;
  }

 private:
  Spec sp_;
  int smax_;
  std::vector<uint64_t> C_, PR_, base_;
  uint64_t& C(int i, int t) { return C_[(size_t)i * (smax_ + 1) + t]; }
  uint64_t C(int i, int t) const { return C_[(size_t)i * (smax_ + 1) + t]; }
  uint64_t& PR(int i, int t, int r) { return PR_[((size_t)i * (smax_ + 1) + t) * 16 + r]; }
  uint64_t PR(int i, int t, int r) const { return PR_[((size_t)i * (smax_ + 1) + t) * 16 + r]; }
};

// The sub-game of eg::Snake for k locked path cells and goal rank r; free cells in snake-path order,
// capped at r unless caps (one per free cell, in path order) is given.
static const int kSnakePath[16] = {0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12};
// path: the 16 cells in chain order (default: the 4-wide snake; e.g. a 3-wide snake with column 3 as a free buffer is
// 0,1,2,6,5,4,8,9,10,14,13,12,15,11,7,3 - macroxue's PDF block)
static inline Spec snake_spec(int k, int r, const std::vector<int>& caps, const int* path = kSnakePath) {
  Spec s;
  uint16_t locked = 0;
  for (int j = 0; j < k; j++) {
    locked |= 1 << path[j];
    int v = r + (k - 1 - j);
    s.chain = bb::set_cell(s.chain, path[j], v > 15 ? 15 : v);
    s.lock_mask |= 0xFULL << (4 * path[j]);
  }
  int end = path[k - 1];
  for (int c = 0; c < 16; c++) {
    if (locked >> c & 1) continue;
    int dr = c / 4 - end / 4, dc = c % 4 - end % 4;
    if (dr * dr + dc * dc == 1) s.goal |= 1 << c;
  }
  s.goal_rank = r;
  for (int j = k; j < 16; j++) {
    s.cells[s.n] = path[j];
    s.cap[s.n] = caps.empty() ? r : caps[j - k];
    s.n++;
  }
  return s;
}

static constexpr float kScale = 16000.0f;  // as eg::Table: 14-bit probability

// Read-only access to a solved table on disk.
class Table {
 public:
  Table(const Spec& s, const std::string& path) : ix_(s) {
    fd_ = open(path.c_str(), O_RDONLY);
  }
  ~Table() {
    if (fd_ >= 0) close(fd_);
  }
  bool ok() const { return fd_ >= 0; }
  const Index& index() const { return ix_; }
  // Probability and best move of state b (chain in place, before a move); -1 if b is outside.
  float lookup(board_t b, int* move) const {
    if ((b & ix_.spec().lock_mask) != ix_.spec().chain) return -1.0f;
    int t = ix_.sum(b);
    if (t < 0) return -1.0f;
    uint64_t off = (ix_.base(t) + ix_.rank(b, t)) * 2;
    uint16_t e;
    if (pread(fd_, &e, 2, (off_t)off) != 2) return -1.0f;
    *move = e >> 14;
    return (e & 0x3FFF) / kScale;
  }

 private:
  Index ix_;
  int fd_ = -1;
};

// Does the board s (in some frame) hold the layered table's chain shape: the first k snake-path cells
// strictly decreasing from the board's largest tile and ending exactly at the goal rank, with at most one
// drop of two ranks (winning then collapses the tail into the missing tile, e.g. [32768 8192 4096 2048 1024]
// + 1024 -> [32768 16384])? The table's sub-game does not depend on the locked ranks (they only must not
// move and stay above the free caps), so s is mapped onto the table's own chain.
static inline bool shape(board_t s, const Spec& sp, board_t* canon) {
  static const int path[16] = {0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12};
  int k = 16 - sp.n;
  int prev = bb::cell(s, path[0]);
  if (prev != bb::max_rank(s)) return false;
  int gaps = 0;
  for (int j = 1; j < k; j++) {
    int v = bb::cell(s, path[j]);
    if (prev - v == 2) gaps++;
    else if (prev - v != 1) return false;
    prev = v;
  }
  if (prev != sp.goal_rank || gaps > 1) return false;
  *canon = (s & ~sp.lock_mask) | sp.chain;
  return true;
}
// rank_lo/rank_hi (optional, per table): use table t only when the real board's largest tile rank is in [lo, hi].
static inline int suggest(const std::vector<std::unique_ptr<Table>>& ltabs, board_t b, float* prob,
                          const int* rank_lo = nullptr, const int* rank_hi = nullptr, int real_max = 0) {
  float best = -1.0f;
  int best_dir = -1;
  for (int t = 0; t < (int)ltabs.size(); t++)
  for (int j = 0; j < 8; j++) {
    if (rank_lo && (real_max < rank_lo[t] || real_max > rank_hi[t])) break;
    const Spec& sp = ltabs[t]->index().spec();
    board_t sj = eg::sym(b, j), s;
    if (!shape(sj, sp, &s)) continue;
    int m = 0;
    float p = ltabs[t]->lookup(s, &m);
    if (p <= best) continue;
    board_t a = bb::move(s, m);
    if (a == s) continue;
    // the real move with the same effect: the same free cells afterwards and the real chain unmoved (the table's
    // board carries its own chain ranks, so whole boards differ unless the real chain is the table's)
    for (int d = 0; d < 4; d++) {
      board_t ad = bb::move(b, d);
      if (ad == b) continue;
      board_t adj = eg::sym(ad, j);
      if (((adj ^ a) & ~sp.lock_mask) == 0 && ((adj ^ sj) & sp.lock_mask) == 0) {
        best = p, best_dir = d;
        break;
      }
    }
  }
  *prob = best;
  return best_dir;
}

}  // namespace lt
