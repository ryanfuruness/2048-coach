// Bitboard engine for 2048.
//
// A board is a 64-bit integer holding 16 cells of 4 bits each. Cell i (0..15,
// row-major, 0 = top-left) lives in bits [4i, 4i+4). A cell stores the tile's
// rank: 0 = empty, r = tile 2^r. Rank 15 (32768) is the largest representable
// rank: two rank-15 tiles merge (scoring 65536) into a rank-15 tile, i.e. the new
// 65536 is stored one rank down, as tile downgrading would. The real game uses
// Game in game.h, which maps larger tiles down before searching.
#pragma once
#include <cstdint>
#include <cstring>
#if defined(__BMI2__)
#include <immintrin.h>
#endif

typedef uint64_t board_t;

enum Dir { UP = 0, RIGHT = 1, DOWN = 2, LEFT = 3 };

namespace bb {

// Gathers the nibbles of x selected by m (m must consist of whole nibbles) into the low bits, lowest nibble first:
// PEXT where the CPU has BMI2, a portable nibble loop elsewhere (ARM, WASM, x86 builds without BMI2).
static inline uint64_t pext_nib(uint64_t x, uint64_t m) {
#if defined(__BMI2__)
  return _pext_u64(x, m);
#else
  uint64_t r = 0;
  int k = 0;
  while (m) {
    int sh = __builtin_ctzll(m) & ~3;
    r |= ((x >> sh) & 0xF) << (4 * k++);
    m &= ~(0xFULL << sh);
  }
  return r;
#endif
}
// The k-th (from 0) set bit of m, as a mask.
static inline uint64_t nth_bit(uint64_t m, int k) {
#if defined(__BMI2__)
  return _pdep_u64(1ULL << k, m);
#else
  for (int i = 0; i < k; i++) m &= m - 1;
  return m & (~m + 1);
#endif
}

struct Tables {
  uint16_t row_left[65536];
  uint16_t row_right[65536];
  uint64_t col_up[65536];    // xor-delta for a column, unpacked to column layout
  uint64_t col_down[65536];
  uint32_t score[65536];     // points earned when this row/column is moved
  Tables();
};
extern const Tables T;

static inline int cell(board_t b, int i) { return (b >> (4 * i)) & 0xF; }
static inline board_t set_cell(board_t b, int i, int v) {
  return (b & ~(0xFULL << (4 * i))) | ((board_t)v << (4 * i));
}

static inline board_t transpose(board_t x) {
  board_t a1 = x & 0xF0F00F0FF0F00F0FULL;
  board_t a2 = x & 0x0000F0F00000F0F0ULL;
  board_t a3 = x & 0x0F0F00000F0F0000ULL;
  board_t a = a1 | (a2 << 12) | (a3 >> 12);
  board_t b1 = a & 0xFF00FF0000FF00FFULL;
  board_t b2 = a & 0x00FF00FF00000000ULL;
  board_t b3 = a & 0x00000000FF00FF00ULL;
  return b1 | (b2 >> 24) | (b3 << 24);
}
// mirror columns (c -> 3-c)
static inline board_t flip_h(board_t b) {
  b = ((b & 0x00FF00FF00FF00FFULL) << 8) | ((b >> 8) & 0x00FF00FF00FF00FFULL);
  return ((b & 0x0F0F0F0F0F0F0F0FULL) << 4) | ((b >> 4) & 0x0F0F0F0F0F0F0F0FULL);
}
// mirror rows (r -> 3-r)
static inline board_t flip_v(board_t b) {
  return (b << 48) | ((b & 0xFFFF0000ULL) << 16) | ((b >> 16) & 0xFFFF0000ULL) | (b >> 48);
}
// All 8 symmetries of the square.
static inline void symmetries(board_t b, board_t out[8]) {
  board_t t = transpose(b);
  out[0] = b;
  out[1] = flip_h(b);
  out[2] = flip_v(b);
  out[3] = flip_h(out[2]);
  out[4] = t;
  out[5] = flip_h(t);
  out[6] = flip_v(t);
  out[7] = flip_h(out[6]);
}

// One bit (bit 4i) set per empty cell.
static inline uint64_t empty_mask(board_t x) {
  x |= (x >> 2) & 0x3333333333333333ULL;
  x |= (x >> 1);
  return ~x & 0x1111111111111111ULL;
}
static inline int count_empty(board_t x) { return __builtin_popcountll(empty_mask(x)); }

static inline int max_rank(board_t b) {
  int m = 0;
  for (int i = 0; i < 16; i++, b >>= 4) {
    int v = b & 0xF;
    if (v > m) m = v;
  }
  return m;
}

// Moves. Return the resulting board; the move is legal iff result != input.
static inline board_t move_left(board_t b, uint32_t& score) {
  board_t r = 0;
  score = 0;
  for (int i = 0; i < 4; i++) {
    unsigned row = (b >> (16 * i)) & 0xFFFF;
    r |= (board_t)T.row_left[row] << (16 * i);
    score += T.score[row];
  }
  return r;
}
static inline board_t move_right(board_t b, uint32_t& score) {
  board_t r = 0;
  score = 0;
  for (int i = 0; i < 4; i++) {
    unsigned row = (b >> (16 * i)) & 0xFFFF;
    r |= (board_t)T.row_right[row] << (16 * i);
    score += T.score[row];
  }
  return r;
}
static inline board_t move_up(board_t b, uint32_t& score) {
  board_t t = transpose(b), r = b;
  score = 0;
  for (int i = 0; i < 4; i++) {
    unsigned col = (t >> (16 * i)) & 0xFFFF;
    r ^= T.col_up[col] << (4 * i);
    score += T.score[col];
  }
  return r;
}
static inline board_t move_down(board_t b, uint32_t& score) {
  board_t t = transpose(b), r = b;
  score = 0;
  for (int i = 0; i < 4; i++) {
    unsigned col = (t >> (16 * i)) & 0xFFFF;
    r ^= T.col_down[col] << (4 * i);
    score += T.score[col];
  }
  return r;
}
static inline board_t move(board_t b, int dir, uint32_t& score) {
  switch (dir) {
    case UP: return move_up(b, score);
    case RIGHT: return move_right(b, score);
    case DOWN: return move_down(b, score);
    default: return move_left(b, score);
  }
}
static inline board_t move(board_t b, int dir) {
  uint32_t s;
  return move(b, dir, s);
}
static inline bool can_move(board_t b) {
  for (int d = 0; d < 4; d++)
    if (move(b, d) != b) return true;
  return false;
}

// ---- random numbers (xoshiro256**) ----
struct Rng {
  uint64_t s[4];
  static uint64_t splitmix(uint64_t& x) {
    uint64_t z = (x += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
  }
  explicit Rng(uint64_t seed = 1) { reseed(seed); }
  void reseed(uint64_t seed) {
    for (int i = 0; i < 4; i++) s[i] = splitmix(seed);
  }
  static inline uint64_t rotl(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }
  inline uint64_t next() {
    uint64_t r = rotl(s[1] * 5, 7) * 9, t = s[1] << 17;
    s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3];
    s[2] ^= t; s[3] = rotl(s[3], 45);
    return r;
  }
  // uniform in [0, n)
  inline uint32_t below(uint32_t n) { return (uint32_t)(((next() >> 32) * (uint64_t)n) >> 32); }
  inline double uniform() { return (next() >> 11) * (1.0 / 9007199254740992.0); }
};

// Place a random tile (2 w.p. 0.9, 4 w.p. 0.1) on a random empty cell.
static inline board_t spawn(board_t b, Rng& rng) {
  uint64_t em = empty_mask(b);
  int n = __builtin_popcountll(em);
  if (n == 0) return b;
  uint64_t bit = nth_bit(em, (int)rng.below(n));
  board_t tile = rng.below(10) == 0 ? 2 : 1;
  return b | (bit * tile);
}
static inline board_t initial_board(Rng& rng) { return spawn(spawn(0, rng), rng); }

// Hand-made heuristic (nneonneo's 2048 AI): per row/column a score for empty cells, merges,
// monotonicity and a penalty on large tiles; used as a shaping potential for the network.
extern float heur_row[65536];
static inline float heuristic(board_t b) {
  board_t t = transpose(b);
  float h = 0;
  for (int i = 0; i < 4; i++) h += heur_row[(b >> (16 * i)) & 0xFFFF] + heur_row[(t >> (16 * i)) & 0xFFFF];
  return h;
}

// Sum of tile values (monotone in time: each spawn adds 2 or 4).
static inline uint64_t tile_sum(board_t b) {
  uint64_t s = 0;
  for (int i = 0; i < 16; i++, b >>= 4)
    if (b & 0xF) s += 1ULL << (b & 0xF);
  return s;
}

}  // namespace bb
