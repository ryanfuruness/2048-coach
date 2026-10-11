// Block formation tools (workstream pdf, 2026-10-07).
//
//   block_tool detect [k gap]       stdin: one position per line, 16 real ranks (any separators; 65536 = 16);
//                                   prints "<in_block> <in_block or one move ahead>" (the second is -1 when a rank
//                                   exceeds 15: moves need the 4-bit board)
//   block_tool pool FILE [every]    a .bin pool / start file (8-byte boards): share in the formation
//   block_tool spec END R           arguments for build/layered that solve the block table (end cell END, goal rank R)
//   block_tool query DIR            stdin: boards (16 hex rank digits, or 16 tile values); prints the block tables'
//                                   move and probability and the per-move success probabilities
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "block.h"

using namespace std;

int main(int argc, char** argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: block_tool detect [k gap] | pool FILE [every]\n");
    return 1;
  }
  string mode = argv[1];
  if (mode == "detect") {
    int k = argc > 2 ? atoi(argv[2]) : 4, gap = argc > 3 ? atoi(argv[3]) : 6;
    char line[4096];
    while (fgets(line, sizeof line, stdin)) {
      int r[16], n = 0;
      for (char* p = line; *p && n < 16;) {
        if (*p >= '0' && *p <= '9') {
          r[n++] = (int)strtol(p, &p, 10);
        } else {
          p++;
        }
      }
      if (n < 16) continue;
      bool small = true;
      board_t b = 0;
      for (int i = 0; i < 16; i++) {
        if (r[i] > 15) small = false;
        else b = bb::set_cell(b, i, r[i]);
      }
      int d0 = blk::block_placement(r, k, gap) >= 0 || blk::block_core(r);
      int d1 = small ? (int)blk::block_formation(b, 1, nullptr, k, gap) : -1;
      printf("%d %d\n", d0, d1);
    }
    return 0;
  }
  if (mode == "pool") {
    FILE* f = fopen(argv[2], "rb");
    if (!f) { perror(argv[2]); return 1; }
    int every = argc > 3 ? atoi(argv[3]) : 1;
    vector<board_t> v;
    board_t b;
    while (fread(&b, 8, 1, f) == 1) v.push_back(b);
    fclose(f);
    long n = 0, h0 = 0, h1 = 0;
    for (size_t i = 0; i < v.size(); i += every) {
      n++;
      h0 += blk::block_formation(v[i], 0);
      h1 += blk::block_formation(v[i], 1);
    }
    printf("%s: %ld boards, in block %ld (%.2f%%), in or one move from %ld (%.2f%%)\n", argv[2], n, h0, 100.0 * h0 / n, h1,
           100.0 * h1 / n);
    return 0;
  }
  if (mode == "spec") {
    int e = atoi(argv[2]), r = atoi(argv[3]);
    const int* p = blk::block_path(e);
    std::vector<int> c = blk::block_caps(r);
    printf("--k 6 --rank %d --path", r);
    for (int i = 0; i < 16; i++) printf("%c%d", i ? ',' : ' ', p[i]);
    printf(" --caps");
    for (size_t i = 0; i < c.size(); i++) printf("%c%d", i ? ',' : ' ', c[i]);
    printf("\n");
    return 0;
  }
  if (mode == "query") {
    blk::Tables T;
    int n = T.load(argv[2]);
    fprintf(stderr, "%d block tables loaded from %s\n", n, argv[2]);
    char line[4096];
    while (fgets(line, sizeof line, stdin)) {
      string t = line;
      while (!t.empty() && (t.back() == '\n' || t.back() == '\r' || t.back() == ' ')) t.pop_back();
      if (t.empty()) continue;
      board_t b = 0;
      if (t.size() == 16 && t.find_first_not_of("0123456789abcdef") == string::npos) {
        for (int i = 0; i < 16; i++) b = bb::set_cell(b, i, t[i] <= '9' ? t[i] - '0' : t[i] - 'a' + 10);
      } else {
        int k = 0;
        for (const char* p = t.c_str(); *p && k < 16;) {
          if (*p >= '0' && *p <= '9') {
            long v = strtol(p, (char**)&p, 10);
            int r = 0;
            while (v > 1) v >>= 1, r++;
            b = bb::set_cell(b, k++, r);
          } else p++;
        }
      }
      float pr;
      int d = blk::suggest(T, b, &pr);
      float mv[4];
      float ps = blk::move_values(T, b, mv);
      printf("%016llx block %d  move %c p %.4f  state %.4f  U %.4f R %.4f D %.4f L %.4f\n", (unsigned long long)b,
             (int)blk::block_formation(b), d >= 0 ? "URDL"[d] : '-', pr, ps, mv[0], mv[1], mv[2], mv[3]);
    }
    return 0;
  }
  fprintf(stderr, "unknown mode %s\n", mode.c_str());
  return 1;
}
