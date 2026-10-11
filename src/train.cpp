// Self-play TD learning of an n-tuple afterstate value function.
//
// Each worker thread plays complete games with the greedy policy
// argmax_a [r(s,a) + V(afterstate(s,a))] and, at the end of the game, sweeps the
// trajectory backwards applying TD(lambda) updates (lambda-returns computed from
// the freshly updated values). Threads share the weights lock-free (Hogwild).
//
// Learning modes: plain TD with rate --alpha, or temporal coherence (--tc, meta
// rate --alpha). Optimistic initialisation (--init V) sets every state's initial
// value to V, which drives exploration (OTD learning, Guei et al.).
//
// Multi-stage: with --stages, the value function uses a separate weight set per
// game stage. One stage (--train-stage) is trained; the others are frozen. Games
// can start from a pool of recorded positions (--pool) so late stages get trained
// without replaying the early game, and positions where a stage is first reached
// can be recorded (--collect) to build such pools.
#include <atomic>
#include <chrono>
#include <cstdio>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "board.h"
#include "ntuple.h"
#include "search.h"
#include "endgame.h"
#include "layered.h"

using namespace std;
using Clock = chrono::steady_clock;

struct Config {
  string patterns = "4x6";
  string load, save, checkpoint, resume;
  string stages;
  int train_stage = 0;
  string pool;
  double pool_prob = 1.0;
  long pool_last = 0;  // use only the last N positions of the pool file (0 = all)
  string collect, collect_when = "14+";  // record the first state satisfying all bounds of collect_when
  long collect_max = 0;
  bool collect_stop = false;  // stop training once collect_max positions are collected
  int threads = 16;
  long episodes = 100000;
  double alpha = 0.1;
  bool tc = false;
  bool learn = true;
  bool downgrade = true;
  int min_gap = 10;
  bool stop_at_boundary = false;  // end episodes when they leave the trained stage
  int corner_lock = 0;            // keep a max tile of at least this rank in its corner (see search.h)
  string endgame_dir;             // endgame tables whose moves the policy plays (lookup only)
  float endgame_min = 0.5f;
  int endgame_full = 2;
  struct Lt {                     // layered (on-disk) tables: --endgame-lt F --lt-k K --lt-rank R --lt-caps c,...
    string file;
    int k = 5, r = 10;
    vector<int> caps;
  };
  vector<Lt> lts;
  float lt_min = 0.5f;
  double lambda = 0.0;
  double init = 0;
  double tc_decay = 1.0;  // scale TC accumulators on resume (lets rates re-adapt faster)
  double boot_c0 = 0, boot_c1 = 0;  // --lt-boot C0 C1 MINP: the afterstate before an episode's first layered-table
  float boot_minp = 2.0f;           // state with P >= MINP gets the target C0 + C1 * P (exact sub-game value) instead
                                    // of the lambda-return through the network's own post-handover values
  bool lt_calib = false;            // --lt-calib: fit return-from-handover ~ C0 + C1 * P (printed at the end)
  double branch_p = 0;   // probability per step of a side branch: a random other legal move, then branch_len greedy
  int branch_len = 8;    // moves, trained by its own backward TD(lambda) sweep (the episode itself stays greedy)
  long log_every = 10000;
  long save_every = 0;
  uint64_t seed = 1;
};

static Config cfg;
static nt::Net<float> fnet;  // all stages (frozen ones are used from here)
static StageFn sf;
static vector<board_t> pool;
static atomic<long> started{0};

// The stage being trained: TC needs per-weight accumulators, plain TD does not.
template <typename Entry>
struct Trained {
  static nt::Net<Entry> net;
};
template <typename Entry>
nt::Net<Entry> Trained<Entry>::net;

template <typename Entry>
static inline float value(board_t as) {
  board_t v = cfg.downgrade ? eval_view(as, cfg.min_gap) : as;
  int st = sf.of(v);
  return st == cfg.train_stage ? Trained<Entry>::net.eval(v) : fnet.eval(v, st);
}

struct Window {
  long games = 0;
  double score_sum = 0;
  long long moves = 0;
  long tiles[20] = {0};  // count of games whose max tile rank == i
  void clear() { *this = Window(); }
};
static mutex stats_mu;
static Window win;
static long finished = 0;
static Clock::time_point t_start, t_window;
static std::unique_ptr<eg::Snake> endgame;  // tables for the policy (lookup only)
static vector<unique_ptr<lt::Table>> ltabs;  // layered tables for the policy (pread lookups)
static atomic<long> lt_moves{0};
static atomic<long> table_moves{0};
static FILE* collect_file = nullptr;
static double cal_n = 0, cal_p = 0, cal_g = 0, cal_pp = 0, cal_pg = 0;  // --lt-calib sums (under stats_mu)
static double cal_v = 0, cal_vv = 0, cal_vg = 0, cal_pv = 0, cal_gg = 0;  // ... with the network's value before the handover
static double cal_bn[10] = {0}, cal_bg[10] = {0}, cal_bs[10] = {0};  // per P decile: count, sum of returns, returns > 100k
static long collected = 0;
static StageFn collect_fn;

template <typename Entry>
static void save_all() {
  if (cfg.save.empty()) return;
  // write fnet with the trained stage replaced by the trained values
  auto& tnet = Trained<Entry>::net;
  fnet.save(cfg.save, cfg.train_stage, [&](size_t i) { return tnet.get(tnet.w[i]); });
}

// Raw dump of the trained stage including TC accumulators, for exact resumption.
template <typename Entry>
static void save_checkpoint() {
  if (cfg.checkpoint.empty()) return;
  auto& tnet = Trained<Entry>::net;
  FILE* f = fopen((cfg.checkpoint + ".tmp").c_str(), "wb");
  if (!f) return;
  fwrite(tnet.w, sizeof(Entry), tnet.total, f);
  fclose(f);
  rename((cfg.checkpoint + ".tmp").c_str(), cfg.checkpoint.c_str());
}

static void report_locked() {
  auto now = Clock::now();
  double dt = chrono::duration<double>(now - t_window).count();
  double el = chrono::duration<double>(now - t_start).count();
  printf("%9ld games  avg %8.0f  len %6.0f  mps %5.2fM  |", finished, win.score_sum / win.games,
         (double)win.moves / win.games, win.moves / dt / 1e6);
  for (int r = 11; r <= 15; r++) {
    long c = 0;
    for (int q = r; q < 20; q++) c += win.tiles[q];
    printf(" %5d:%5.1f%%", 1 << r, 100.0 * c / win.games);
  }
  if (endgame) {
    static long last_tm = 0;
    long tm = table_moves.load();
    printf("  table moves %5.2f%%", 100.0 * (tm - last_tm) / max(1L, (long)win.moves));
    last_tm = tm;
    if (!ltabs.empty()) {
      static long last_lm = 0;
      long lm = lt_moves.load();
      printf(" (layered %5.2f%%)", 100.0 * (lm - last_lm) / max(1L, (long)win.moves));
      last_lm = lm;
    }
  }
  printf("  | %.0fs\n", el);
  fflush(stdout);
  win.clear();
  t_window = now;
}

// The policy's move from s: greedy on r + V(afterstate) among the moves the corner lock allows, replaced by a known
// winning table move. Fills the candidate afterstates; false when no move is legal.
template <typename Entry>
static bool choose(board_t s, board_t& best_as, uint32_t& best_r, float& best, board_t* cas, uint32_t* cr, int& nc,
                   bool& tabled, bool count, float* lt_p = nullptr) {
  if (lt_p) *lt_p = -1.0f;
  best = -1e30f;
  best_as = 0;
  best_r = 0;
  tabled = false;
  bool any = false;
  nc = 0;
  for (int d = 0; d < 4; d++) {
    board_t as = bb::move(s, d, cr[nc]);
    if (as != s) cas[nc++] = as;
  }
  nc = corner_filter(s, cfg.corner_lock, nc, cas, cr);
  for (int i = 0; i < nc; i++) {
    float v = cr[i] + value<Entry>(cas[i]);
    if (!any || v > best) best = v, best_as = cas[i], best_r = cr[i], any = true;
  }
  if (!any) return false;
  float pk = -1.0f;
  if (endgame) {  // a known winning table move replaces the network's choice
    int d = endgame->peek(s, &pk);
    if (d >= 0 && pk >= cfg.endgame_min) {
      uint32_t r;
      board_t as = bb::move(s, d, r);
      best = r + value<Entry>(as), best_as = as, best_r = r;
      tabled = true;
      if (count) table_moves++;
    } else {
      pk = -1.0f;
    }
  }
  if (!ltabs.empty()) {  // ... and so does a layered table's, when its probability is higher
    float pl;
    int d = lt::suggest(ltabs, s, &pl);
    if (lt_p && d >= 0) *lt_p = pl;
    if (d >= 0 && pl >= cfg.lt_min && pl > pk) {
      uint32_t r;
      board_t as = bb::move(s, d, r);
      best = r + value<Entry>(as), best_as = as, best_r = r;
      if (count && !tabled) table_moves++;
      if (count) lt_moves++;
      tabled = true;
    }
  }
  return true;
}

// Side branch (--branch P L): from a random non-chosen candidate afterstate, play L greedy moves and train that
// branch by a backward TD(lambda) sweep, bootstrapped from the policy's next value (0 at game over, the next stage's
// value at the stage boundary). Trains the off-policy positions a search compares, with on-policy targets.
template <typename Entry>
static void branch(bb::Rng& rng, const board_t* cas, const uint32_t* cr, int nc, board_t chosen,
                   vector<board_t>& bpath, vector<uint32_t>& brew) {
  auto& tnet = Trained<Entry>::net;
  const float lam = (float)cfg.lambda, lr = (float)cfg.alpha;
  int j = (int)rng.below((uint32_t)(nc - 1)), alt = -1;
  for (int i = 0, seen = 0; i < nc; i++) {
    if (cas[i] == chosen) continue;
    if (seen++ == j) { alt = i; break; }
  }
  if (alt < 0) return;
  bpath.clear();
  brew.clear();
  bpath.push_back(cas[alt]);
  brew.push_back(cr[alt]);
  board_t s = bb::spawn(cas[alt], rng);
  float G0 = 0;
  for (int k = 0;; k++) {
    board_t c2[4], as;
    uint32_t r2[4], r;
    int n2;
    float best;
    bool tb;
    if (!choose<Entry>(s, as, r, best, c2, r2, n2, tb, false)) { G0 = 0; break; }  // game over
    if (cfg.stop_at_boundary) {
      board_t v = cfg.downgrade ? eval_view(as, cfg.min_gap) : as;
      if (sf.of(v) != cfg.train_stage) { G0 = best; break; }
    }
    if (k == cfg.branch_len) { G0 = best; break; }  // cut: bootstrap from the policy's next r + V
    bpath.push_back(as);
    brew.push_back(r);
    s = bb::spawn(as, rng);
  }
  float G = G0;
  for (long t = (long)bpath.size() - 1; t >= 0; t--) {
    board_t v = cfg.downgrade ? eval_view(bpath[t], cfg.min_gap) : bpath[t];
    int st = sf.of(v);
    float nv = st == cfg.train_stage ? tnet.learn(v, G, lr, cfg.tc) : fnet.eval(v, st);
    G = brew[t] + (1 - lam) * nv + lam * G;
  }
}

template <typename Entry>
static void worker(int tid) {
  auto& tnet = Trained<Entry>::net;
  bb::Rng rng(cfg.seed * 1000003 + tid * 7919 + 17);
  vector<board_t> path;
  vector<uint32_t> rew;
  path.reserve(1 << 16);
  rew.reserve(1 << 16);
  vector<board_t> bpath;
  vector<uint32_t> brew;
  const float lam = (float)cfg.lambda, lr = (float)cfg.alpha;
  while (started.fetch_add(1) < cfg.episodes) {
    board_t s;
    if (!pool.empty() && rng.uniform() < cfg.pool_prob)
      s = pool[rng.below((uint32_t)pool.size())];
    else
      s = bb::initial_board(rng);
    path.clear();
    rew.clear();
    uint64_t score = 0;
    bool collecting = collect_file != nullptr;
    float G0 = 0;  // return beyond the last afterstate: 0 at game over, bootstrapped at a stage boundary
    long t_h = -1;  // index of the move from the episode's first layered-table state (P >= boot_minp)
    float p_h = 0, v_h = 0;
    for (;;) {
      if (collecting) {
        if (collect_fn.last_holds(s)) {
          collecting = false;
          lock_guard<mutex> g(stats_mu);
          if (collected < cfg.collect_max) {
            fwrite(&s, sizeof s, 1, collect_file);
            fflush(collect_file);
            collected++;
          }
        }
      }
      float best;
      board_t best_as;
      uint32_t best_r;
      board_t cas[4];
      uint32_t cr[4];
      int nc;
      bool tabled;
      float lp;
      if (!choose<Entry>(s, best_as, best_r, best, cas, cr, nc, tabled, true, &lp)) break;
      if (t_h < 0 && lp >= cfg.boot_minp) {
        t_h = (long)path.size(), p_h = lp;
        if (cfg.lt_calib && t_h > 0) v_h = value<Entry>(path[t_h - 1]);
      }
      if (cfg.stop_at_boundary) {
        board_t v = cfg.downgrade ? eval_view(best_as, cfg.min_gap) : best_as;
        if (sf.of(v) != cfg.train_stage) {  // leaving the trained stage: bootstrap from the next one
          G0 = best;
          score += best_r;
          break;
        }
      }
      if (cfg.branch_p > 0 && cfg.learn && !tabled && nc >= 2 && rng.uniform() < cfg.branch_p)
        branch<Entry>(rng, cas, cr, nc, best_as, bpath, brew);
      path.push_back(best_as);
      rew.push_back(best_r);
      score += best_r;
      s = bb::spawn(best_as, rng);
    }
    if (cfg.learn) {
      // backward TD(lambda) sweep; afterstates of frozen stages are not updated
      float G = G0;
      bool boot = cfg.boot_c1 != 0 && t_h > 0;
      for (long t = (long)path.size() - 1; t >= 0; t--) {
        if (boot && t == t_h - 1) G = (float)(cfg.boot_c0 + cfg.boot_c1 * p_h);  // exact sub-game value of s_h
        board_t v = cfg.downgrade ? eval_view(path[t], cfg.min_gap) : path[t];
        int st = sf.of(v);
        float nv = st == cfg.train_stage ? tnet.learn(v, G, lr, cfg.tc) : fnet.eval(v, st);
        G = rew[t] + (1 - lam) * nv + lam * G;
      }
    }
    if (cfg.lt_calib && t_h > 0) {  // Monte Carlo return from the handover state
      double g = G0;
      for (long t = t_h; t < (long)path.size(); t++) g += rew[t];
      lock_guard<mutex> lk(stats_mu);
      cal_n += 1, cal_p += p_h, cal_g += g, cal_pp += (double)p_h * p_h, cal_pg += p_h * g;
      cal_v += v_h, cal_vv += (double)v_h * v_h, cal_vg += v_h * g, cal_pv += (double)p_h * v_h, cal_gg += g * g;
      int b = std::min(9, std::max(0, (int)(p_h * 10)));
      cal_bn[b] += 1, cal_bg[b] += g, cal_bs[b] += g > 100000;
    }
    {
      lock_guard<mutex> g(stats_mu);
      win.games++;
      win.score_sum += score;
      win.moves += path.size();
      win.tiles[bb::max_rank(s)]++;
      finished++;
      if (finished % cfg.log_every == 0) report_locked();
      if (cfg.save_every && finished % cfg.save_every == 0) {
        save_all<Entry>();
        save_checkpoint<Entry>();
      }
      if (collect_file && cfg.collect_stop && collected >= cfg.collect_max) started = cfg.episodes;
    }
  }
}

static void scale_tc(nt::Net<float>&, float) {}
static void scale_tc(nt::Net<nt::TCEntry>& n, float f) {
  for (size_t i = 0; i < n.total; i++) n.w[i].e *= f, n.w[i].a *= f;
}

template <typename Entry>
static int run() {
  auto& tnet = Trained<Entry>::net;
  int S = sf.count();
  // fnet holds the frozen stages; the trained stage lives only in tnet.
  if (!cfg.load.empty()) {
    fnet.load(cfg.load, S, cfg.train_stage, [&](size_t i, float v) {
      if (!tnet.w) tnet.init(fnet.pats, 1);
      tnet.set(tnet.w[i], v);
    });
  } else {
    fnet.init(nt::parse_patterns(cfg.patterns), S);
    tnet.init(fnet.pats, 1);
    float v0 = (float)(cfg.init / fnet.features());
    for (int st = 0; st < S; st++)
      if (st != cfg.train_stage)
        for (size_t i = 0; i < fnet.stage_size; i++) fnet.w[st * fnet.stage_size + i] = v0;
    for (size_t i = 0; i < tnet.stage_size; i++) tnet.set(tnet.w[i], v0);
  }
  if (!cfg.resume.empty()) {
    FILE* f = fopen(cfg.resume.c_str(), "rb");
    if (!f || fread(tnet.w, sizeof(Entry), tnet.total, f) != tnet.total) {
      fprintf(stderr, "cannot resume from %s\n", cfg.resume.c_str());
      return 1;
    }
    fclose(f);
    if (cfg.tc_decay != 1.0) scale_tc(tnet, (float)cfg.tc_decay);
  }
  if (!cfg.pool.empty()) {
    FILE* f = fopen(cfg.pool.c_str(), "rb");
    if (!f) { fprintf(stderr, "cannot read pool %s\n", cfg.pool.c_str()); return 1; }
    board_t b;
    while (fread(&b, sizeof b, 1, f) == 1) pool.push_back(b);
    fclose(f);
    if (cfg.pool_last > 0 && (long)pool.size() > cfg.pool_last) pool.erase(pool.begin(), pool.end() - cfg.pool_last);
    printf("pool: %zu start positions\n", pool.size());
  }
  if (!cfg.collect.empty()) {
    collect_file = fopen(cfg.collect.c_str(), "wb");
    collect_fn = StageFn::parse(cfg.collect_when);
    if (!cfg.collect_max) cfg.collect_max = 1L << 40;
  }
  printf("patterns: %s  (%d features, stages %d, training stage %d, %.0f MB)\n", nt::pattern_string(fnet.pats).c_str(),
         fnet.features(), sf.count(), cfg.train_stage,
         (tnet.total * sizeof(Entry) + (fnet.total - fnet.stage_size) * sizeof(float)) / 1e6);
  if (!cfg.endgame_dir.empty()) {
    int max_rank[17] = {0};
    for (int k = 6; k <= 16; k++) max_rank[k] = std::min(16 - k, k == 6 ? 9 : 8);
    endgame.reset(new eg::Snake(6, max_rank, cfg.endgame_full));
    printf("endgame: %d tables from %s, played when p >= %.2f (lookup only)\n", endgame->load(cfg.endgame_dir),
           cfg.endgame_dir.c_str(), cfg.endgame_min);
  }
  for (auto& l : cfg.lts) {
    ltabs.emplace_back(new lt::Table(lt::snake_spec(l.k, l.r, l.caps), l.file));
    if (!ltabs.back()->ok()) {
      fprintf(stderr, "cannot open layered table %s\n", l.file.c_str());
      return 1;
    }
    printf("layered table %s: k=%d r=%d, played when p >= %.2f\n", l.file.c_str(), l.k, l.r, cfg.lt_min);
  }
  if (cfg.corner_lock) printf("corner lock: a max tile of rank >= %d stays in its corner\n", cfg.corner_lock);
  printf("mode: %s alpha=%g lambda=%g init=%g threads=%d episodes=%ld%s\n", cfg.tc ? "TC" : "TD", cfg.alpha, cfg.lambda,
         cfg.init, cfg.threads, cfg.episodes, cfg.learn ? "" : " (no learning)");
  if (cfg.branch_p > 0) printf("side branches: p=%g, %d greedy moves\n", cfg.branch_p, cfg.branch_len);
  fflush(stdout);
  t_start = t_window = Clock::now();
  vector<thread> th;
  for (int i = 0; i < cfg.threads; i++) th.emplace_back(worker<Entry>, i);
  for (auto& t : th) t.join();
  if (collect_file) {
    fclose(collect_file);
    printf("collected %ld positions\n", collected);
  }
  if (cfg.lt_calib && cal_n > 1) {
    double mp = cal_p / cal_n, mg = cal_g / cal_n, vp = cal_pp / cal_n - mp * mp, cv = cal_pg / cal_n - mp * mg;
    double c1 = vp > 0 ? cv / vp : 0, c0 = mg - c1 * mp;
    printf("lt-calib: %.0f handovers, mean P %.4f, mean return %.0f -> return ~ %.0f + %.0f * P\n", cal_n, mp, mg, c0, c1);
    double mv = cal_v / cal_n, vv = cal_vv / cal_n - mv * mv, vg = cal_gg / cal_n - mg * mg;
    double cpg = cv / sqrt(vp * vg), cvg = (cal_vg / cal_n - mv * mg) / sqrt(vv * vg), cpv = (cal_pv / cal_n - mp * mv) / sqrt(vp * vv);
    printf("lt-calib: correlations P~return %.3f, V(before)~return %.3f, P~V %.3f (mean V %.0f)\n", cpg, cvg, cpv, mv);
    for (int b = 0; b < 10; b++)
      if (cal_bn[b] > 0)
        printf("lt-calib: P in [%.1f, %.1f): %6.0f handovers, mean return %7.0f, return > 100k %.3f\n", b / 10.0, (b + 1) / 10.0,
               cal_bn[b], cal_bg[b] / cal_bn[b], cal_bs[b] / cal_bn[b]);
  }
  if (cfg.learn) {
    save_all<Entry>();
    save_checkpoint<Entry>();
  }
  return 0;
}

int main(int argc, char** argv) {
  for (int i = 1; i < argc; i++) {
    string a = argv[i];
    auto next = [&]() -> string {
      if (i + 1 >= argc) { fprintf(stderr, "missing value for %s\n", a.c_str()); exit(1); }
      return argv[++i];
    };
    if (a == "--patterns") cfg.patterns = next();
    else if (a == "--load") cfg.load = next();
    else if (a == "--save") cfg.save = next();
    else if (a == "--checkpoint") cfg.checkpoint = next();
    else if (a == "--resume") cfg.resume = next();
    else if (a == "--stages") cfg.stages = next();
    else if (a == "--train-stage") cfg.train_stage = stoi(next());
    else if (a == "--pool") cfg.pool = next();
    else if (a == "--pool-prob") cfg.pool_prob = stod(next());
    else if (a == "--pool-last") cfg.pool_last = stol(next());
    else if (a == "--collect") cfg.collect = next();
    else if (a == "--collect-when") cfg.collect_when = next();
    else if (a == "--collect-max") cfg.collect_max = stol(next());
    else if (a == "--collect-stop") cfg.collect_stop = true;
    else if (a == "--threads") cfg.threads = stoi(next());
    else if (a == "--episodes") cfg.episodes = stol(next());
    else if (a == "--alpha") cfg.alpha = stod(next());
    else if (a == "--tc") cfg.tc = true;
    else if (a == "--no-learn") cfg.learn = false;
    else if (a == "--no-downgrade") cfg.downgrade = false;
    else if (a == "--min-gap") cfg.min_gap = stoi(next());
    else if (a == "--stop-at-boundary") cfg.stop_at_boundary = true;
    else if (a == "--corner-lock") cfg.corner_lock = stoi(next());
    else if (a == "--endgame-dir") cfg.endgame_dir = next();
    else if (a == "--endgame-min") cfg.endgame_min = stof(next());
    else if (a == "--endgame-full") cfg.endgame_full = stoi(next());
    else if (a == "--endgame-lt") {
      cfg.lts.emplace_back();
      cfg.lts.back().file = next();
    }
    else if (a == "--lt-k" && !cfg.lts.empty()) cfg.lts.back().k = stoi(next());
    else if (a == "--lt-rank" && !cfg.lts.empty()) cfg.lts.back().r = stoi(next());
    else if (a == "--lt-min") cfg.lt_min = stof(next());
    else if (a == "--lt-caps") {
      string v = next();
      for (size_t q = 0; q < v.size();) {
        size_t e = v.find(',', q);
        if (e == string::npos) e = v.size();
        if (!cfg.lts.empty()) cfg.lts.back().caps.push_back(stoi(v.substr(q, e - q)));
        q = e + 1;
      }
    }
    else if (a == "--lambda") cfg.lambda = stod(next());
    else if (a == "--init") cfg.init = stod(next());
    else if (a == "--tc-decay") cfg.tc_decay = stod(next());
    else if (a == "--log") cfg.log_every = stol(next());
    else if (a == "--lt-boot") { cfg.boot_c0 = stod(next()); cfg.boot_c1 = stod(next()); cfg.boot_minp = stof(next()); }
    else if (a == "--lt-calib") { cfg.lt_calib = true; if (cfg.boot_minp > 1.0f) cfg.boot_minp = 0.0f; }
    else if (a == "--branch") { cfg.branch_p = stod(next()); cfg.branch_len = stoi(next()); }
    else if (a == "--save-every") cfg.save_every = stol(next());
    else if (a == "--seed") cfg.seed = stoull(next());
    else { fprintf(stderr, "unknown option %s\n", a.c_str()); return 1; }
  }
  if (!cfg.stages.empty()) sf = StageFn::parse(cfg.stages);
  if (!sf.sums.empty()) cfg.downgrade = false;  // downgrading would change the tile sum
  if (cfg.train_stage < 0 || cfg.train_stage >= sf.count()) { fprintf(stderr, "bad --train-stage\n"); return 1; }
  if (cfg.tc) return run<nt::TCEntry>();
  return run<float>();
}
