// The real game (unbounded tile ranks) and its mapping onto 4-bit search boards.
#pragma once
#include <array>
#include <cstdint>
#include <string>
#include "board.h"

struct Game {
  std::array<uint8_t, 16> r{};  // rank per cell, 0 = empty
  uint64_t score = 0;
  long moves = 0;

  static int slide(uint8_t* line[4], uint64_t& gained) {
    uint8_t vals[4];
    int n = 0;
    for (int j = 0; j < 4; j++)
      if (*line[j]) vals[n++] = *line[j];
    uint8_t out[4] = {0, 0, 0, 0};
    int m = 0;
    for (int j = 0; j < n; j++) {
      if (j + 1 < n && vals[j] == vals[j + 1]) {
        out[m++] = vals[j] + 1;
        gained += 1ULL << (vals[j] + 1);
        j++;
      } else {
        out[m++] = vals[j];
      }
    }
    int changed = 0;
    for (int j = 0; j < 4; j++) {
      changed |= *line[j] != out[j];
      *line[j] = out[j];
    }
    return changed;
  }
  // Applies a move; returns false (and leaves the game unchanged) if it is illegal.
  bool apply(int dir) {
    Game g = *this;
    uint64_t gained = 0;
    int changed = 0;
    for (int k = 0; k < 4; k++) {
      uint8_t* line[4];
      for (int j = 0; j < 4; j++) {
        int row, col;
        switch (dir) {
          case UP: row = j; col = k; break;
          case DOWN: row = 3 - j; col = k; break;
          case LEFT: row = k; col = j; break;
          default: row = k; col = 3 - j; break;
        }
        line[j] = &g.r[row * 4 + col];
      }
      changed |= slide(line, gained);
    }
    if (!changed) return false;
    g.score += gained;
    g.moves++;
    *this = g;
    return true;
  }
  bool can_move() const {
    for (int d = 0; d < 4; d++) {
      Game g = *this;
      if (g.apply(d)) return true;
    }
    return false;
  }
  void spawn(bb::Rng& rng) {
    int empt[16], n = 0;
    for (int i = 0; i < 16; i++)
      if (!r[i]) empt[n++] = i;
    if (!n) return;
    int c = empt[rng.below(n)];
    r[c] = rng.below(10) == 0 ? 2 : 1;
  }
  void reset(bb::Rng& rng) {
    r.fill(0);
    score = 0;
    moves = 0;
    spawn(rng);
    spawn(rng);
  }
  uint64_t tile_sum() const {
    uint64_t s = 0;
    for (int v : r) s += v ? 1ULL << v : 0;
    return s;
  }
  int max_rank() const {
    int m = 0;
    for (int v : r) m = v > m ? v : m;
    return m;
  }
  std::string str() const {
    std::string s;
    for (int i = 0; i < 16; i++) {
      char buf[16];
      snprintf(buf, sizeof buf, "%6d", r[i] ? 1 << r[i] : 0);
      s += buf;
      if (i % 4 == 3) s += '\n';
    }
    return s;
  }
};

// Safe gaps for map_search_board (`--map-safe`, workstream late 2026-10-07; off by default): prefer a gap g whose rank
// g-1 holds at most one tile (as downgrade_view_safe). Otherwise two tiles of rank g-1 can merge into g at once and
// collide with the lowered tile above, e.g. 16384 . 16384 . / ... with a 65536: the new 32768 and the 65536 would
// both be rank 15 (fuzz workstream).
inline bool g_map_safe_gap = false;

// Like to_search_board, but never clamps: if the board does not fit with gaps >= min_gap, smaller gaps are used (down
// to rank 1), and back[r] gets the real rank of search rank r (for showing real tile values). Returns false only if
// the board cannot fit at all (more than 15 distinct ranks).
static inline bool map_search_board(const Game& g, board_t* out, int back[16]) {
  int distinct = 0;
  {
    bool seen[32] = {false};
    for (int v : g.r)
      if (v && !seen[v]) seen[v] = true, distinct++;
  }
  if (distinct > 15) return false;
  for (int min_gap = 8; min_gap >= 1; min_gap--) {
    int map[32];
    for (int i = 0; i < 32; i++) map[i] = i;
    int cnt[32] = {0}, maxv = 0;
    for (int v : g.r) cnt[v]++, maxv = v > maxv ? v : maxv;
    auto view_count = [&](int k) {
      int c = 0;
      for (int v = 1; v <= maxv; v++)
        if (map[v] == k) c += cnt[v];
      return c;
    };
    bool ok = true;
    while (map[maxv] > 15) {
      int gap = -1;
      if (g_map_safe_gap)
        for (int k = map[maxv] - 1; k >= min_gap; k--)
          if (!view_count(k) && view_count(k - 1) <= 1) { gap = k; break; }
      if (gap < 0)
        for (int k = map[maxv] - 1; k >= min_gap; k--)
          if (!view_count(k)) { gap = k; break; }
      if (gap < 0) { ok = false; break; }
      for (int v = 1; v <= maxv; v++)
        if (map[v] > gap) map[v]--;
    }
    if (!ok) continue;
    board_t b = 0;
    for (int r = 0; r < 16; r++) back[r] = r;
    for (int i = 0; i < 16; i++) {
      int v = g.r[i] ? map[g.r[i]] : 0;
      b |= (board_t)v << (4 * i);
      if (g.r[i]) back[v] = g.r[i];
    }
    // search ranks between real ones (merge results) map to the rank above the lower real neighbour
    for (int r = 1; r < 16; r++)
      if (back[r] == r && r > 0 && back[r - 1] != r - 1) back[r] = back[r - 1] + 1;
    *out = b;
    return true;
  }
  return false;
}

// Maps the real board onto a 4-bit search board. The mapping is exact whenever the
// board fits (all ranks <= 15; two 32768s merge on search boards too). Otherwise
// tiles are "downgraded": the largest rank g >= min_gap absent from the board is
// found and every rank above g is lowered by one, until the board fits. Equal
// tiles stay equal and order is preserved, so the legal moves are unchanged.
// (Only needed once a 65536 exists; ranks that still do not fit are clamped.)
static inline board_t to_search_board(const Game& g, int min_gap = 8) {
  int map[32];
  for (int i = 0; i < 32; i++) map[i] = i;
  int cnt[32] = {0};
  for (int v : g.r) cnt[v]++;
  int maxv = 0;
  for (int v = 1; v < 32; v++)
    if (cnt[v]) maxv = v;
  auto view_count = [&](int k) {
    int c = 0;
    for (int v = 1; v <= maxv; v++)
      if (map[v] == k) c += cnt[v];
    return c;
  };
  for (;;) {
    int top = map[maxv];
    if (top <= 15) break;
    int gap = -1;
    for (int k = top - 1; k >= min_gap; k--)
      if (!view_count(k)) { gap = k; break; }
    if (gap < 0) break;
    for (int v = 1; v <= maxv; v++)
      if (map[v] > gap) map[v]--;
  }
  board_t b = 0;
  for (int i = 0; i < 16; i++) {
    int v = g.r[i] ? map[g.r[i]] : 0;
    if (v > 15) v = 15;
    b |= (board_t)v << (4 * i);
  }
  return b;
}
