// Explores endgame sub-games (src/endgame.h) on the snake path: the first k cells of the path
// hold a decreasing chain whose smallest tile has rank r; the free cells must make another
// rank-r tile next to it.
//
// usage: endgame --k K --rank R [--cap C] [--starts N] [--seed S]
// Prints the table size, time and memory, and the success probability from N random
// positions with only small tiles in the free region.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "endgame.h"

static const int kSnake[16] = {0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12};

static void show(board_t b) {
  for (int r = 0; r < 4; r++) {
    for (int c = 0; c < 4; c++) {
      int v = bb::cell(b, r * 4 + c);
      printf("%6d", v ? 1 << v : 0);
    }
    printf("\n");
  }
}

// Snake matcher: the same ending in all 8 orientations must give the same probability, and
// the suggested move must keep the chain in place.
static int selftest() {
  board_t b = 0;
  const int chain[6] = {14, 13, 12, 11, 10, 9};
  for (int j = 0; j < 6; j++) b = bb::set_cell(b, eg::Snake::kPath[j], chain[j]);
  const int rest[][2] = {{5, 8}, {4, 7}, {8, 3}, {9, 2}, {10, 1}, {12, 1}, {13, 2}};
  for (auto& c : rest) b = bb::set_cell(b, c[0], c[1]);
  show(b);
  int max_rank[17] = {0};
  for (int k = 6; k <= 16; k++) max_rank[k] = std::min(16 - k, k == 6 ? 9 : 8);
  eg::Snake sn(6, max_rank);
  int fails = 0;
  float p0 = -1;
  for (int j = 0; j < 8; j++) {
    board_t bj = eg::sym(b, j);
    float p;
    int d = sn.suggest(bj, &p);
    board_t a = d >= 0 ? bb::move(bj, d) : bj;
    // chain cells of bj: the image of the canonical chain under symmetry j
    bool kept = true;
    for (int c = 0; c < 6; c++) {
      board_t one = bb::set_cell(0, eg::Snake::kPath[c], 1);
      board_t img = eg::sym(one, j);
      int cell = __builtin_ctzll(img) / 4;
      kept &= bb::cell(a, cell) == bb::cell(bj, cell);
    }
    printf("symmetry %d: p %.4f move %c chain kept %d\n", j, p, d >= 0 ? "URDL"[d] : '-', kept);
    if (p0 < 0) p0 = p;
    fails += (d < 0) || !kept || std::fabs(p - p0) > 1e-4f;
  }
  printf("%s\n", fails ? "SELFTEST FAILED" : "selftest ok");
  return fails != 0;
}

// Simulates the table policy from random starts and compares the empirical success rate with
// the table's probability (checks the DP).
static int verify(int k, int rank, int starts, int sims) {
  int max_rank[17] = {0};
  for (int kk = 6; kk <= 16; kk++) max_rank[kk] = std::min(16 - kk, kk == 6 ? 9 : 8);
  eg::Snake sn(k, max_rank);
  bb::Rng rng(7);
  double sp = 0, se = 0;
  for (int i = 0; i < starts; i++) {
    board_t b = 0;
    for (int j = 0; j < k; j++) b = bb::set_cell(b, eg::Snake::kPath[j], rank + (k - 1 - j));
    int ntiles = 2 + rng.below(5);
    for (int j = 0; j < ntiles; j++) {
      int c;
      do c = eg::Snake::kPath[k + rng.below(16 - k)];
      while (bb::cell(b, c));
      b = bb::set_cell(b, c, 1 + rng.below(std::min(rank, 6)));
    }
    float p;
    int d = sn.suggest(b, &p);
    if (d < 0) { i--; continue; }
    int wins = 0;
    for (int t = 0; t < sims; t++) {
      board_t s = b;
      for (;;) {
        float q;
        int m = sn.suggest(s, &q);
        if (m < 0) break;  // no table move (lost, or the chain changed)
        board_t a = bb::move(s, m);
        // won: the goal tile is next to the chain end (the chain is still intact)
        int end = eg::Snake::kPath[k - 1];
        bool won = false;
        for (int c = 0; c < 16; c++) {
          int dr = c / 4 - end / 4, dc = c % 4 - end % 4;
          if (dr * dr + dc * dc == 1 && bb::cell(a, end) == rank && bb::cell(a, c) == rank) won = true;
        }
        if (won) { wins++; break; }
        s = bb::spawn(a, rng);
      }
    }
    sp += p, se += (double)wins / sims;
    if (i < 5) printf("start %d: table p %.4f  simulated %.4f\n", i, p, (double)wins / sims);
  }
  printf("k=%d rank=%d: mean table p %.4f  mean simulated %.4f  (%d starts x %d)\n", k, rank, sp / starts,
         se / starts, starts, sims);
  return 0;
}

// Reads boards (16 hex digits, cell 0 first) from stdin; prints each one's table probability
// (full-collapse snake endings with >= 6 locked tiles, one missing rank allowed), or -1.
static int query(int full) {
  int max_rank[17] = {0};
  for (int kk = 6; kk <= 16; kk++) max_rank[kk] = std::min(16 - kk, kk == 6 ? 9 : 8);
  eg::Snake sn(6, max_rank, full);
  char line[256];
  while (fgets(line, sizeof line, stdin)) {
    board_t b = 0;
    for (int i = 0; i < 16; i++) {
      char c = line[i];
      int v = c <= '9' ? c - '0' : c - 'a' + 10;
      b |= (board_t)v << (4 * i);
    }
    float p;
    int d = sn.suggest(b, &p);
    printf("%.4f\n", d >= 0 ? p : -1.0f);
    fflush(stdout);
  }
  return 0;
}

int main(int argc, char** argv) {
  if (argc > 1 && std::string(argv[1]) == "--selftest") return selftest();
  if (argc > 1 && std::string(argv[1]) == "--query") return query(argc > 2 ? std::stoi(argv[2]) : 2);
  if (argc > 1 && std::string(argv[1]) == "--verify")
    return verify(std::stoi(argv[2]), std::stoi(argv[3]), std::stoi(argv[4]), std::stoi(argv[5]));
  int k = 8, rank = 7, cap = -1, starts = 1000;
  std::string caps;  // optional per-path-position caps after the chain, e.g. "10,9,9,8,8,8,8,7,7,7,7"
  uint64_t seed = 1;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    auto next = [&]() { return std::string(argv[++i]); };
    if (a == "--k") k = std::stoi(next());
    else if (a == "--rank") rank = std::stoi(next());
    else if (a == "--cap") cap = std::stoi(next());
    else if (a == "--caps") caps = next();
    else if (a == "--starts") starts = std::stoi(next());
    else if (a == "--seed") seed = std::stoull(next());
  }
  if (cap < 0) cap = rank;
  eg::Spec s;
  board_t chain = 0;
  for (int j = 0; j < k; j++) {
    s.locked |= 1 << kSnake[j];
    chain = bb::set_cell(chain, kSnake[j], rank + (k - 1 - j));
  }
  int end = kSnake[k - 1];
  std::vector<int> cv;
  for (size_t p = 0; p < caps.size();) {
    size_t q = caps.find(',', p);
    if (q == std::string::npos) q = caps.size();
    cv.push_back(std::stoi(caps.substr(p, q - p)));
    p = q + 1;
  }
  for (int c = 0; c < 16; c++) {
    if (s.locked >> c & 1) continue;
    s.cap[c] = cap;
    for (int j = k; j < 16; j++)
      if (kSnake[j] == c && j - k < (int)cv.size()) s.cap[c] = cv[j - k];
    int dr = c / 4 - end / 4, dc = c % 4 - end % 4;
    if (dr * dr + dc * dc == 1) s.goal |= 1 << c;
  }
  s.goal_rank = rank;
  for (int i = 0; i < 16; i++) s.order[i] = kSnake[i];
  eg::Table t(s, chain);
  printf("k=%d rank=%d cap=%d: %d free cells, index space %llu\n", k, rank, cap, t.free_cells(),
         (unsigned long long)t.size());
  show(chain);
  bb::Rng rng(seed);
  double sum = 0;
  auto t0 = std::chrono::steady_clock::now();
  for (int i = 0; i < starts; i++) {
    // a few small tiles in the free region
    board_t b = chain;
    int ntiles = 2 + rng.below(4);
    for (int j = 0; j < ntiles; j++) {
      int c;
      do c = rng.below(16);
      while ((s.locked >> c & 1) || bb::cell(b, c));
      b = bb::set_cell(b, c, 1 + rng.below(3));
    }
    int mv;
    float p = t.solve(b, &mv);
    sum += p;
    if (i < 2) {
      printf("start %d: p=%.4f move %d\n", i, p, mv);
      show(b);
    }
    if ((i + 1) % (starts / 10 > 0 ? starts / 10 : 1) == 0) {
      double el = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
      printf("%5d starts  mean p %.4f  entries %ld  memory %.0f MB  %.1fs\n", i + 1, sum / (i + 1), t.entries(),
             t.chunk_bytes() / 1e6, el);
      fflush(stdout);
    }
  }
  return 0;
}
