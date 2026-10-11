// Solves a snake endgame sub-game by tile-sum layers (layered.h) and writes it to disk.
//
//   layered --k K --rank R [--caps c,c,...] --out FILE [--threads N]
//       sub-game of eg::Snake: the first K cells of the snake path hold a chain ending in rank R;
//       make a rank-R tile next to the chain's end. Free cells are capped at R (as in endgame.h)
//       unless --caps gives one cap per free cell in snake-path order.
//   layered ... --verify EGT    compare every entry of a memoised table (endgame.h format, same
//                               sub-game with the default caps) with the layered solution.
//   layered ... --query         read boards (16 hex digits, cell 0 first) on stdin, print P/move.
#include <atomic>
#include <cmath>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>
#include <vector>

#include "board.h"
#include "endgame.h"
#include "layered.h"

using namespace std;

static inline bool won(const lt::Spec& s, board_t a) {
  for (uint16_t g = s.goal; g; g &= g - 1) {
    int c = __builtin_ctz(g);
    if (bb::cell(a, c) == s.goal_rank) return true;
  }
  return false;
}

int main(int argc, char** argv) {
  int k = 0, r = 0, threads = 16;
  vector<int> caps;
  string out, verify;
  bool query = false;
  long sims = 0;
  int resume = -1;  // --resume T: layers above T are complete in the output file; continue at T
  vector<int> path;  // --path c0,c1,...,c15: chain order of the cells (default: the 4-wide snake)
  int sim_lo = 0, sim_hi = 0;
  for (int i = 1; i < argc; i++) {
    string a = argv[i];
    auto next = [&]() -> string {
      if (i + 1 >= argc) { fprintf(stderr, "missing value for %s\n", a.c_str()); exit(1); }
      return argv[++i];
    };
    if (a == "--k") k = stoi(next());
    else if (a == "--rank") r = stoi(next());
    else if (a == "--caps") {
      string v = next();
      for (size_t p = 0; p < v.size();) {
        size_t q = v.find(',', p);
        if (q == string::npos) q = v.size();
        caps.push_back(stoi(v.substr(p, q - p)));
        p = q + 1;
      }
    } else if (a == "--out") out = next();
    else if (a == "--threads") threads = stoi(next());
    else if (a == "--verify") verify = next();
    else if (a == "--query") query = true;
    else if (a == "--resume") resume = stoi(next());
    else if (a == "--path") {
      string v = next();
      for (size_t p = 0; p < v.size();) {
        size_t q = v.find(',', p);
        if (q == string::npos) q = v.size();
        path.push_back(stoi(v.substr(p, q - p)));
        p = q + 1;
      }
    }
    else if (a == "--sim") {  // --sim N LO HI: N games of the table policy from random states with sum in [LO, HI]
      sims = stol(next());
      sim_lo = stoi(next());
      sim_hi = stoi(next());
    }
    else { fprintf(stderr, "unknown option %s\n", a.c_str()); return 1; }
  }
  if (k < 1 || r < 1 || out.empty() || (!caps.empty() && (int)caps.size() != 16 - k)) {
    fprintf(stderr, "usage: layered --k K --rank R [--caps c,...(16-K values)] --out FILE [--threads N] [--verify EGT] [--query]\n");
    return 1;
  }
  if (!path.empty() && path.size() != 16) { fprintf(stderr, "--path needs 16 cells\n"); return 1; }
  lt::Spec sp = path.empty() ? lt::snake_spec(k, r, caps) : lt::snake_spec(k, r, caps, path.data());
  lt::Index ix(sp);
  printf("sub-game k=%d r=%d: %d free cells, caps", k, r, sp.n);
  for (int i = 0; i < sp.n; i++) printf(" %d:%d", sp.cells[i], sp.cap[i]);
  printf("; %llu states in %d layers (largest sum %d)\n", (unsigned long long)ix.total(), ix.smax() + 1, 2 * ix.smax());

  if (query || !verify.empty() || sims) {
    lt::Table t(sp, out);
    if (!t.ok()) { fprintf(stderr, "cannot open %s\n", out.c_str()); return 1; }
    if (sims) {
      // plays the table's own policy from random states (tile sums in [sim_lo, sim_hi]) and compares the
      // success rate with the table's probability
      bb::Rng rng(12345);
      double psum = 0;
      long wins = 0, n = 0, steps = 0;
      while (n < sims) {
        int tl = sim_lo / 2 + (int)rng.below((uint32_t)(sim_hi / 2 - sim_lo / 2 + 1));
        if (tl > ix.smax() || ix.layer_size(tl) == 0) continue;
        uint64_t sz = ix.layer_size(tl);
        uint64_t idx = ((uint64_t)rng.below(1u << 31) << 31 | rng.below(1u << 31)) % sz;
        board_t st = ix.unrank(idx, tl);
        int m;
        float p0 = t.lookup(st, &m);
        if (p0 <= 0.02f) continue;  // mostly dead or hopeless states
        psum += p0;
        n++;
        bool win = false;
        for (;;) {
          float p = t.lookup(st, &m);
          if (p <= 0) break;
          board_t a = bb::move(st, m);
          steps++;
          if (a == st || (a & sp.lock_mask) != sp.chain) break;
          if (won(sp, a)) { win = true; break; }
          if (ix.sum(a) < 0) break;
          st = bb::spawn(a, rng);
        }
        wins += win;
      }
      printf("%ld simulated games from random states (sum %d-%d, p > 0.02): mean table p %.4f, success %.4f +- %.4f, "
             "%.0f moves/game\n", n, sim_lo, sim_hi, psum / n, (double)wins / n,
             sqrt((double)wins / n * (1 - (double)wins / n) / n), (double)steps / n);
      return 0;
    }
    if (query) {
      char buf[64];
      while (scanf("%63s", buf) == 1) {
        board_t b = 0;
        for (int c = 0; c < 16 && buf[c]; c++) {
          char ch = buf[c];
          int v = ch <= '9' ? ch - '0' : ch - 'a' + 10;
          b = bb::set_cell(b, c, v);
        }
        int m = -1;
        float p = t.lookup(b, &m);
        printf("%s %.4f %d\n", buf, p, m);
      }
      return 0;
    }
    // compare with a memoised table of the same sub-game
    int maxr[17] = {0};
    for (int kk = 0; kk <= 16; kk++) maxr[kk] = 15;
    eg::Snake snake(k, maxr, 0);
    eg::Table* et = snake.get(k, r);
    if (!et->load(verify.c_str())) { fprintf(stderr, "cannot load %s\n", verify.c_str()); return 1; }
    long n = 0, diff = 0, movediff = 0;
    double maxd = 0;
    vector<uint16_t> buf(eg::Table::chunk_size());
    for (uint64_t idx = 0; idx < et->size(); idx++) {
      board_t b = et->board_of(idx);
      int m1;
      float p1 = et->peek(b, &m1);
      if (p1 < 0) continue;
      int m2;
      float p2 = t.lookup(b, &m2);
      n++;
      double d = fabs(p1 - p2);
      if (d > maxd) maxd = d;
      if (d > 0.5 / lt::kScale) diff++;
      if (p1 > 0 && m1 != m2) movediff++;
      if (idx % (et->size() / 20 + 1) == 0) fprintf(stderr, ".");
    }
    printf("\nverified %ld entries: %ld differ (max |dp| %.6f), %ld with a different move\n", n, diff, maxd, movediff);
    return 0;
  }

  int fd = resume >= 0 ? open(out.c_str(), O_RDWR) : open(out.c_str(), O_RDWR | O_CREAT | O_TRUNC, 0644);
  if (fd < 0) { fprintf(stderr, "cannot create %s\n", out.c_str()); return 1; }
  uint64_t maxl = 0;
  for (int t = 0; t <= ix.smax(); t++) maxl = max(maxl, ix.layer_size(t));
  vector<uint16_t> L1(maxl, 0), L2(maxl, 0), cur(maxl, 0);  // layers t+1, t+2, t
  auto t0 = chrono::steady_clock::now();
  uint64_t done = 0;
  int top = ix.smax();
  if (resume >= 0) {
    // reload the two finished layers above the restart point
    for (int q = 1; q <= 2; q++) {
      int t = resume + q;
      if (t > ix.smax()) continue;
      vector<uint16_t>& L = q == 1 ? L1 : L2;
      uint64_t N = ix.layer_size(t);
      if (pread(fd, L.data(), N * 2, (off_t)(ix.base(t) * 2)) != (ssize_t)(N * 2)) {
        fprintf(stderr, "cannot reload layer %d\n", t);
        return 1;
      }
    }
    top = resume;
    done = ix.total() - ix.base(resume + 1);
    printf("resuming at layer %d (%.2f%% done)\n", resume, 100.0 * done / ix.total());
  }
  for (int t = top; t >= 0; t--) {
    uint64_t N = ix.layer_size(t);
    atomic<uint64_t> next_chunk{0};
    const uint64_t CH = 4096;
    auto work = [&]() {
      for (;;) {
        uint64_t lo = next_chunk.fetch_add(CH);
        if (lo >= N) break;
        uint64_t hi = min(N, lo + CH);
        for (uint64_t idx = lo; idx < hi; idx++) {
          board_t s = ix.unrank(idx, t);
          float best = 0.0f;
          int best_move = 0;
          for (int d = 0; d < 4; d++) {
            board_t a = bb::move(s, d);
            if (a == s || (a & sp.lock_mask) != sp.chain) continue;
            float p;
            if (won(sp, a)) p = 1.0f;
            else if (ix.sum(a) < 0) p = 0.0f;
            else {
              // chance node: same order and arithmetic as eg::Table::chance
              uint64_t em = bb::empty_mask(a);
              int n = __builtin_popcountll(em);
              float sum = 0.0f;
              for (uint64_t m = em; m; m &= m - 1) {
                uint64_t bit = m & -m;
                board_t s2 = a | bit, s4 = a | (bit << 1);
                // a spawn adds 1 (2-tile) or 2 (4-tile) units: layers t+1 and t+2
                float v2 = (L1[ix.rank(s2, t + 1)] & 0x3FFF) / lt::kScale;
                sum += 0.9f * v2;
                int c = __builtin_ctzll(bit) / 4;
                bool cap4 = true;
                for (int i = 0; i < sp.n; i++)
                  if (sp.cells[i] == c) { cap4 = sp.cap[i] >= 2; break; }
                float v4 = cap4 ? (L2[ix.rank(s4, t + 2)] & 0x3FFF) / lt::kScale : 0.0f;
                sum += 0.1f * v4;
              }
              p = n ? sum / n : 0.0f;
            }
            if (p > best) best = p, best_move = d;
            if (best >= 1.0f) break;
          }
          uint16_t q = (uint16_t)(best * lt::kScale + 0.5f);
          cur[idx] = (uint16_t)(q | (best_move << 14));
        }
      }
    };
    vector<thread> th;
    for (int i = 0; i < threads; i++) th.emplace_back(work);
    for (auto& x : th) x.join();
    if (pwrite(fd, cur.data(), N * 2, (off_t)(ix.base(t) * 2)) != (ssize_t)(N * 2)) {
      fprintf(stderr, "write failed at layer %d\n", t);
      return 1;
    }
    swap(L2, L1);
    swap(L1, cur);
    done += N;
    if (t % 32 == 0 || t < 8) {
      double el = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
      printf("layer %5d (sum %5d): %12llu states  done %6.2f%%  %.0fs\n", t, 2 * t, (unsigned long long)N,
             100.0 * done / ix.total(), el);
      fflush(stdout);
    }
  }
  close(fd);
  // P at the empty board (a sanity number): the layer-0 state
  printf("P(empty free region) = %.4f\n", (L1[0] & 0x3FFF) / lt::kScale);
  return 0;
}
