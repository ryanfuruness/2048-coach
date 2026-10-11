#include "board.h"
#include <algorithm>
#include <cmath>

namespace bb {

static uint16_t reverse_row(uint16_t r) {
  return (uint16_t)(((r & 0xF) << 12) | ((r & 0xF0) << 4) | ((r >> 4) & 0xF0) | (r >> 12));
}
static uint64_t unpack_col(uint16_t r) {
  uint64_t x = r;
  return (x & 0xF) | ((x & 0xF0) << 12) | ((x & 0xF00) << 24) | ((x & 0xF000) << 36);
}

Tables::Tables() {
  for (unsigned r = 0; r < 65536; r++) {
    unsigned line[4] = {r & 0xF, (r >> 4) & 0xF, (r >> 8) & 0xF, (r >> 12) & 0xF};
    unsigned out[4] = {0, 0, 0, 0};
    int n = 0;
    bool last_merged = true;  // the tile at out[n-1] may not merge again
    uint32_t sc = 0;
    for (int i = 0; i < 4; i++) {
      if (!line[i]) continue;
      if (n > 0 && !last_merged && out[n - 1] == line[i]) {
        // two 32768s make a 65536, stored as rank 15 (one rank down, like tile downgrading)
        sc += 1u << (out[n - 1] + 1);
        if (out[n - 1] < 15) out[n - 1]++;
        last_merged = true;
      } else {
        out[n++] = line[i];
        last_merged = false;
      }
    }
    uint16_t res = (uint16_t)(out[0] | (out[1] << 4) | (out[2] << 8) | (out[3] << 12));
    row_left[r] = res;
    score[r] = sc;
  }
  for (unsigned r = 0; r < 65536; r++) {
    uint16_t rev = reverse_row((uint16_t)r);
    row_right[r] = reverse_row(row_left[rev]);
    col_up[r] = unpack_col(row_left[r]) ^ unpack_col((uint16_t)r);
    col_down[r] = unpack_col(row_right[r]) ^ unpack_col((uint16_t)r);
  }
}

const Tables T;

float heur_row[65536];
static struct HeurInit {
  HeurInit() {
    const double LOST = 200000, MONO_POW = 4, MONO_W = 47, SUM_POW = 3.5, SUM_W = 11, MERGE_W = 700, EMPTY_W = 270;
    for (unsigned r = 0; r < 65536; r++) {
      int line[4] = {(int)(r & 0xF), (int)((r >> 4) & 0xF), (int)((r >> 8) & 0xF), (int)((r >> 12) & 0xF)};
      double sum = 0;
      int empty = 0, merges = 0, prev = 0, counter = 0;
      for (int i = 0; i < 4; i++) {
        int rank = line[i];
        sum += pow(rank, SUM_POW);
        if (rank == 0) {
          empty++;
        } else {
          if (prev == rank) counter++;
          else if (counter > 0) merges += 1 + counter, counter = 0;
          prev = rank;
        }
      }
      if (counter > 0) merges += 1 + counter;
      double mono_left = 0, mono_right = 0;
      for (int i = 1; i < 4; i++) {
        if (line[i - 1] > line[i]) mono_left += pow(line[i - 1], MONO_POW) - pow(line[i], MONO_POW);
        else mono_right += pow(line[i], MONO_POW) - pow(line[i - 1], MONO_POW);
      }
      heur_row[r] = (float)(LOST + EMPTY_W * empty + MERGE_W * merges - MONO_W * std::min(mono_left, mono_right) - SUM_W * sum);
    }
  }
} heur_init;

}  // namespace bb
