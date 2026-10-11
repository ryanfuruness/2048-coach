// Block formation (workstream pdf, 2026-10-07).
//
// Some strong players keep their biggest tiles in a 3x2 block touching a corner (the "PDF" block of macroxue's
// 2048-ai) instead of a snake along an edge. Our engine is a snake player: its values in block positions carry no
// information about the experts' moves there (expert disputes: 105 of 150 came from one block player; claimed 21%
// value loss, real -1%). This header detects the formation, so that analysis can treat such positions differently,
// and defines the cells of the block for the exact block tables.
//
// Detector (fitted on workstream mx's labeled expert positions, results/pdf/report.txt): the 4 biggest tiles (with
// multiplicity) all lie inside one 3x2 block that touches a corner, and the 4th biggest is at most 6 ranks below the
// biggest (>= max / 64); or the 3 biggest in a corner 2x2 square (3rd >= max / 8). Snake chains fail both: their
// biggest tiles run along one edge.
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>

#include "board.h"
#include "endgame.h"
#include "layered.h"

namespace blk {

// The 8 placements of a 3x2 block touching a corner (cells, row-major from the top-left).
inline constexpr int kPlacements[8][6] = {
    {0, 1, 2, 4, 5, 6},      {1, 2, 3, 5, 6, 7},      // rows 0-1, cols 0-2 / 1-3
    {8, 9, 10, 12, 13, 14},  {9, 10, 11, 13, 14, 15}, // rows 2-3
    {0, 1, 4, 5, 8, 9},      {4, 5, 8, 9, 12, 13},    // cols 0-1, rows 0-2 / 1-3
    {2, 3, 6, 7, 10, 11},    {6, 7, 10, 11, 14, 15},  // cols 2-3
};

// Index of the placement holding the k biggest ranks of r[16] (with multiplicity), the k-th biggest being at most
// `gap` ranks below the biggest; -1 if none. r: real ranks (may exceed 15).
inline int block_placement(const int r[16], int k = 4, int gap = 6) {
  int s[16];
  std::copy(r, r + 16, s);
  std::sort(s, s + 16, [](int a, int b) { return a > b; });
  if (k < 1 || k > 6 || s[k - 1] <= 0 || s[k - 1] < s[0] - gap) return -1;
  for (int p = 0; p < 8; p++) {
    int t[6];
    for (int i = 0; i < 6; i++) t[i] = r[kPlacements[p][i]];
    std::sort(t, t + 6, [](int a, int b) { return a > b; });
    if (std::equal(t, t + k, s)) return p;
  }
  return -1;
}

// Ranks of board b, through `real_rank` (search rank -> real rank, e.g. analyze's display map for boards with tiles
// above 32768) when given.
inline void ranks_of(board_t b, int out[16], const int* real_rank = nullptr) {
  for (int i = 0; i < 16; i++) {
    int v = bb::cell(b, i);
    out[i] = v && real_rank ? real_rank[v] : v;
  }
}

// The block's core: the 3 biggest ranks of r[16] (with multiplicity) in a 2x2 square at a corner, the 3rd at most
// core_gap ranks below the biggest (catches block positions whose 4th tile is still small, e.g. 8192 32768 / 256
// 16384). A snake chain fails it: its 3 biggest tiles run along one edge.
inline bool block_core(const int r[16], int core_gap = 3) {
  static const int sq[4][4] = {{0, 1, 4, 5}, {2, 3, 6, 7}, {8, 9, 12, 13}, {10, 11, 14, 15}};
  int s[16];
  std::copy(r, r + 16, s);
  std::sort(s, s + 16, [](int a, int b) { return a > b; });
  if (core_gap < 0 || s[2] <= 0 || s[2] < s[0] - core_gap) return false;
  for (auto& q : sq) {
    int t[4] = {r[q[0]], r[q[1]], r[q[2]], r[q[3]]};
    std::sort(t, t + 4, [](int a, int b) { return a > b; });
    if (std::equal(t, t + 3, s)) return true;
  }
  return false;
}

inline bool in_block(board_t b, const int* real_rank = nullptr, int k = 4, int gap = 6, int core_gap = 3) {
  int r[16];
  ranks_of(b, r, real_rank);
  return block_placement(r, k, gap) >= 0 || block_core(r, core_gap);
}

// True when b is in the block formation, or (moves_ahead = 1) one of its legal moves leads into it: the 4 biggest
// tiles in a corner 3x2 block (4th >= max/64) or the 3 biggest in a corner 2x2 square (3rd >= max/8; core_gap -1
// turns this off). Measured (results/pdf/report.txt; moves_ahead 0): the block player's expert disputes 97/105,
// snake experts' positions 2/185 (one genuine block game), our engine's own late positions 1.0%, other experts'
// 16384+ positions <= 0.3%. Use it at max tile >= 16384 (the strong tier's short early chains sit in a corner block
// 4% of the time at 8192).
inline bool block_formation(board_t b, int moves_ahead = 0, const int* real_rank = nullptr, int k = 4, int gap = 6,
                            int core_gap = 3) {
  if (in_block(b, real_rank, k, gap, core_gap)) return true;
  if (moves_ahead > 0)
    for (int d = 0; d < 4; d++) {
      board_t a = bb::move(b, d);
      if (a != b && in_block(a, real_rank, k, gap, core_gap)) return true;
    }
  return false;
}

// How complete the block is: 6 when the 6 biggest tiles fill a corner 3x2 block (6th >= max/1024), 4 when
// block_formation holds (4 biggest in the block or 3 biggest in its 2x2 core), else 0. --block-lock keeps the level:
// in the formation the engine plays the best searched move whose afterstate keeps the same level (or at least 4).
inline int block_level(board_t b, const int* real_rank = nullptr) {
  int r[16];
  ranks_of(b, r, real_rank);
  if (block_placement(r, 6, 10) >= 0) return 6;
  return block_placement(r, 4, 6) >= 0 || block_core(r) ? 4 : 0;
}
// The --block-lock choice among searched root moves (dirs[i], values[i]); -1 to keep the search's move.
inline int lock_choice(board_t b, int n, const int* dirs, const float* values) {
  int lv = block_level(b);
  if (lv == 0) return -1;
  for (int need : {lv, 4}) {
    int bd = -1;
    float bv = -1e30f;
    for (int i = 0; i < n; i++) {
      if (block_level(bb::move(b, dirs[i])) < need) continue;
      if (values[i] > bv) bv = values[i], bd = dirs[i];
    }
    if (bd >= 0) return bd;
    if (need == 4) break;
  }
  return -1;
}

// ---- exact block tables ----
// The sub-game, as for the snake tables (endgame.h, layered.h): the 6 block cells hold the 6 biggest tiles and must
// not move; the 10 free cells build a tile equal to the block's smallest tile (the end) in a free cell next to it.
// Success doubles the end tile. Canonical frame: block = cells 0 1 2 / 4 5 6. The block player keeps the end at cell 6
// (goal cells 7 and 10: 92% of their block positions) or at cell 4 (goal cell 8: 7.5%). The table's sub-game does not
// depend on the other block tiles (they only must not move), so any order inside the block matches.
inline constexpr int kBlockCells[6] = {0, 1, 2, 4, 5, 6};
// lt::snake_spec path: the block cells with the end last, then the free cells (nearest the goal first).
inline const int* block_path(int end) {
  static const int p6[16] = {0, 1, 2, 4, 5, 6, 7, 10, 3, 11, 9, 14, 15, 8, 13, 12};
  static const int p4[16] = {0, 1, 2, 6, 5, 4, 8, 9, 12, 13, 10, 14, 11, 15, 7, 3};
  return end == 4 ? p4 : p6;
}
// Free-cell caps in path order: r-1 (a free tile of the goal rank only counts in a goal cell), the free cell farthest
// from the goal r-2.
inline std::vector<int> block_caps(int r) {
  std::vector<int> c(10, r - 1);
  c[9] = r - 2;
  return c;
}
inline lt::Spec block_spec(int end, int r) { return lt::snake_spec(6, r, block_caps(r), block_path(end)); }
inline std::string table_name(int end, int r) { return "block_e" + std::to_string(end) + "_r" + std::to_string(r) + ".lt"; }

// Does s (canonical frame) hold table sp's shape: the end cell holds the goal rank and the other 5 block cells hold
// larger tiles (the free cells' caps are checked by the lookup)? canon: s with the table's own block tiles.
inline bool shape(board_t s, const lt::Spec& sp, int end, board_t* canon) {
  int r = sp.goal_rank;
  if (bb::cell(s, end) != r) return false;
  for (int c : kBlockCells)
    if (c != end && bb::cell(s, c) <= r) return false;
  *canon = (s & ~sp.lock_mask) | sp.chain;
  return true;
}

struct Tables {
  std::vector<std::unique_ptr<lt::Table>> t;
  std::vector<int> end;
  bool empty() const { return t.empty(); }
  // Loads every table block_e{4,6}_r{3..10}.lt present in dir; returns the number loaded.
  int load(const std::string& dir) {
    int n = 0;
    for (int e : {6, 4})
      for (int r = 3; r <= 10; r++) {
        std::string f = dir + "/" + table_name(e, r);
        FILE* fp = fopen(f.c_str(), "rb");
        if (!fp) continue;
        fclose(fp);
        t.emplace_back(new lt::Table(block_spec(e, r), f));
        end.push_back(e);
        n++;
      }
    return n;
  }
};

// Best block-table move for board b and its success probability, or -1 (as lt::suggest).
inline int suggest(const Tables& T, board_t b, float* prob) {
  float best = -1.0f;
  int best_dir = -1;
  for (int i = 0; i < (int)T.t.size(); i++)
    for (int j = 0; j < 8; j++) {
      const lt::Spec& sp = T.t[i]->index().spec();
      board_t sj = eg::sym(b, j), s;
      if (!shape(sj, sp, T.end[i], &s)) continue;
      int m = 0;
      float p = T.t[i]->lookup(s, &m);
      if (p <= best) continue;
      board_t a = bb::move(s, m);
      if (a == s) continue;
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

// Sub-game success probability after each move of b (afterstate value over the random tile) under the block table and
// frame that match b with the highest state value; -1 for illegal moves and moves that move the block. Returns the
// matching state's probability (-1: no table applies). As lt_move_values (engine.h) for the snake tables.
inline float move_values(const Tables& T, board_t b, float out[4]) {
  for (int d = 0; d < 4; d++) out[d] = -1.0f;
  float best = -1.0f;
  for (int i = 0; i < (int)T.t.size(); i++)
    for (int j = 0; j < 8; j++) {
      const lt::Table& tab = *T.t[i];
      const lt::Spec& sp = tab.index().spec();
      board_t sj = eg::sym(b, j), s;
      if (!shape(sj, sp, T.end[i], &s)) continue;
      int m = 0;
      float p = tab.lookup(s, &m);
      if (p <= best) continue;
      best = p;
      for (int d = 0; d < 4; d++) {
        out[d] = -1.0f;
        board_t ad = bb::move(b, d);
        if (ad == b) continue;
        board_t adj = eg::sym(ad, j);
        if (((adj ^ sj) & sp.lock_mask) != 0) continue;  // the block moved: outside the sub-game
        board_t a = (adj & ~sp.lock_mask) | sp.chain;
        bool won = false;
        for (uint16_t g = sp.goal; g; g &= g - 1)
          if (bb::cell(a, __builtin_ctz(g)) == sp.goal_rank) won = true;
        if (won) {
          out[d] = 1.0f;
          continue;
        }
        if (tab.index().sum(a) < 0) {
          out[d] = 0.0f;
          continue;
        }
        uint64_t em = bb::empty_mask(a);
        int n = __builtin_popcountll(em);
        float sum = 0.0f;
        for (uint64_t mm = em; mm; mm &= mm - 1) {
          uint64_t bit = mm & -mm;
          int mv;
          float v2 = tab.lookup(a | bit, &mv), v4 = tab.lookup(a | (bit << 1), &mv);
          sum += 0.9f * (v2 > 0 ? v2 : 0.0f) + 0.1f * (v4 > 0 ? v4 : 0.0f);
        }
        out[d] = n ? sum / n : 0.0f;
      }
    }
  return best;
}

}  // namespace blk
