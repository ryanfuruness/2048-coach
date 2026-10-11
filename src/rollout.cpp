// Rollout judge: ground-truth move values by playouts, independent of the network's judgment of the position itself.
//
//   build/rollout --preset best [engine flags] --pool FILE.bin [--first N] [--skip S] --playouts K [--horizon H]
//                 [--threads T] [--seed X] [--moves all|engine] --out FILE.tsv
//
// For every position of the pool and every legal move (or only the engine's move): K playouts of the move followed by
// up to H engine moves (H = 0: to the end of the game); the playout's value is the rewards collected plus, if it was cut
// off alive at H moves, the network's value of its last afterstate. The same K random streams are used for every move
// of a position (common random numbers). --soft T replaces the engine in the playouts by the softmax player of
// temperature T (losses "at that skill level"); --human S by the human move model of src/human.h at skill S (value
// skill S, structure skill min(S, 0.4): the personal-odds v3 family of scripts/hm_personal.sh; weights from
// --human-model FILE, else the built-in ones). Output per (position, move): mean playout value and its standard error, the
// share of playouts that died, the share that reached each tile, and the engine's own analysis (value, choice).
#include <atomic>
#include <cmath>
#include <cstdio>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "engine.h"
#include "human.h"

using namespace std;

static Engine E;
static vector<board_t> pool;
static long playouts = 16, horizon = 200;
static int stop_rank = 0;
static double soft_t = 0;  // --soft T: playouts by the softmax player of temperature T instead of the engine  // --stop-rank R: a playout ends (as a success for the tile counts) once a tile of rank >= R exists
static double human_s = NAN;  // --human S: playouts by the human move model at skill S
static hm::Model HM;
static uint64_t seed = 1;
static bool all_moves = true;

struct Task {
  size_t pos;
  int move;
};
struct Acc {
  double sum = 0, sum2 = 0, rew = 0;
  long n = 0, died = 0;
  long reached[20] = {};
};

static vector<Task> tasks;
static vector<Acc> acc;
static vector<Analysis> analyses;
static atomic<size_t> next_task{0};
static mutex mu;

// Work items are chunks of a task's playouts (kChunk each), so a few slow late-game tasks spread over all threads
// instead of leaving a long single-threaded tail; the chunks' sums are merged into the task's accumulator.
static const long kChunk = 8;
static void worker() {
  EngineThread T(E);
  const long chunks = (playouts + kChunk - 1) / kChunk;
  for (;;) {
    size_t w = next_task.fetch_add(1);
    if (w >= tasks.size() * (size_t)chunks) break;
    size_t t = w / chunks;
    long k0 = (long)(w % chunks) * kChunk, k1 = min(playouts, k0 + kChunk);
    const Task& tk = tasks[t];
    board_t s0 = pool[tk.pos];
    Acc a;
    for (long k = k0; k < k1; k++) {
      // every playout starts from an empty search cache: entries left by the previous playout of the same start make
      // the budgeted iterative deepening under-predict the cost and search deeper and deeper (the fuzz study), so
      // the continuation would depend on the chunk's order
      T.reset_search();
      bb::Rng rng(seed * 0x9E3779B97F4A7C15ULL + tk.pos * 1000003ULL + (uint64_t)k * 7919ULL);
      uint32_t r;
      board_t s = bb::move(s0, tk.move, r);
      hm::History hist;
      hist.push(tk.move);
      double total = r;
      board_t last = s;
      int top = bb::max_rank(s);
      bool dead = false;
      long steps = 0;
      for (;;) {
        s = bb::spawn(last, rng);
        if (horizon && steps >= horizon) break;
        int d = !std::isnan(human_s) ? hm::move(E, HM, s, hist, human_s, rng, std::min(human_s, 0.4))
                : soft_t > 0 ? soft_move(E, s, soft_t, rng) : T.choose(s);
        if (d >= 0) hist.push(d);
        if (d < 0) {
          dead = true;
          break;
        }
        uint32_t rr;
        last = bb::move(s, d, rr);
        total += rr;
        top = max(top, bb::max_rank(last));
        steps++;
        if (stop_rank && top >= stop_rank) break;
      }
      double boot = dead ? 0.0 : (double)E.ev(E.view(last));
      if (!horizon) boot = 0.0;
      double v = total + boot;
      a.sum += v, a.sum2 += v * v, a.rew += total, a.n++, a.died += dead;
      for (int q = 0; q <= top && q < 20; q++) a.reached[q]++;
    }
    lock_guard<mutex> lk(mu);
    Acc& g = acc[t];
    g.sum += a.sum, g.sum2 += a.sum2, g.rew += a.rew, g.n += a.n, g.died += a.died;
    for (int q = 0; q < 20; q++) g.reached[q] += a.reached[q];
  }
}

int main(int argc, char** argv) {
  string pool_file, out;
  long first = 0, skip = 0;
  int threads = 16;
  E.cfg.preset_best(".", true);
  for (int i = 1; i < argc; i++) {
    string a = argv[i];
    auto next = [&]() -> string {
      if (i + 1 >= argc) {
        fprintf(stderr, "missing value for %s\n", a.c_str());
        exit(1);
      }
      return argv[++i];
    };
    if (a == "--preset") {
      string p = next();
      E.cfg = EngineConfig();
      E.cfg.preset_best(".", p == "best");
    } else if (E.cfg.parse(i, argc, argv)) {
    } else if (a == "--pool") pool_file = next();
    else if (a == "--first") first = stol(next());
    else if (a == "--skip") skip = stol(next());
    else if (a == "--playouts") playouts = stol(next());
    else if (a == "--horizon") horizon = stol(next());
    else if (a == "--threads") threads = stoi(next());
    else if (a == "--seed") seed = stoull(next());
    else if (a == "--moves") all_moves = next() == "all";
    else if (a == "--stop-rank") stop_rank = stoi(next());
    else if (a == "--soft") soft_t = stod(next());
    else if (a == "--human") human_s = stod(next());
    else if (a == "--human-model") {
      string f = next();
      if (!HM.load(f)) {
        fprintf(stderr, "cannot read %s\n", f.c_str());
        return 1;
      }
    }
    else if (a == "--out") out = next();
    else {
      fprintf(stderr, "unknown option %s\n", a.c_str());
      return 1;
    }
  }
  FILE* f = fopen(pool_file.c_str(), "rb");
  if (!f) {
    fprintf(stderr, "cannot read %s\n", pool_file.c_str());
    return 1;
  }
  board_t b;
  long idx = 0;
  while (fread(&b, sizeof b, 1, f) == 1) {
    if (idx++ < skip) continue;
    if (first && (long)pool.size() >= first) break;
    pool.push_back(b);
  }
  fclose(f);
  if (!E.load()) return 1;
  {
    EngineThread T(E);
    for (size_t p = 0; p < pool.size(); p++) {
      T.reset_search();  // each position analysed as build/analyze does (independent requests)
      analyses.push_back(T.analyze(pool[p]));
      for (int d = 0; d < 4; d++)
        if (analyses[p].mv[d].legal && (all_moves || d == analyses[p].engine_move)) tasks.push_back(Task{p, d});
    }
  }
  acc.resize(tasks.size());
  fprintf(stderr, "%zu positions, %zu (position, move) tasks x %ld playouts, horizon %ld\n", pool.size(), tasks.size(),
          playouts, horizon);
  vector<thread> th;
  for (int t = 0; t < threads; t++) th.emplace_back(worker);
  for (auto& t : th) t.join();
  FILE* o = out.empty() ? stdout : fopen(out.c_str(), "w");
  fprintf(o, "pos\tboard\tsum\tmax\tmove\tengine_move\tsource\tvalue\tq\tq_se\trewards\tdied\tn\tp2048\tp4096\tp8192"
             "\tp16384\tp32768\tp65536\n");
  for (size_t t = 0; t < tasks.size(); t++) {
    const Task& tk = tasks[t];
    const Analysis& A = analyses[tk.pos];
    const Acc& a = acc[t];
    double m = a.sum / max(1L, a.n), var = a.sum2 / max(1L, a.n) - m * m;
    double se = a.n > 1 ? sqrt(max(0.0, var) / (a.n - 1)) : 0;
    fprintf(o, "%zu\t%s\t%u\t%d\t%c\t%c\t%s\t%.1f\t%.1f\t%.1f\t%.1f\t%.4f\t%ld", tk.pos, board_hex(A.board).c_str(),
            tile_sum(A.board), 1 << bb::max_rank(A.board), kDirChar[tk.move],
            A.engine_move >= 0 ? kDirChar[A.engine_move] : '-', A.source, A.mv[tk.move].value, m, se,
            a.rew / max(1L, a.n), (double)a.died / max(1L, a.n), a.n);
    for (int q = 11; q <= 16; q++) fprintf(o, "\t%.4f", (double)a.reached[q] / max(1L, a.n));
    fprintf(o, "\n");
  }
  if (o != stdout) fclose(o);
  return 0;
}
