// Search-bootstrapped value training ("distillation"): fits one stage of a weight file to (afterstate, value) targets
// recorded by `play --dump-train` (the searched value of each root afterstate: expected future reward after depth-1
// more plies of expectimax with the tables), so the network learns what the search knows.
//
//   distill --load IN.w --stage S --data FILE [FILE...] --out OUT.w [--alpha A] [--epochs E] [--seed N]
//
// Plain SGD, value += alpha * (target - value) per sample (spread over the 64 features), samples shuffled each epoch.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <string>
#include <vector>

#include "board.h"
#include "ntuple.h"

using namespace std;

struct Rec {
  board_t a;
  float v;
};

int main(int argc, char** argv) {
  string load, out;
  vector<string> data;
  int stage = 0, epochs = 2;
  int center = 0;  // --center BIN: subtract the mean (target - V) of each tile-sum bin of width BIN before fitting
  double alpha = 0.1;
  uint64_t seed = 1;
  for (int i = 1; i < argc; i++) {
    string a = argv[i];
    auto next = [&]() -> string {
      if (i + 1 >= argc) { fprintf(stderr, "missing value for %s\n", a.c_str()); exit(1); }
      return argv[++i];
    };
    if (a == "--load") load = next();
    else if (a == "--stage") stage = stoi(next());
    else if (a == "--out") out = next();
    else if (a == "--alpha") alpha = stod(next());
    else if (a == "--epochs") epochs = stoi(next());
    else if (a == "--seed") seed = stoull(next());
    else if (a == "--center") center = stoi(next());
    else if (a == "--data") {
      while (i + 1 < argc && argv[i + 1][0] != '-') data.push_back(argv[++i]);
    } else { fprintf(stderr, "unknown option %s\n", a.c_str()); return 1; }
  }
  if (load.empty() || out.empty() || data.empty()) {
    fprintf(stderr, "usage: distill --load IN.w --stage S --data FILE... --out OUT.w [--alpha A] [--epochs E]\n");
    return 1;
  }
  vector<Rec> recs;
  for (auto& f : data) {
    FILE* fp = fopen(f.c_str(), "rb");
    if (!fp) { fprintf(stderr, "cannot read %s\n", f.c_str()); return 1; }
    Rec r;
    while (fread(&r.a, sizeof(board_t), 1, fp) == 1 && fread(&r.v, sizeof(float), 1, fp) == 1) recs.push_back(r);
    fclose(fp);
  }
  printf("%zu samples\n", recs.size());
  nt::Net<float> net;
  net.load(load);
  printf("loaded %s: %d stages, training stage %d\n", load.c_str(), net.nstages, stage);
  if (center > 0) {
    // the searched values sit above the network's (better policy, and the max-bias of expectimax backups); fitting on-path
    // states to that offset distorts them against the off-path positions the search compares -> learn only the relative part
    vector<double> se(4096, 0.0);
    vector<long> sn(4096, 0);
    auto bin = [&](board_t a) { return (int)min<uint64_t>(4095, bb::tile_sum(a) / (uint64_t)center); };
    for (auto& r : recs) {
      int b = bin(r.a);
      se[b] += r.v - net.eval(r.a, stage);
      sn[b]++;
    }
    for (auto& r : recs) {
      int b = bin(r.a);
      r.v -= (float)(se[b] / sn[b]);
    }
    for (int b = 0; b < 4096; b++)
      if (sn[b] > 10000) printf("  sum %6d+: %8ld samples, mean (target - V) %+.0f removed\n", b * center, sn[b], se[b] / sn[b]);
  }
  mt19937_64 rng(seed);
  for (int ep = 0; ep < epochs; ep++) {
    shuffle(recs.begin(), recs.end(), rng);
    double se = 0, sab = 0;
    for (auto& r : recs) {
      float before = net.eval(r.a, stage);
      net.learn(r.a, r.v, (float)alpha, false, stage);
      double e = r.v - before;
      se += e * e;
      sab += fabs(e);
    }
    printf("epoch %d: rms error before update %.0f, mean |error| %.0f\n", ep + 1, sqrt(se / recs.size()), sab / recs.size());
    fflush(stdout);
  }
  net.save(out);
  printf("saved %s\n", out.c_str());
  return 0;
}
