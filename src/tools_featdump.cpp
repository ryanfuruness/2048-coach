// value and simple features of positions (hex win sum per line) -> CSV
#include <cstdio>
#include <cstring>
#include "board.h"
#include "ntuple.h"
#include "search.h"
int main(int argc, char** argv) {
  nt::Net<float> net; net.load(argv[1]);
  char hex[32]; int win; long sum;
  printf("v1,empty,distinct_small,tiny,chain,maxfree,ntiles,win,sum\n");
  while (scanf("%31s %d %ld", hex, &win, &sum) == 3) {
    board_t b = 0;
    for (int c = 0; c < 16; c++) { char ch = hex[c]; int v = ch <= '9' ? ch - '0' : ch - 'a' + 10; b = bb::set_cell(b, c, v); }
    board_t as[4]; uint32_t rw[4]; int n = 0;
    for (int d = 0; d < 4; d++) { board_t x = bb::move(b, d, rw[n]); if (x != b) as[n++] = x; }
    n = corner_filter(b, 14, n, as, rw);
    float best = -1e30f;
    for (int i = 0; i < n; i++) { float v = rw[i] + net.eval(as[i], 0); if (v > best) best = v; }
    if (n == 0) best = 0;
    int empty = bb::count_empty(b), tiny = 0, ntiles = 0, maxfree = 0; unsigned seen = 0;
    uint64_t chain = chain_cells(b, 1, 9);  // snake chain of tiles >= 512 from the max tile
    int clen = __builtin_popcountll(chain) / 4;
    for (int c = 0; c < 16; c++) {
      int r = bb::cell(b, c);
      if (!r) continue;
      ntiles++;
      if (r <= 5) tiny++;
      bool in_chain = (chain >> (4 * c)) & 0xF;
      if (!in_chain) { if (r <= 9) seen |= 1u << r; if (r > maxfree) maxfree = r; }
    }
    printf("%.0f,%d,%d,%d,%d,%d,%d,%d,%ld\n", best, empty, __builtin_popcount(seen), tiny, clen, maxfree, ntiles, win, sum);
  }
}
