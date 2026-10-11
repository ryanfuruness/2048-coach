// Workstream hm3: how does a playout player handle danger on REAL boards? From each given position (a real human's
// board and their last moves), K short playouts of the human move model (value skill --theta, structure skill
// --theta-s; optional care in danger as in messy's human policy: --dq Q --de E --dm M) for --steps moves: the share
// that reaches >= 4 empty cells (escape), and that dies (no legal move).
//
//   build/hm3_tool [--preset best-notables] --theta S [--theta-s SS] [--dq Q --de 2 --dm 1|2] [--samples 32]
//                  [--steps 10] [--human-model FILE] [--threads 8] < IN > OUT
//   IN: "id hex hl m1 .. m_hl" (moves 0-3 = U R D L, oldest first); OUT: "id escape dead"
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "engine.h"
#include "human.h"

static Engine E;
static hm::Model HM;

struct Job {
  std::string id;
  board_t b;
  std::vector<int> hist;
};

int main(int argc, char** argv) {
  E.cfg.preset_best(".", false);
  double theta = 0, theta_s = NAN, dq = 0;
  int de = 2, dm = 1, samples = 32, steps = 10, threads = 8;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    auto next = [&]() { return std::string(argv[++i]); };
    if (a == "--theta") theta = std::stod(next());
    else if (a == "--theta-s") theta_s = std::stod(next());
    else if (a == "--dq") dq = std::stod(next());
    else if (a == "--de") de = std::stoi(next());
    else if (a == "--dm") dm = std::stoi(next());
    else if (a == "--samples") samples = std::stoi(next());
    else if (a == "--steps") steps = std::stoi(next());
    else if (a == "--threads") threads = std::stoi(next());
    else if (a == "--human-model") {
      if (!HM.load(next())) return 1;
    } else if (a == "--preset") {
      std::string p = next();
      E.cfg = EngineConfig();
      E.cfg.preset_best(".", p == "best");
    } else if (!E.cfg.parse(i, argc, argv)) {
      fprintf(stderr, "unknown option %s\n", a.c_str());
      return 1;
    }
  }
  if (!E.load(false)) return 1;
  std::vector<Job> jobs;
  char line[4096], id[256], hex[64];
  while (fgets(line, sizeof line, stdin)) {
    int hl, used;
    if (sscanf(line, "%255s %63s %d%n", id, hex, &hl, &used) != 3 || strlen(hex) != 16) continue;
    Job j;
    j.id = id;
    j.b = 0;
    for (int c = 0; c < 16; c++) {
      char ch = hex[c];
      int r = ch >= '0' && ch <= '9' ? ch - '0' : ch - 'a' + 10;
      j.b = bb::set_cell(j.b, c, r);
    }
    char* q = line + used;
    for (int k = 0; k < hl; k++) {
      int d, u2;
      if (sscanf(q, "%d%n", &d, &u2) != 1) break;
      j.hist.push_back(d);
      q += u2;
    }
    jobs.push_back(j);
  }
  std::vector<double> esc(jobs.size()), dead(jobs.size());
  std::atomic<size_t> nxt{0};
  auto in_corner = [](board_t x) {
    int m = bb::max_rank(x);
    return bb::cell(x, 0) == m || bb::cell(x, 3) == m || bb::cell(x, 12) == m || bb::cell(x, 15) == m;
  };
  auto work = [&]() {
    EngineThread T(E);
    for (;;) {
      size_t k = nxt.fetch_add(1);
      if (k >= jobs.size()) break;
      const Job& j = jobs[k];
      int ne = 0, nd = 0;
      for (int s = 0; s < samples; s++) {
        bb::Rng rng(0x9E3779B97F4A7C15ULL * (k + 1) + 7919ULL * s + 13);
        hm::History hist;
        for (int d : j.hist) hist.push(d);
        board_t b = j.b;
        bool escaped = false, died = false;
        for (int st = 0; st < steps && !escaped; st++) {
          int d = hm::move(E, HM, b, hist, theta, rng, theta_s);
          if (d < 0) {
            died = true;
            break;
          }
          if (dq > 0 && bb::count_empty(b) <= de && rng.uniform() < dq) {
            if (dm == 2) {
              bool keep = in_corner(b);
              float mv[4];
              board_t vb = E.view(b);
              T.search->move_values(vb, 2, mv, E.params(vb));
              double bq = -1e300;
              int bk = -1;
              for (int pass = 0; pass < 2 && bk < 0; pass++)
                for (int dd = 0; dd < 4; dd++) {
                  board_t a = bb::move(b, dd);
                  if (a == b || std::isnan(mv[dd])) continue;
                  if (pass == 0 && keep && !in_corner(a)) continue;
                  if (mv[dd] > bq) bq = mv[dd], bk = dd;
                }
              if (bk >= 0) d = bk;
            } else {
              d = T.choose(b);
            }
          }
          hist.push(d);
          b = bb::spawn(bb::move(b, d), rng);
          if (bb::count_empty(b) >= 4) escaped = true;
        }
        if (!escaped && !died) {  // dead after the last spawn?
          bool any = false;
          for (int dd = 0; dd < 4 && !any; dd++) any = bb::move(b, dd) != b;
          died = !any;
        }
        ne += escaped, nd += died;
      }
      esc[k] = (double)ne / samples, dead[k] = (double)nd / samples;
    }
  };
  std::vector<std::thread> th;
  for (int i = 0; i < threads; i++) th.emplace_back(work);
  for (auto& t : th) t.join();
  for (size_t k = 0; k < jobs.size(); k++) printf("%s\t%.4f\t%.4f\n", jobs[k].id.c_str(), esc[k], dead[k]);
  return 0;
}
