// Human move model (workstream hm), data step: for every position (hex board, engine encoding) and legal move, the
// 1-ply value exactly as soft_move computes it (reward + network value of the afterstate's view) and the concept
// features of the afterstate (explain.h), plus the same features of the position itself (row d = -1). Input for the
// human move model fits (scripts/hm_fit.py).
//
//   build/hm_tool [--preset best-notables|best] [engine flags] < IN.tsv > OUT.tsv
//   build/hm_tool --probs MODEL.txt < IN2.tsv > OUT2.tsv   (check of src/human.h against the Python fit)
//   IN2: "id hex theta hl m1 m2 ... m_hl" (the player's last hl <= 20 moves, oldest first, 0-3 = U R D L)
//        -> "id p_U p_R p_D p_L" (the human model's move probabilities)
//
// IN: "id <TAB> hex" per line ("id ..." header lines skipped). OUT (TSV with a header): one row per (position, d):
//   id d reward q max_rank corner chain_len chain_ranks empty merges trapped big_off_edge corner_dist exposed moved
//   q2 death
// d = -1: the position itself (reward 0, q 0, moved 0); d = 0..3 (U R D L): legal moves only; moved = cells whose
// content changed; q2 = 2-ply value: reward + expectation over the spawn (2: 0.9, 4: 0.1, uniform over the empty
// cells) of the best reply's 1-ply value (0 when no reply is possible); death = the share of spawns with no reply.
#include <cstdio>
#include <algorithm>
#include <cstring>
#include <string>

#include "engine.h"
#include "explain.h"
#include "human.h"

static Engine E;

int main(int argc, char** argv) {
  E.cfg.preset_best(".", false);
  std::string probs_model;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    if (a == "--probs" && i + 1 < argc) {
      probs_model = argv[++i];
    } else if (a == "--preset" && i + 1 < argc) {
      std::string p = argv[++i];
      E.cfg = EngineConfig();
      E.cfg.preset_best(".", p == "best");
    } else if (!E.cfg.parse(i, argc, argv)) {
      fprintf(stderr, "unknown option %s\n", a.c_str());
      return 1;
    }
  }
  if (!E.load(false)) return 1;
  if (!probs_model.empty()) {
    hm::Model M;
    if (probs_model != "default" && !M.load(probs_model)) {
      fprintf(stderr, "cannot read %s\n", probs_model.c_str());
      return 1;
    }
    char line[4096], id[4000], hex[64];
    int hl, used;
    double th;
    while (fgets(line, sizeof line, stdin)) {
      if (sscanf(line, "%3999s %63s %lf %d%n", id, hex, &th, &hl, &used) != 4 || strlen(hex) != 16) continue;
      hm::History hist;
      char* q = line + used;
      for (int k = 0; k < hl; k++) {
        int d, u2;
        if (sscanf(q, "%d%n", &d, &u2) != 1) break;
        hist.push(d);
        q += u2;
      }
      board_t b = 0;
      for (int c = 0; c < 16; c++) {
        char ch = hex[c];
        b = bb::set_cell(b, c, ch <= '9' ? ch - '0' : ch - 'a' + 10);
      }
      double p[4];
      hm::probs(E, M, b, hist, th, p);
      printf("%s\t%.6f\t%.6f\t%.6f\t%.6f\n", id, p[0], p[1], p[2], p[3]);
    }
    return 0;
  }
  printf("id\td\treward\tq\tmax_rank\tcorner\tchain_len\tchain_ranks\tempty\tmerges\ttrapped\tbig_off_edge\tcorner_dist"
         "\texposed\tmoved\tq2\tdeath\n");
  char line[4096];
  long n = 0;
  while (fgets(line, sizeof line, stdin)) {
    char id[4000], hex[64];
    if (sscanf(line, "%3999s %63s", id, hex) != 2 || strcmp(id, "id") == 0 || strlen(hex) != 16) continue;
    board_t b = 0;
    for (int c = 0; c < 16; c++) {
      char ch = hex[c];
      int v = ch <= '9' ? ch - '0' : ch - 'a' + 10;
      b = bb::set_cell(b, c, v);
    }
    auto row = [&](int d, uint32_t r, double q, board_t x, int moved, double q2, double death) {
      ex::Features f = ex::features(x);
      printf("%s\t%d\t%u\t%.1f\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%.1f\t%.4f\n", id, d, r, q, f.max_rank,
             (int)f.corner, f.chain_len, f.chain_ranks, f.empty, f.merges, f.trapped, f.big_off_edge, f.corner_dist,
             f.exposed, moved, q2, death);
    };
    // 2-ply: expectation over spawns of the best reply's 1-ply value
    auto two_ply = [&](board_t a, double* death) {
      double tot = 0, dead = 0;
      int ne = 0;
      for (int c = 0; c < 16; c++) {
        if (bb::cell(a, c)) continue;
        ne++;
        for (int k = 1; k <= 2; k++) {
          double pk = k == 1 ? 0.9 : 0.1;
          board_t s2 = bb::set_cell(a, c, k);
          double best = -1e300;
          bool any = false;
          for (int d2 = 0; d2 < 4; d2++) {
            uint32_t r2 = 0;
            board_t a2 = bb::move(s2, d2, r2);
            if (a2 == s2) continue;
            any = true;
            best = std::max(best, (double)r2 + E.ev(E.view(a2)));
          }
          if (!any) dead += pk, best = 0;
          tot += pk * best;
        }
      }
      if (!ne) { *death = 0; return 0.0; }
      *death = dead / ne;
      return tot / ne;
    };
    row(-1, 0, 0.0, b, 0, 0.0, 0.0);
    for (int d = 0; d < 4; d++) {
      uint32_t r = 0;
      board_t a = bb::move(b, d, r);
      if (a == b) continue;
      int moved = 0;
      for (int c = 0; c < 16; c++) moved += bb::cell(a, c) != bb::cell(b, c);
      double death = 0, q2 = r + two_ply(a, &death);
      row(d, r, r + E.ev(E.view(a)), a, moved, q2, death);
    }
    n++;
  }
  fprintf(stderr, "%ld positions\n", n);
  return 0;
}
