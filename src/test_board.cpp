// Cross-checks the bitboard move tables against a straightforward array implementation.
#include <cstdio>
#include <cstdlib>
#include "board.h"

using namespace bb;

// Naive reference: grid[r][c], slide toward direction.
static board_t naive_move(board_t b, int dir, uint32_t& score) {
  int g[4][4];
  for (int i = 0; i < 16; i++) g[i / 4][i % 4] = cell(b, i);
  score = 0;
  for (int k = 0; k < 4; k++) {
    // collect the line in the order tiles travel toward
    int idx[4][2];
    for (int j = 0; j < 4; j++) {
      int r, c;
      switch (dir) {
        case UP: r = j; c = k; break;
        case DOWN: r = 3 - j; c = k; break;
        case LEFT: r = k; c = j; break;
        default: r = k; c = 3 - j; break;
      }
      idx[j][0] = r; idx[j][1] = c;
    }
    int vals[4], n = 0;
    for (int j = 0; j < 4; j++) {
      int v = g[idx[j][0]][idx[j][1]];
      if (v) vals[n++] = v;
    }
    int out[4] = {0, 0, 0, 0}, m = 0;
    for (int j = 0; j < n; j++) {
      if (j + 1 < n && vals[j] == vals[j + 1]) {
        out[m++] = vals[j] < 15 ? vals[j] + 1 : 15;
        score += 1u << (vals[j] + 1);
        j++;
      } else {
        out[m++] = vals[j];
      }
    }
    for (int j = 0; j < 4; j++) g[idx[j][0]][idx[j][1]] = out[j];
  }
  board_t r = 0;
  for (int i = 0; i < 16; i++) r |= (board_t)g[i / 4][i % 4] << (4 * i);
  return r;
}

int main() {
  Rng rng(12345);
  long errors = 0;
  for (long t = 0; t < 5000000; t++) {
    board_t b = 0;
    // random boards with a mix of empties and small/large ranks
    for (int i = 0; i < 16; i++) {
      int v = rng.below(3) == 0 ? 0 : (int)rng.below(16);
      if (rng.below(4) == 0) v = rng.below(4);
      b |= (board_t)v << (4 * i);
    }
    for (int d = 0; d < 4; d++) {
      uint32_t s1, s2;
      board_t r1 = move(b, d, s1), r2 = naive_move(b, d, s2);
      if (r1 != r2 || s1 != s2) {
        if (errors++ < 5)
          printf("mismatch dir %d board %016llx: %016llx/%u vs %016llx/%u\n", d, (unsigned long long)b,
                 (unsigned long long)r1, s1, (unsigned long long)r2, s2);
      }
    }
    // symmetry sanity: transpose twice, flips twice
    if (transpose(transpose(b)) != b || flip_h(flip_h(b)) != b || flip_v(flip_v(b)) != b) errors++;
    // transpose maps cell (r,c) -> (c,r)
    board_t tb = transpose(b);
    for (int i = 0; i < 16; i++)
      if (cell(tb, (i % 4) * 4 + i / 4) != cell(b, i)) { errors++; break; }
    board_t fh = flip_h(b), fv = flip_v(b);
    for (int i = 0; i < 16; i++) {
      int r = i / 4, c = i % 4;
      if (cell(fh, r * 4 + 3 - c) != cell(b, i) || cell(fv, (3 - r) * 4 + c) != cell(b, i)) { errors++; break; }
    }
    int ne = 0;
    for (int i = 0; i < 16; i++) ne += cell(b, i) == 0;
    if (ne != count_empty(b)) errors++;
  }
  // spawn distribution sanity
  long twos = 0, fours = 0;
  for (int t = 0; t < 1000000; t++) {
    board_t b = spawn(0x1111111111111110ULL, rng);  // only cell 0 empty
    if (cell(b, 0) == 1) twos++; else if (cell(b, 0) == 2) fours++; else errors++;
  }
  printf("spawn: p(4) = %.4f\n", fours / (double)(twos + fours));
  printf("%s (%ld errors)\n", errors ? "FAIL" : "PASS", errors);
  return errors ? 1 : 0;
}
