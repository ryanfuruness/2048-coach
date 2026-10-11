// Workstream yc (your chance, 2026-10-10): how a move changes a HUMAN player's chances, measured by playouts of the
// simulated human player of the personal odds (src/hplayer.h: the human move model + care in danger, at a model key).
//
//   build/hv_tool first --in POS.tsv --keys K1,K2,... [--playouts N] [--threads T] [--seed S] [--max-moves M]
//                       [--human-model FILE] [engine flags, e.g. --packed weights/serve/v6c_s0only_i16.wp]
//
// POS.tsv: a header line, then "id <TAB> board [<TAB> recent moves]" (board: 16 hex rank digits, engine encoding;
// recent moves: the player's last moves as U/R/D/L, oldest first, for the model's habits; optional).
// For every legal first move, playout k continues with the player until the position's milestone (2048, then the
// next doubling of the largest tile), death or the move cap; the playouts of the four first moves share their random
// streams (common random numbers). Output (stdout or --out): id key k r_U r_R r_D r_L m_U m_R m_D m_L
// (r: milestone reached 1/0, -1 = illegal move; m: moves played).
//
//   build/hv_tool train --key K --out FILE.hv [--init FILE.hv] [--steps MILLIONS] [--lr L0,L1,...] [--eps E]
//                       [--pool POOL.txt] [--pool-frac F] [--patterns SPEC] [--threads T] [--seed S] [engine flags]
// TD evaluation of the key-K player's own chance of the next milestone (src/hvalue.h): games of the player (with
// probability E a uniformly random move instead, for coverage), every afterstate moved toward the EXPECTED value of the
// next one under the player's move probabilities (so exploration does not bias the values): 0 when the new tile ends
// the game, 1 for a move that reaches the milestone. Games start from the initial board or, with probability F, from a
// pool position (16 hex digits per line; drawn stage-balanced: a stage at random, then a position of it). The learning
// rate steps through the list L0, L1, ... in equal parts of the run.
//
//   build/hv_tool eval --in POS.tsv --model FILE.hv[,FILE2.hv...] --keys K1,K2 [engine flags]
// Per position, key and legal move: the model's chance after the move (id key move q), and the position's chance
// for the player (the move probabilities x q: id key - v).
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "engine.h"
#include "hplayer.h"
#include "human.h"
#include "hvalue.h"

using namespace std;

static Engine E;
static hm::Model HM;

struct Pos {
  string id;
  board_t b = 0;
  vector<int> hist;
};
static vector<Pos> pos;
static vector<double> keys;
static long playouts = 200, max_moves = 20000, chunk = 10;
static uint64_t seed = 1;

static vector<string> split(const string& s, char sep) {
  vector<string> out;
  size_t p = 0;
  for (;;) {
    size_t q = s.find(sep, p);
    out.push_back(s.substr(p, q == string::npos ? string::npos : q - p));
    if (q == string::npos) break;
    p = q + 1;
  }
  return out;
}

static bool parse_hex(const string& h, board_t* b) {
  if (h.size() != 16) return false;
  board_t x = 0;
  for (int c = 0; c < 16; c++) {
    char ch = h[c];
    int r = ch >= '0' && ch <= '9' ? ch - '0' : ch >= 'a' && ch <= 'f' ? ch - 'a' + 10 : -1;
    if (r < 0) return false;
    x = bb::set_cell(x, c, r);
  }
  *b = x;
  return true;
}

struct Result {
  int reached = -1;
  long moves = 0;
};

// From afterstate a (a spawn comes first), the player plays until rank `target`, death or the move cap.
static Result play_out(EngineThread& T, const hp::Player& P, board_t a, int target, hm::History hist, bb::Rng& srng,
                       bb::Rng& prng) {
  Result r;
  if (bb::max_rank(a) >= target) {
    r.reached = 1;
    return r;
  }
  board_t s = a;
  for (;;) {
    s = bb::spawn(s, srng);
    if (r.moves >= max_moves) break;
    int d = hp::move(T, HM, P, s, hist, prng);
    if (d < 0) break;
    s = bb::move(s, d);
    hist.push(d);
    r.moves++;
    if (bb::max_rank(s) >= target) {
      r.reached = 1;
      return r;
    }
  }
  r.reached = 0;
  return r;
}

struct Item {
  size_t p;
  size_t ki;
  long k0, k1;
};
static vector<Item> items;
static atomic<size_t> next_item{0};
static mutex mu;
static FILE* out_f = stdout;

static void worker_first() {
  EngineThread T(E);
  string buf;
  for (;;) {
    size_t w = next_item.fetch_add(1);
    if (w >= items.size()) break;
    const Item& it = items[w];
    const Pos& P = pos[it.p];
    hp::Player pl(keys[it.ki]);
    int target = hp::milestone_rank(P.b);
    hm::History h0;
    for (int d : P.hist) h0.push(d);
    buf.clear();
    for (long k = it.k0; k < it.k1; k++) {
      Result res[4];
      for (int d = 0; d < 4; d++) {
        board_t a = bb::move(P.b, d);
        if (a == P.b) continue;
        uint64_t s0 = seed * 0x9E3779B97F4A7C15ULL + it.p * 1000003ULL + (uint64_t)k * 7919ULL;
        bb::Rng srng(s0), prng(s0 ^ 0xD1B54A32D192ED03ULL);
        hm::History h = h0;
        h.push(d);
        res[d] = play_out(T, pl, a, target, h, srng, prng);
      }
      char line[512];
      snprintf(line, sizeof line, "%s\t%g\t%ld\t%d\t%d\t%d\t%d\t%ld\t%ld\t%ld\t%ld\n", P.id.c_str(), keys[it.ki], k,
               res[0].reached, res[1].reached, res[2].reached, res[3].reached, res[0].moves, res[1].moves,
               res[2].moves, res[3].moves);
      buf += line;
    }
    lock_guard<mutex> lk(mu);
    fputs(buf.c_str(), out_f);
    fflush(out_f);
  }
}


// ---------------------------------------------------------------- train
static hv::Net tnet;
static vector<double> lr_sched = {0.5, 0.2, 0.05};
static double eps_rand = 0.05, pool_frac = 0.5;
static long total_steps = 100000000;
static atomic<long> steps_done{0};
struct PoolPos {
  board_t b;
  vector<int> hist;  // the player's last moves (oldest first), for the move model's habits
};
static vector<vector<PoolPos>> pool_by_stage(hv::kStages);
static vector<int> pool_stages;
static double train_key = 0.016;
struct StageStats {
  atomic<long> n{0};
  atomic<long> abs_err_1e6{0};
  atomic<long> v_1e6{0};
};
static StageStats sstats[hv::kStages];

static double current_lr(long done) {
  size_t i = (size_t)((double)done / total_steps * lr_sched.size());
  return lr_sched[min(i, lr_sched.size() - 1)];
}

// One afterstate of the current game, waiting for its lambda-return.
struct Ent {
  board_t a;
  double e = 0;        // the expected one-step target (0 if the new tile ended the game)
  double qnext = 0;    // the value of the move actually played next (1 if it reached the milestone)
  bool cut = true;     // no lambda correction after this entry: the game ended, the next move was exploratory or
                       // reached the milestone (the next afterstate plays for another milestone), or not known yet
  bool known = false;  // e is known (the next state's move probabilities were computed)
};
static double lambda_ = 0.0;
static int horizon = 16;
static double side_prob = 0.0;  // --side X: per move, with probability X also train a non-chosen move's afterstate

static void flush(vector<Ent>& buf, size_t upto, long& local, bool all) {
  // lambda-returns backward over the buffer (the last entry bootstraps with its expected target)
  while (!buf.empty() && !buf.back().known && all) buf.pop_back();  // the move cap: no target for the last one
  size_t n = buf.size();
  if (n < (all ? 1u : 2u)) return;
  size_t last = all ? n - 1 : n - 2;  // the last entry whose target is known (in a game: not the newest one)
  vector<double> G(n);
  G[last] = buf[last].e;
  for (size_t i = last; i-- > 0;)
    G[i] = buf[i].e + (buf[i].cut ? 0.0 : lambda_ * (G[i + 1] - buf[i].qnext));
  size_t m = all ? n : min(upto, last + 1);
  double lr = current_lr(steps_done.load(memory_order_relaxed));
  for (size_t i = 0; i < m; i++) {
    int st = hv::stage_of(buf[i].a);
    double y = min(1.0, max(0.0, G[i]));
    double vp = hv::sigmoid(tnet.z(buf[i].a, st));
    tnet.update(buf[i].a, lr * (y - vp));
    StageStats& S = sstats[st];
    S.n.fetch_add(1, memory_order_relaxed);
    S.abs_err_1e6.fetch_add((long)(fabs(y - vp) * 1e6), memory_order_relaxed);
    S.v_1e6.fetch_add((long)(vp * 1e6), memory_order_relaxed);
    if (++local == 1000) steps_done.fetch_add(1000, memory_order_relaxed), local = 0;
  }
  buf.erase(buf.begin(), buf.begin() + m);
}

static void worker_train(int tid) {
  EngineThread T(E);
  hp::Player pl(train_key);
  bb::Rng rng(seed * 0x9E3779B97F4A7C15ULL + (uint64_t)tid * 104729ULL + 17);
  long local = 0;
  vector<Ent> buf;
  const size_t H = lambda_ > 0 ? (size_t)horizon : 0;
  while (steps_done.load(memory_order_relaxed) < total_steps) {
    board_t s;
    hm::History hist;
    if (!pool_stages.empty() && rng.uniform() < pool_frac) {
      const vector<PoolPos>& v = pool_by_stage[pool_stages[rng.below((uint32_t)pool_stages.size())]];
      const PoolPos& pp = v[rng.below((uint32_t)v.size())];
      s = pp.b;
      for (int d : pp.hist) hist.push(d);
    } else {
      s = bb::initial_board(rng);
    }
    if (hv::stage_of(s) < 0) continue;
    buf.clear();
    for (long mv = 0; mv < max_moves; mv++) {
      double p[4];
      int n = hp::probs(T, HM, pl, s, hist, p);
      board_t as[4];
      double qv[4] = {0, 0, 0, 0};
      for (int d = 0; d < 4; d++) as[d] = bb::move(s, d);
      if (!buf.empty()) {
        int M = hv::milestone_rank(buf.back().a);
        double y = 0;
        for (int d = 0; d < 4 && n; d++) {
          if (as[d] == s || p[d] <= 0) continue;
          qv[d] = bb::max_rank(as[d]) >= M ? 1.0 : tnet.v(as[d]);
          y += p[d] * qv[d];
        }
        buf.back().e = y;
        buf.back().known = true;
      }
      if (!n) break;  // the last entry's target: 0 (cut stays set)
      int d = -1;
      bool explore = rng.uniform() < eps_rand;
      if (explore) {
        int legal[4], nl = 0;
        for (int k = 0; k < 4; k++)
          if (as[k] != s) legal[nl++] = k;
        d = legal[rng.below((uint32_t)nl)];
      } else {
        double u = rng.uniform(), acc = 0;
        for (int k = 0; k < 4; k++) {
          if (p[k] <= 0) continue;
          d = k;
          acc += p[k];
          if (u < acc) break;
        }
      }
      if (side_prob > 0 && n > 1 && rng.uniform() < side_prob) {
        // a side sample: a non-chosen legal move's afterstate, toward its one-step expected target (the player's
        // probabilities after a random new tile; 0 if it ends the game), without following it
        int alt[4], na = 0;
        for (int k = 0; k < 4; k++)
          if (as[k] != s && k != d) alt[na++] = k;
        board_t a2 = as[alt[rng.below((uint32_t)na)]];
        int M2 = hv::milestone_rank(s);
        if (bb::max_rank(a2) < M2 && hv::stage_of(a2) >= 0) {
          board_t s2 = bb::spawn(a2, rng);
          hm::History h2 = hist;
          double p2[4], y2 = 0;
          int n2 = hp::probs(T, HM, pl, s2, h2, p2);
          for (int k = 0; k < 4 && n2; k++) {
            board_t b2 = bb::move(s2, k);
            if (b2 == s2 || p2[k] <= 0) continue;
            y2 += p2[k] * (bb::max_rank(b2) >= M2 ? 1.0 : tnet.v(b2));
          }
          int st2 = hv::stage_of(a2);
          double v2 = hv::sigmoid(tnet.z(a2, st2));
          tnet.update(a2, current_lr(steps_done.load(memory_order_relaxed)) * (y2 - v2));
        }
      }
      board_t a = as[d];
      if (!explore) hist.push(d);  // the habits are the player's own: an exploratory move is not one of them
      bool reached = !buf.empty() && bb::max_rank(a) >= hv::milestone_rank(buf.back().a);
      if (!buf.empty()) {
        buf.back().qnext = qv[d];
        buf.back().cut = explore || reached;
      }
      if (hv::stage_of(a) < 0) break;  // a 16384: beyond the modelled milestones
      Ent en;
      en.a = a;
      buf.push_back(en);
      if (buf.size() > 2 * H + 1) flush(buf, buf.size() - H - 1, local, false);
      s = bb::spawn(a, rng);
    }
    // the game ended (death: the last entry's target is 0; a 16384 or the move cap: its expected target so far)
    flush(buf, 0, local, true);
  }
  steps_done.fetch_add(local, memory_order_relaxed);
}

static int run_train(const string& out, const string& init, const string& patterns, const string& pool, int threads,
                     long report_every) {
  if (!init.empty()) {
    hv::Family fam;
    if (!fam.load(init)) {
      fprintf(stderr, "cannot read %s\n", init.c_str());
      return 1;
    }
    tnet.init(nt::pattern_string(fam.nets[0]->pats), train_key);
    tnet.w = fam.nets[0]->w;
  } else {
    tnet.init(patterns, train_key);
  }
  if (!pool.empty()) {
    FILE* f = fopen(pool.c_str(), "r");
    if (!f) {
      fprintf(stderr, "cannot read %s\n", pool.c_str());
      return 1;
    }
    char line[256];
    long n = 0;
    while (fgets(line, sizeof line, f)) {
      string l(line);
      while (!l.empty() && (l.back() == '\n' || l.back() == '\r')) l.pop_back();
      PoolPos pp;
      if (!parse_hex(l.substr(0, 16), &pp.b)) continue;
      for (size_t i = 16; i < l.size(); i++) {
        const char* q = strchr("URDL", l[i]);
        if (q && l[i]) pp.hist.push_back((int)(q - "URDL"));
      }
      int st = hv::stage_of(pp.b);
      if (st < 0 || !bb::can_move(pp.b)) continue;
      pool_by_stage[st].push_back(pp), n++;
    }
    fclose(f);
    for (int st = 0; st < hv::kStages; st++)
      if (!pool_by_stage[st].empty()) pool_stages.push_back(st);
    fprintf(stderr, "pool: %ld positions in %zu stages\n", n, pool_stages.size());
  }
  hp::Player pl(train_key);
  fprintf(stderr, "train key %g (theta %.3f, structure %.3f, care %.2f), %ld steps, lr", train_key, pl.theta,
          pl.theta_s, pl.dq, total_steps);
  for (double l : lr_sched) fprintf(stderr, " %g", l);
  fprintf(stderr, ", eps %g, side %g, pool %g, lambda %g (horizon %d), patterns %s, %d threads\n", eps_rand, side_prob,
          pool_frac, lambda_, horizon, nt::pattern_string(tnet.pats).c_str(), threads);
  vector<thread> th;
  auto t0 = chrono::steady_clock::now();
  for (int t = 0; t < threads; t++) th.emplace_back(worker_train, t);
  long next_report = report_every;
  while (steps_done.load() < total_steps) {
    this_thread::sleep_for(chrono::milliseconds(500));
    long done = steps_done.load();
    if (done >= next_report) {
      next_report += report_every;
      double secs = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
      fprintf(stderr, "%6.1fM %5.0fs lr %.3g |", done / 1e6, secs, current_lr(done));
      for (int st = 0; st < hv::kStages; st++) {
        long n = sstats[st].n.exchange(0);
        long e = sstats[st].abs_err_1e6.exchange(0), v = sstats[st].v_1e6.exchange(0);
        if (n) fprintf(stderr, " s%d %.3f/%.3f", st, e / 1e6 / n, v / 1e6 / n);
      }
      fprintf(stderr, "\n");
      hv::Family fam;
      fam.nets.emplace_back(new hv::Net);
      *fam.nets[0] = tnet;
      fam.save(out);
    }
  }
  for (auto& t : th) t.join();
  hv::Family fam;
  fam.nets.emplace_back(new hv::Net);
  *fam.nets[0] = tnet;
  fam.save(out);
  fprintf(stderr, "saved %s\n", out.c_str());
  return 0;
}

// ---------------------------------------------------------------- eval
static int run_eval(const string& models) {
  hv::Family fam;
  for (auto& m : split(models, ','))
    if (!fam.load(m)) {
      fprintf(stderr, "cannot read %s\n", m.c_str());
      return 1;
    }
  EngineThread T(E);
  fprintf(out_f, "id\tkey\tmove\tq\n");
  for (auto& P : pos) {
    int M = hv::milestone_rank(P.b);
    hm::History h0;
    for (int d : P.hist) h0.push(d);
    for (double k : keys) {
      hp::Player pl(k);
      double p[4], v = 0;
      int n = hp::probs(T, HM, pl, P.b, h0, p);
      for (int d = 0; d < 4 && n; d++) {
        board_t a = bb::move(P.b, d);
        if (a == P.b) continue;
        double q = hp::with_survival(fam.v(a, M, k), a);
        v += p[d] * q;
        fprintf(out_f, "%s\t%g\t%c\t%.5f\n", P.id.c_str(), k, kDirChar[d], q);
      }
      fprintf(out_f, "%s\t%g\t-\t%.5f\n", P.id.c_str(), k, v);
    }
  }
  return 0;
}

// ---------------------------------------------------------------- calib
// On-policy calibration: N fresh games of the key's player (or games from pool positions with --pool-frac 1); every
// afterstate's model chance vs whether the game then reached that afterstate's milestone (bins of 0.05 per stage).
static int run_calib(const string& models, long games, int threads) {
  hv::Family fam;
  for (auto& m : split(models, ','))
    if (!fam.load(m)) {
      fprintf(stderr, "cannot read %s\n", m.c_str());
      return 1;
    }
  double key = keys.empty() ? 0.016 : keys[0];
  static double sum_v[hv::kStages][20], sum_y[hv::kStages][20];
  static long cnt[hv::kStages][20];
  mutex m2;
  atomic<long> next_game{0};
  auto work = [&](int tid) {
    EngineThread T(E);
    hp::Player pl(key);
    double lv[hv::kStages][20] = {}, ly[hv::kStages][20] = {};
    long lc[hv::kStages][20] = {};
    for (;;) {
      long g = next_game.fetch_add(1);
      if (g >= games) break;
      bb::Rng rng(seed * 7919ULL + (uint64_t)g * 0x9E3779B97F4A7C15ULL + tid);
      board_t s;
      hm::History hist;
      if (!pool_stages.empty() && rng.uniform() < pool_frac) {
        const vector<PoolPos>& v = pool_by_stage[pool_stages[rng.below((uint32_t)pool_stages.size())]];
        const PoolPos& pp = v[rng.below((uint32_t)v.size())];
        s = pp.b;
        for (int d : pp.hist) hist.push(d);
      } else {
        s = bb::initial_board(rng);
      }
      vector<pair<board_t, double>> trace;  // afterstates and their model chance
      for (long mv = 0; mv < max_moves; mv++) {
        int d = hp::move(T, HM, pl, s, hist, rng);
        if (d < 0) break;
        board_t a = bb::move(s, d);
        hist.push(d);
        if (hv::stage_of(a) < 0) {
          trace.push_back({a, 1.0});
          break;
        }
        trace.push_back({a, fam.v(a, hv::milestone_rank(a), key)});
        s = bb::spawn(a, rng);
      }
      int top = 0;
      for (auto& t : trace) top = max(top, bb::max_rank(t.first));
      for (size_t i = 0; i + 1 < trace.size() || (i < trace.size() && hv::stage_of(trace[i].first) >= 0); i++) {
        board_t a = trace[i].first;
        int st = hv::stage_of(a);
        if (st < 0) continue;
        int M = hv::milestone_rank(a), bin = min(19, (int)(trace[i].second * 20));
        double y = top >= M ? 1.0 : 0.0;
        lv[st][bin] += trace[i].second, ly[st][bin] += y, lc[st][bin]++;
      }
    }
    lock_guard<mutex> lk(m2);
    for (int st = 0; st < hv::kStages; st++)
      for (int b = 0; b < 20; b++) sum_v[st][b] += lv[st][b], sum_y[st][b] += ly[st][b], cnt[st][b] += lc[st][b];
  };
  vector<thread> th;
  for (int t = 0; t < threads; t++) th.emplace_back(work, t);
  for (auto& t : th) t.join();
  fprintf(out_f, "stage\tbin\tn\tmean_model\tobserved\n");
  for (int st = 0; st < hv::kStages; st++) {
    double tv = 0, ty = 0;
    long tc = 0;
    for (int b = 0; b < 20; b++) {
      if (!cnt[st][b]) continue;
      tv += sum_v[st][b], ty += sum_y[st][b], tc += cnt[st][b];
      fprintf(out_f, "%d\t%d\t%ld\t%.4f\t%.4f\n", st, b, cnt[st][b], sum_v[st][b] / cnt[st][b], sum_y[st][b] / cnt[st][b]);
    }
    if (tc) fprintf(stderr, "stage %d: %ld afterstates, model %.4f, observed %.4f\n", st, tc, tv / tc, ty / tc);
  }
  return 0;
}

// ---------------------------------------------------------------- recal
// Recalibration: games of each net's player (from pool positions with probability --pool-frac, else fresh), every
// afterstate kept with probability 1/8; per stage, the outcome (the afterstate's milestone reached later) is fitted as
// sigmoid(a + b z) of the net's raw logit z (Newton steps, a weak pull toward a = 0, b = 1 for stages with few
// samples). Writes the family with the calibration to --out.
static int run_recal(const string& models, const string& out, long games, int threads) {
  hv::Family fam;
  for (auto& m : split(models, ','))
    if (!fam.load(m)) {
      fprintf(stderr, "cannot read %s\n", m.c_str());
      return 1;
    }
  for (auto& netp : fam.nets) {
    hv::Net& net = *netp;
    vector<vector<pair<float, uint8_t>>> samples(hv::kStages);
    mutex m2;
    atomic<long> next_game{0};
    auto work = [&](int tid) {
      EngineThread T(E);
      hp::Player pl(net.key);
      vector<vector<pair<float, uint8_t>>> loc(hv::kStages);
      for (;;) {
        long g = next_game.fetch_add(1);
        if (g >= games) break;
        bb::Rng rng(seed * 104729ULL + (uint64_t)g * 0x9E3779B97F4A7C15ULL + tid * 31 + 5);
        board_t s;
        hm::History hist;
        if (!pool_stages.empty() && rng.uniform() < pool_frac) {
          const vector<PoolPos>& v = pool_by_stage[pool_stages[rng.below((uint32_t)pool_stages.size())]];
          const PoolPos& pp = v[rng.below((uint32_t)v.size())];
          s = pp.b;
          for (int d : pp.hist) hist.push(d);
        } else {
          s = bb::initial_board(rng);
        }
        vector<pair<board_t, float>> kept;
        int top = bb::max_rank(s);
        for (long mv = 0; mv < max_moves; mv++) {
          int d = hp::move(T, HM, pl, s, hist, rng);
          if (d < 0) break;
          board_t a = bb::move(s, d);
          hist.push(d);
          top = max(top, bb::max_rank(a));
          int st = hv::stage_of(a);
          if (st < 0) break;
          if (rng.below(8) == 0) kept.push_back({a, (float)net.z(a, st)});
          s = bb::spawn(a, rng);
        }
        for (auto& k : kept) loc[hv::stage_of(k.first)].push_back({k.second, (uint8_t)(top >= hv::milestone_rank(k.first))});
      }
      lock_guard<mutex> lk(m2);
      for (int st = 0; st < hv::kStages; st++) samples[st].insert(samples[st].end(), loc[st].begin(), loc[st].end());
    };
    vector<thread> th;
    for (int t = 0; t < threads; t++) th.emplace_back(work, t);
    for (auto& t : th) t.join();
    fprintf(stderr, "key %g:", net.key);
    for (int st = 0; st < hv::kStages; st++) {
      auto& S = samples[st];
      double a = 0, b = 1;
      const double lam = 5.0;  // pull toward (0, 1), in samples' worth
      for (int it = 0; it < 30 && S.size() >= 50; it++) {
        double g0 = -lam * a, g1 = -lam * (b - 1), h00 = lam, h01 = 0, h11 = lam;
        for (auto& x : S) {
          double z = x.first, p = hv::sigmoid(a + b * z), w = p * (1 - p), r = x.second - p;
          g0 += r, g1 += r * z, h00 += w, h01 += w * z, h11 += w * z * z;
        }
        double det = h00 * h11 - h01 * h01;
        if (det <= 1e-12) break;
        double da = (h11 * g0 - h01 * g1) / det, db = (h00 * g1 - h01 * g0) / det;
        a += da, b += db;
        if (fabs(da) + fabs(db) < 1e-7) break;
      }
      double mraw = 0, mcal = 0, my = 0;
      for (auto& x : S) mraw += hv::sigmoid(x.first), mcal += hv::sigmoid(a + b * x.first), my += x.second;
      size_t n = max<size_t>(1, S.size());
      net.cal_a[st] = (float)a, net.cal_b[st] = (float)b;
      fprintf(stderr, " s%d n%zu raw %.3f cal %.3f obs %.3f (a %.2f b %.2f) |", st, S.size(), mraw / n, mcal / n, my / n, a, b);
    }
    fprintf(stderr, "\n");
  }
  fam.save(out);
  fprintf(stderr, "saved %s\n", out.c_str());
  return 0;
}

int main(int argc, char** argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: hv_tool first --in POS.tsv --keys K1,K2 [options]\n");
    return 1;
  }
  string mode = argv[1], in, out, init, patterns = "0123 4567 0145 1256 569a", pool, models;
  int threads = 16;
  long report_every = 10000000;
  E.cfg.preset_best(".", false);
  for (int i = 2; i < argc; i++) {
    string a = argv[i];
    auto next = [&]() -> string {
      if (i + 1 >= argc) {
        fprintf(stderr, "missing value for %s\n", a.c_str());
        exit(1);
      }
      return argv[++i];
    };
    if (a == "--in") in = next();
    else if (a == "--out") out = next();
    else if (a == "--keys") {
      keys.clear();
      for (auto& x : split(next(), ',')) keys.push_back(stod(x));
    } else if (a == "--playouts") playouts = stol(next());
    else if (a == "--chunk") chunk = stol(next());
    else if (a == "--max-moves") max_moves = stol(next());
    else if (a == "--threads") threads = stoi(next());
    else if (a == "--seed") seed = stoull(next());
    else if (a == "--key") train_key = stod(next());
    else if (a == "--init") init = next();
    else if (a == "--steps") total_steps = (long)(stod(next()) * 1e6);
    else if (a == "--lr") {
      lr_sched.clear();
      for (auto& x : split(next(), ',')) lr_sched.push_back(stod(x));
    } else if (a == "--eps") eps_rand = stod(next());
    else if (a == "--pool") pool = next();
    else if (a == "--pool-frac") pool_frac = stod(next());
    else if (a == "--patterns") patterns = next();
    else if (a == "--lambda") lambda_ = stod(next());
    else if (a == "--side") side_prob = stod(next());
    else if (a == "--horizon") horizon = stoi(next());
    else if (a == "--model") models = next();
    else if (a == "--report") report_every = (long)(stod(next()) * 1e6);
    else if (a == "--human-model") {
      string f = next();
      if (!HM.load(f)) {
        fprintf(stderr, "cannot read %s\n", f.c_str());
        return 1;
      }
    } else if (E.cfg.parse(i, argc, argv)) {
    } else {
      fprintf(stderr, "unknown option %s\n", a.c_str());
      return 1;
    }
  }
  if (mode != "first" && mode != "train" && mode != "eval" && mode != "calib" && mode != "recal") {
    fprintf(stderr, "unknown mode %s\n", mode.c_str());
    return 1;
  }
  if (mode == "calib" || mode == "recal") {
    if (!E.load(false)) return 1;
    if (!pool.empty()) {
      FILE* f = fopen(pool.c_str(), "r");
      char line[256];
      while (f && fgets(line, sizeof line, f)) {
        string l(line);
        while (!l.empty() && (l.back() == '\n' || l.back() == '\r')) l.pop_back();
        PoolPos pp;
        if (!parse_hex(l.substr(0, 16), &pp.b)) continue;
        for (size_t i = 16; i < l.size(); i++) {
          const char* q = strchr("URDL", l[i]);
          if (q && l[i]) pp.hist.push_back((int)(q - "URDL"));
        }
        int st = hv::stage_of(pp.b);
        if (st >= 0 && bb::can_move(pp.b)) pool_by_stage[st].push_back(pp);
      }
      if (f) fclose(f);
      for (int st = 0; st < hv::kStages; st++)
        if (!pool_by_stage[st].empty()) pool_stages.push_back(st);
    }
    if (mode == "recal") return run_recal(models, out, (long)(total_steps / 1e6 * 1000), threads);
    if (!out.empty()) out_f = fopen(out.c_str(), "w");
    return run_calib(models, (long)(total_steps / 1e6 * 1000), threads);  // --steps N: N thousand games
  }
  if (mode == "train") {
    if (out.empty()) {
      fprintf(stderr, "train needs --out\n");
      return 1;
    }
    if (!E.load(false)) return 1;
    return run_train(out, init, patterns, pool, threads, report_every);
  }
  FILE* f = fopen(in.c_str(), "r");
  if (!f) {
    fprintf(stderr, "cannot read %s\n", in.c_str());
    return 1;
  }
  char lbuf[4096];
  bool header = true;
  while (fgets(lbuf, sizeof lbuf, f)) {
    if (header) {
      header = false;
      continue;
    }
    string l(lbuf);
    while (!l.empty() && (l.back() == '\n' || l.back() == '\r')) l.pop_back();
    if (l.empty()) continue;
    vector<string> c = split(l, '\t');
    if (c.size() < 2) continue;
    Pos p;
    p.id = c[0];
    if (!parse_hex(c[1], &p.b)) {
      fprintf(stderr, "bad board %s\n", c[1].c_str());
      return 1;
    }
    if (c.size() >= 3)
      for (char ch : c[2]) {
        const char* q = strchr("URDL", ch);
        if (q && ch) p.hist.push_back((int)(q - "URDL"));
      }
    pos.push_back(p);
  }
  fclose(f);
  if (!E.load(false)) return 1;
  if (!out.empty()) {
    out_f = fopen(out.c_str(), "w");
    if (!out_f) {
      fprintf(stderr, "cannot write %s\n", out.c_str());
      return 1;
    }
  }
  if (mode == "eval") {
    int rc = run_eval(models);
    if (out_f != stdout) fclose(out_f);
    return rc;
  }
  for (size_t p = 0; p < pos.size(); p++)
    for (size_t ki = 0; ki < keys.size(); ki++)
      for (long k0 = 0; k0 < playouts; k0 += chunk) items.push_back(Item{p, ki, k0, min(playouts, k0 + chunk)});
  fprintf(out_f, "id\tkey\tk\tr_U\tr_R\tr_D\tr_L\tm_U\tm_R\tm_D\tm_L\n");
  fflush(out_f);
  fprintf(stderr, "%zu positions x %zu keys x %ld playouts, %zu work items, %d threads\n", pos.size(), keys.size(),
          playouts, items.size(), threads);
  vector<thread> th;
  for (int t = 0; t < threads; t++) th.emplace_back(worker_first);
  for (auto& t : th) t.join();
  if (out_f != stdout) fclose(out_f);
  fprintf(stderr, "done\n");
  return 0;
}
