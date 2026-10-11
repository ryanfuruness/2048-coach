// Plays full games with expectimax search and reports statistics.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <unistd.h>
#include "board.h"
#include "game.h"
#include "ntuple.h"
#include "search.h"
#include "endgame.h"
#include "layered.h"
#include "block.h"

using namespace std;
using Clock = chrono::steady_clock;

struct Config {
  string weights, stages, record, start;
  string collect, collect_when;  // record the first board satisfying all bounds of collect_when
  int threads = 16;
  long games = 100;
  uint64_t seed = 12345;
  SearchParams sp;
  bool downgrade = true;
  int min_gap = 10;
  int tt_bits = 20;
  bool quiet = false;
  bool quantize = false;
  int stop_at = 0;  // end a game as soon as a tile of this rank appears (0 = never)
  long max_moves = 0;  // end a game after this many moves (0 = never)
  long stop_sum = 0;   // end a game once the tile sum reaches this (0 = never)
  string analyze;      // print move values of this board (16 hex digits, cell 0 first) and exit
  vector<int> stage_depth;  // optional per-stage max search depth (indexed by the root's stage)
  int root_down = 0;        // >0: search on the root board downgraded while it holds a tile >= this rank
  int disagree = 0;         // >0: print this many positions where depth 1 and depth 2 choose differently
  string ens_weights, ens_stages;  // ensemble partner network and its stage spec
  vector<int> ens_stage_depth;     // replace mode: max depth by the second network's stage
  int root_down_gap = 5;    // smallest rank that may be the gap
  long root_down_skip_lo = 0, root_down_skip_hi = 0;  // no root view while the real tile sum is in [lo, hi)
  int watch = -1;  // >= 0: print every board, sleeping this many ms per move
  int endgame = 0;           // >0: play exact endgame-table moves in snake endings with >= this many locked tiles
  float endgame_min = 0.1f;  // ... when their success probability is at least this
  int endgame_full = 0;      // ... only for chains that collapse completely (1; 2: also below the corner tile)
  float endgame_leaf = 0;    // >0: search leaves that are endings get value endgame_leaf * P(success)
  string endgame_dir;        // load the tables from this directory, and save them back at the end
  struct Lt {               // a layered (on-disk) snake table: --endgame-lt FILE --lt-k K --lt-rank R --lt-caps c,...
    string file;             // (repeat the group for more tables)
    int k = 5, r = 10;
    vector<int> caps;
    int rank_lo = 0, rank_hi = 15;  // --lt-ranks LO HI: only when the real largest tile rank is in [LO, HI]
    bool real = false;              // --lt-real: always match this table on the real board (not the root view)
  };
  vector<Lt> lts;
  float lt_min = 0.5f;       // ... played when its probability is at least this and above the other tables'
  int lt_max_rank = 15;      // ... only on boards whose largest tile is at most this rank (matched on the real board)
  bool endgame_real = false; // match the k>=6 tables on the real board, not the root-downgraded view
  string block_dir;          // --block-tables DIR: exact block tables (src/block.h; workstream pdf), played when no
  float block_min = 0.0f;    // snake table decided and their probability is >= --block-min
  bool block_lock = false;   // --block-lock: in the block formation (blk::block_formation), play the best searched move
                             // that keeps it, if any (as the corner lock)
  bool endgame_nosave = false;  // do not write the tables back to --endgame-dir at the end
  int grad_mode = 0, grad_min_rank = 14, grad_depth = 6;
  long grad_max_sum = 0;
  float grad_prob_cut = 0.002f;
  string dump_train;         // --dump-train FILE LO HI: append (afterstate, searched value) of every searched root
  long dump_lo = 0, dump_hi = 0;  // move whose afterstate tile sum is in [LO, HI) (search-bootstrapped training data)
  uint32_t dump_tree = 0;    // --dump-tree RATE: also interior chance nodes, each with probability RATE/65536
  int ro_n = 0, ro_horizon = 200, ro_min_stage = 2;  // --rollouts N H CLOSE MINSTAGE: when the search's best and
  float ro_close = 0.005f;                            // second root values differ by < CLOSE*|best|, re-rank the close
                                                      // moves by N greedy playouts of H moves (+ value at the end)
  bool lt_view = false;      // match the layered tables on the root view (like the k>=6 tables) instead of the real board
};

struct Result {
  long id;
  uint64_t score;
  int max_rank;
  long moves;
  double secs;
  long evals;
  double depth_sum;
  long escalations;
  bool reached_sum;
  long table_moves;
  long lt_moves;
};

static Config cfg;
static vector<board_t> starts;  // optional start positions (game i starts from starts[i % n])
static nt::Net<float> net;
static nt::Net<int16_t> qnet;
static nt::Net<int16_t> qnet2;  // optional ensemble partner (always quantized)
static Evaluator ev;
static atomic<long> next_game{0};
static mutex mu;
static vector<Result> results;
static StageFn collect_fn;
static FILE* collect_file = nullptr;
static long collected = 0;
static const char* DIRS = "URDL";
static unique_ptr<eg::Snake> endgame;
static vector<unique_ptr<lt::Table>> ltabs;
static blk::Tables btabs;  // --block-tables
static atomic<long> block_moves{0}, block_locks{0};
static Evaluator ev_grad;  // copy of ev with gradient leaves (--gradient)
static FILE* dump_file = nullptr;
static atomic<long> rollout_checks{0}, rollout_changes{0};
static mutex dump_mu;
// Best move of the layered table for the real-frame board b and its probability, or -1.
// One greedy playout from afterstate a: up to h moves of the 1-ply policy (corner lock, k>=6 table moves), returning the
// rewards collected plus the network's value of the last afterstate (0 if the game dies).
static float playout(board_t a, int h, bb::Rng& rng) {
  float acc = 0;
  board_t last = a;
  board_t s = bb::spawn(a, rng);
  for (int step = 0; step < h; step++) {
    board_t as[4];
    uint32_t rw[4];
    int n = 0;
    for (int d = 0; d < 4; d++) {
      board_t x = bb::move(s, d, rw[n]);
      if (x != s) as[n++] = x;
    }
    n = corner_filter(s, cfg.sp.corner_lock, n, as, rw);
    if (n == 0) return acc;  // dead
    int bi = 0;
    float bv = -1e30f;
    if (endgame) {
      float p;
      int td = endgame->peek(s, &p);
      if (td >= 0 && p >= cfg.endgame_min) {
        uint32_t r;
        board_t x = bb::move(s, td, r);
        acc += r, last = x, s = bb::spawn(x, rng);
        continue;
      }
    }
    for (int i = 0; i < n; i++) {
      float v = rw[i] + ev(as[i]);
      if (v > bv) bv = v, bi = i;
    }
    acc += rw[bi], last = as[bi], s = bb::spawn(as[bi], rng);
  }
  return acc + ev(last);
}
static bool real_sum_in(board_t b, long lo, long hi) {
  long t = (long)tile_sum(b);
  return hi > lo && t >= lo && t < hi;
}
static vector<int> lt_rank_lo, lt_rank_hi;
static vector<unique_ptr<lt::Table>> ltabs_real;  // tables matched on the real board regardless of --lt-view
static vector<int> ltr_rank_lo, ltr_rank_hi;
static int lt_suggest(board_t b, float* prob, int real_max) {
  return lt::suggest(ltabs, b, prob, lt_rank_lo.data(), lt_rank_hi.data(), real_max);
}
static bool endgame_leaf(board_t a, float* v) {
  float p = endgame->after_value(a);
  if (p < 0) return false;
  *v = cfg.endgame_leaf * p;
  return true;
}

static void print_board(const Game& g, int dir, const SearchStats& st, double ms) {
  static const char* colors[] = {"\033[0m",       "\033[38;5;238m", "\033[38;5;240m", "\033[38;5;208m",
                                 "\033[38;5;202m", "\033[38;5;196m", "\033[38;5;160m", "\033[38;5;220m",
                                 "\033[38;5;226m", "\033[38;5;190m", "\033[38;5;154m", "\033[38;5;46m",
                                 "\033[38;5;51m",  "\033[38;5;39m",  "\033[38;5;27m",  "\033[38;5;93m",
                                 "\033[38;5;201m", "\033[38;5;199m"};
  printf("\033[H\033[2J");
  printf("  score %llu   moves %ld   last move %c   search depth %d  (%.1f ms)\n\n", (unsigned long long)g.score,
         g.moves, dir >= 0 ? DIRS[dir] : '-', st.depth, ms);
  for (int r = 0; r < 4; r++) {
    printf("  ");
    for (int c = 0; c < 4; c++) {
      int v = g.r[r * 4 + c];
      if (v) printf("%s\033[1m%7d\033[0m", colors[v < 18 ? v : 17], 1 << v);
      else printf("%7s", ".");
    }
    printf("\n\n");
  }
  fflush(stdout);
}

static void worker(int tid) {
  (void)tid;
  Searcher search(ev, cfg.tt_bits);
  Searcher search_g(ev_grad, cfg.tt_bits);
  search.tree_rate = dump_file ? cfg.dump_tree : 0;
  if (endgame && cfg.endgame_leaf > 0) search.leaf_oracle = endgame_leaf;
  for (;;) {
    long id = next_game.fetch_add(1);
    if (id >= cfg.games) break;
    bb::Rng rng(cfg.seed + 0x9E3779B97F4A7C15ULL * (id + 1));
    bb::Rng ro_rng(cfg.seed * 7919 + 0xC2B2AE3D27D4EB4FULL * (id + 1));  // playouts: separate stream (games stay paired)
    Game g;
    g.reset(rng);
    if (!starts.empty()) {
      board_t b = starts[id % starts.size()];
      for (int i = 0; i < 16; i++) g.r[i] = bb::cell(b, i);
    }
    string rec;
    if (!cfg.record.empty()) {
      for (int i = 0; i < 16; i++) rec += "0123456789abcdefghijklmnopqrstuv"[g.r[i]];
      rec += ' ';
    }
    auto t0 = Clock::now();
    SearchStats st;
    double depth_sum = 0;
    bool collecting = collect_file != nullptr;
    bool reached_sum = false;
    long table_moves = 0, lt_moves = 0;
    for (;;) {
      board_t b = to_search_board(g);
      const board_t real_b = b;
      int real_max = bb::max_rank(b);
      if (cfg.root_down && !(real_sum_in(real_b, cfg.root_down_skip_lo, cfg.root_down_skip_hi)))
        b = downgrade_view(b, cfg.root_down, cfg.root_down_gap);
      if (collecting && collect_fn.last_holds(b)) {
        collecting = false;
        lock_guard<mutex> lk(mu);
        fwrite(&b, sizeof b, 1, collect_file);
        fflush(collect_file);
        collected++;
      }
      // stop conditions come after the collection, so both can name the same position
      if (cfg.stop_at && g.max_rank() >= cfg.stop_at) break;
      if (cfg.stop_sum && (long)g.tile_sum() >= cfg.stop_sum) {
        reached_sum = true;
        break;
      }
      auto tm = Clock::now();
      SearchParams sp = cfg.sp;
      if (!cfg.stage_depth.empty()) {
        int stg = ev.stages.of(b);
        sp.max_depth = cfg.stage_depth[min(stg, (int)cfg.stage_depth.size() - 1)];
        if (!cfg.ens_stage_depth.empty() && ev.ens_mode == 3 && stg >= ev.ens_from_stage) {
          int s2 = ev.stages2.of(b);
          sp.max_depth = cfg.ens_stage_depth[min(s2, (int)cfg.ens_stage_depth.size() - 1)];
        }
        if (sp.min_depth > sp.max_depth) sp.min_depth = sp.max_depth;
      }
      int d = -1;
      float pt = -1.0f;
      if (endgame) {
        d = endgame->suggest(cfg.endgame_real ? real_b : b, &pt);
        if (d >= 0 && pt < cfg.endgame_min) d = -1;
        if (d >= 0) table_moves++;
      }
      if ((!ltabs.empty() || !ltabs_real.empty()) && real_max <= cfg.lt_max_rank) {
        float pl;
        int dl = lt_suggest(cfg.lt_view ? b : real_b, &pl, real_max);
        bool real_first = false;
        if (!ltabs_real.empty()) {
          float pr;
          int dr = lt::suggest(ltabs_real, real_b, &pr, ltr_rank_lo.data(), ltr_rank_hi.data(), real_max);
          // a real-board table is exact; view-matched tables can be distorted (and claim higher p) -> it goes first
          if (dr >= 0 && pr >= cfg.lt_min) dl = dr, pl = pr, real_first = true;
          else if (dr >= 0 && pr > pl) dl = dr, pl = pr;
        }
        if (dl >= 0 && pl >= cfg.lt_min && (d < 0 || pl > pt || real_first)) {
          if (d < 0) table_moves++;
          d = dl;
          lt_moves++;
        }
      }
      if (d < 0 && !btabs.empty()) {
        float pb;
        int db = blk::suggest(btabs, real_b, &pb);
        if (db >= 0 && pb >= cfg.block_min) d = db, table_moves++, block_moves++;
      }
      if (d < 0) {
        if (cfg.grad_mode && real_max >= cfg.grad_min_rank && (long)tile_sum(real_b) < cfg.grad_max_sum) {
          SearchParams gp = sp;
          gp.max_depth = cfg.grad_depth;
          gp.min_depth = std::min(gp.min_depth, gp.max_depth);
          gp.prob_cut = cfg.grad_prob_cut;
          d = search_g.best_move(b, gp, &st);
        } else {
          d = search.best_move(b, sp, &st);
          if (cfg.ro_n > 0 && search.last_n >= 2 && ev.stages.of(b) >= cfg.ro_min_stage) {
            float best = -1e30f, sec = -1e30f;
            for (int i = 0; i < search.last_n; i++) {
              float v = search.last_reward[i] + search.last_value[i];
              if (v > best) sec = best, best = v;
              else if (v > sec) sec = v;
            }
            if (best - sec < cfg.ro_close * fabsf(best)) {
              float bq = -1e30f;
              int bd = d;
              for (int i = 0; i < search.last_n; i++) {
                float v = search.last_reward[i] + search.last_value[i];
                if (best - v >= cfg.ro_close * fabsf(best)) continue;  // only the close moves
                double q = 0;
                for (int k = 0; k < cfg.ro_n; k++) q += playout(search.last_after[i], cfg.ro_horizon, ro_rng);
                q = search.last_reward[i] + q / cfg.ro_n;
                if (q > bq) bq = (float)q, bd = search.last_dir[i];
              }
              if (bd != d) rollout_changes++;
              rollout_checks++;
              d = bd;
            }
          }
          if (cfg.block_lock && d >= 0 && search.last_n > 1) {
            float vals[4];
            for (int i = 0; i < search.last_n; i++) vals[i] = search.last_reward[i] + search.last_value[i];
            int bd = blk::lock_choice(real_b, search.last_n, search.last_dir, vals);
            if (bd >= 0 && bd != d) d = bd, block_locks++;
          }
          if (dump_file && search.last_n > 0) {
            struct Rec { board_t a; float v; };
            vector<Rec> recs;
            for (int i = 0; i < search.last_n; i++) {
              long t = (long)tile_sum(search.last_after[i]);
              if (t >= cfg.dump_lo && t < cfg.dump_hi) recs.push_back(Rec{search.last_after[i], search.last_value[i]});
            }
            for (auto& ts : search.tree_samples) {
              long t = (long)tile_sum(ts.first);
              if (t >= cfg.dump_lo && t < cfg.dump_hi) recs.push_back(Rec{ts.first, ts.second});
            }
            search.tree_samples.clear();
            if (!recs.empty()) {
              lock_guard<mutex> lk(dump_mu);
              for (auto& r : recs) {
                fwrite(&r.a, sizeof(board_t), 1, dump_file);
                fwrite(&r.v, sizeof(float), 1, dump_file);
              }
            }
          }
        }
      }
      if (cfg.disagree > 0) {
        static atomic<int> shown{0};
        float v1[4], v2[4];
        search.move_values(b, 1, v1, cfg.sp);
        search.move_values(b, 2, v2, cfg.sp);
        int m1 = -1, m2 = -1;
        for (int k = 0; k < 4; k++) {
          if (!std::isnan(v1[k]) && (m1 < 0 || v1[k] > v1[m1])) m1 = k;
          if (!std::isnan(v2[k]) && (m2 < 0 || v2[k] > v2[m2])) m2 = k;
        }
        if (m1 != m2 && shown.fetch_add(1) < cfg.disagree) {
          lock_guard<mutex> lk(mu);
          printf("--- disagreement (sum %u, depth1 %c, depth2 %c)\n", tile_sum(b), DIRS[m1], DIRS[m2]);
          for (int r = 0; r < 4; r++) {
            for (int c = 0; c < 4; c++) {
              int v = bb::cell(b, r * 4 + c);
              printf("%7d", v ? 1 << v : 0);
            }
            printf("\n");
          }
          for (int k = 0; k < 4; k++)
            if (!std::isnan(v1[k])) printf("  %c: depth1 %9.0f  depth2 %9.0f\n", DIRS[k], v1[k], v2[k]);
        }
      }
      if (cfg.watch >= 0) {
        print_board(g, d, st, 1000 * chrono::duration<double>(Clock::now() - tm).count());
        if (cfg.watch > 0) usleep(cfg.watch * 1000);
      }
      if (d < 0 || !g.apply(d)) {
        // fall back to any legal move if the mapped board disagrees (should not happen)
        bool moved = false;
        for (int k = 0; k < 4 && !moved; k++) moved = g.apply(k), d = k;
        if (!moved) break;
      }
      depth_sum += st.depth;
      if (cfg.max_moves && g.moves >= cfg.max_moves) break;

      Game before = g;
      g.spawn(rng);
      if (!cfg.record.empty()) {
        int c = 0;
        for (int i = 0; i < 16; i++)
          if (before.r[i] != g.r[i]) c = i;
        rec += DIRS[d];
        rec += "0123456789abcdef"[c];
        rec += g.r[c] == 1 ? '2' : '4';
      }
    }
    double secs = chrono::duration<double>(Clock::now() - t0).count();
    Result r{id, g.score, g.max_rank(), g.moves, secs, st.evals, depth_sum, st.escalations, reached_sum, table_moves, lt_moves};
    lock_guard<mutex> lk(mu);
    results.push_back(r);
    if (!cfg.quiet)
      printf("game %4ld  score %8llu  max %6d  moves %6ld  %7.1fs  %6.1f ms/move  depth %.2f  evals/move %.0f  sum %llu\n",
             id, (unsigned long long)r.score, 1 << r.max_rank, r.moves, secs, 1000 * secs / max(1L, r.moves),
             depth_sum / max(1L, r.moves), (double)st.evals / max(1L, r.moves), (unsigned long long)g.tile_sum());
    fflush(stdout);
    if (!cfg.record.empty()) {
      FILE* f = fopen(cfg.record.c_str(), "a");
      if (f) {
        fprintf(f, "%ld %llu %d %s\n", id, (unsigned long long)g.score, 1 << g.max_rank(), rec.c_str());
        fclose(f);
      }
    }
  }
}

static void summary() {
  size_t n = results.size();
  if (!n) return;
  vector<uint64_t> sc;
  double sum = 0, moves = 0, secs = 0, depth = 0, evals = 0, esc = 0, tmoves = 0, ltmoves = 0;
  long reached = 0;
  long cnt[32] = {0};
  for (auto& r : results) {
    sc.push_back(r.score);
    sum += r.score;
    moves += r.moves;
    secs += r.secs;
    depth += r.depth_sum;
    evals += r.evals;
    esc += r.escalations;
    reached += r.reached_sum;
    tmoves += r.table_moves;
    ltmoves += r.lt_moves;
    cnt[r.max_rank]++;
  }
  sort(sc.begin(), sc.end());
  double mean = sum / n, var = 0;
  for (auto s : sc) var += (s - mean) * (s - mean);
  double sd = n > 1 ? sqrt(var / (n - 1)) : 0;
  printf("\n=== %zu games ===\n", n);
  printf("mean score %.0f (+- %.0f)  median %llu  max %llu  min %llu\n", mean, sd / sqrt((double)n),
         (unsigned long long)sc[n / 2], (unsigned long long)sc.back(), (unsigned long long)sc.front());
  printf("avg moves %.0f   avg %.2f ms/move   depth %.2f   evals/move %.0f   close-call escalations %.2f%%\n",
         moves / n, 1000 * secs / moves, depth / moves, evals / moves, 100 * esc / moves);
  if (endgame)
    printf("endgame table moves %.2f%%  (tables %.0f MB)\n", 100 * tmoves / moves, endgame->memory() / 1e6);
  if (!ltabs.empty() || !ltabs_real.empty()) printf("layered table moves %.2f%%\n", 100 * ltmoves / moves);
  if (!btabs.empty()) printf("block table moves %.2f%%\n", 100 * block_moves.load() / moves);
  if (cfg.block_lock) printf("block lock changed %.3f%% of the moves\n", 100 * block_locks.load() / moves);
  if (cfg.ro_n > 0)
    printf("rollout checks %.2f%% of moves, %ld moves changed\n", 100.0 * rollout_checks / moves, rollout_changes.load());
  if (cfg.stop_sum)
    printf("  reached tile sum %ld: %.2f%% +- %.2f  (%ld)\n", cfg.stop_sum, 100.0 * reached / n,
           100.0 * sqrt((double)reached / n * (1 - (double)reached / n) / n), reached);
  for (int r = 11; r < 20; r++) {
    long c = 0;
    for (int q = r; q < 32; q++) c += cnt[q];
    if (c == 0 && r > 15) break;
    printf("  reached %6d: %6.2f%%  (%ld)\n", 1 << r, 100.0 * c / n, c);
  }
}

int main(int argc, char** argv) {
  for (int i = 1; i < argc; i++) {
    string a = argv[i];
    auto next = [&]() -> string {
      if (i + 1 >= argc) { fprintf(stderr, "missing value for %s\n", a.c_str()); exit(1); }
      return argv[++i];
    };
    if (a == "--weights") cfg.weights = next();
    else if (a == "--stages") cfg.stages = next();
    else if (a == "--threads") cfg.threads = stoi(next());
    else if (a == "--games") cfg.games = stol(next());
    else if (a == "--seed") cfg.seed = stoull(next());
    else if (a == "--depth") cfg.sp.max_depth = stoi(next());
    else if (a == "--min-depth") cfg.sp.min_depth = stoi(next());
    else if (a == "--budget") cfg.sp.budget = stol(next());
    else if (a == "--prob-cut") cfg.sp.prob_cut = stof(next());
    else if (a == "--vprune") cfg.sp.vprune = stof(next());
    else if (a == "--beam") cfg.sp.beam = stoi(next());
    else if (a == "--budget-hi") cfg.sp.budget_hi = stol(next());
    else if (a == "--close") cfg.sp.close = stof(next());
    else if (a == "--corner-lock") cfg.sp.corner_lock = stoi(next());
    else if (a == "--chain-lock") cfg.sp.chain_lock = stoi(next());
    else if (a == "--chain-min-rank") cfg.sp.chain_min_rank = stoi(next());
    else if (a == "--endgame") cfg.endgame = stoi(next());
    else if (a == "--endgame-min") cfg.endgame_min = stof(next());
    else if (a == "--endgame-full") cfg.endgame_full = stoi(next());
    else if (a == "--endgame-leaf") cfg.endgame_leaf = stof(next());
    else if (a == "--endgame-dir") cfg.endgame_dir = next();
    else if (a == "--endgame-lt") {
      cfg.lts.emplace_back();
      cfg.lts.back().file = next();
    }
    else if (a == "--endgame-real") cfg.endgame_real = true;
    else if (a == "--endgame-nosave") cfg.endgame_nosave = true;
    else if (a == "--lt-view") cfg.lt_view = true;
    else if (a == "--dump-tree") cfg.dump_tree = (uint32_t)stoul(next());
    else if (a == "--rollouts") {
      cfg.ro_n = stoi(next());
      cfg.ro_horizon = stoi(next());
      cfg.ro_close = stof(next());
      cfg.ro_min_stage = stoi(next());
    }
    else if (a == "--dump-train") {
      cfg.dump_train = next();
      cfg.dump_lo = stol(next());
      cfg.dump_hi = stol(next());
    }
    else if (a == "--lt-k" && !cfg.lts.empty()) cfg.lts.back().k = stoi(next());
    else if (a == "--lt-rank" && !cfg.lts.empty()) cfg.lts.back().r = stoi(next());
    else if (a == "--lt-real" && !cfg.lts.empty()) cfg.lts.back().real = true;
    else if (a == "--lt-ranks" && !cfg.lts.empty()) {
      cfg.lts.back().rank_lo = stoi(next());
      cfg.lts.back().rank_hi = stoi(next());
    }
    else if (a == "--lt-min") cfg.lt_min = stof(next());
    else if (a == "--lt-max-rank") cfg.lt_max_rank = stoi(next());
    else if (a == "--block-tables") cfg.block_dir = next();
    else if (a == "--block-min") cfg.block_min = stof(next());
    else if (a == "--block-lock") cfg.block_lock = true;
    else if (a == "--lt-caps") {
      string v = next();
      for (size_t p = 0; p < v.size();) {
        size_t q = v.find(',', p);
        if (q == string::npos) q = v.size();
        if (!cfg.lts.empty()) cfg.lts.back().caps.push_back(stoi(v.substr(p, q - p)));
        p = q + 1;
      }
    }
    else if (a == "--max-moves") cfg.max_moves = stol(next());
    else if (a == "--stop-sum") cfg.stop_sum = stol(next());
    else if (a == "--analyze") cfg.analyze = next();
    else if (a == "--root-downgrade") cfg.root_down = stoi(next());
    else if (a == "--disagree") cfg.disagree = stoi(next());
    else if (a == "--shaping") ev.shaping = stof(next());
    else if (a == "--heuristic-only") ev.heuristic_only = true;
    else if (a == "--snake") ev.snake_rho = stof(next());
    else if (a == "--snake-pen") {  // --snake-pen W K LO HI: leaf -= W * snake_break(leaf, K) for view tile sums in [LO, HI)
      ev.snake_pen = stof(next());
      ev.pen_k = stoi(next());
      ev.pen_lo = (uint32_t)stoul(next());
      ev.pen_hi = (uint32_t)stoul(next());
    }
    else if (a == "--exposed-pen") {  // --exposed-pen W LO HI: leaf -= W * exposed_cells(leaf) for view tile sums in [LO, HI)
      ev.exposed_pen = stof(next());
      ev.exp_lo = (uint32_t)stoul(next());
      ev.exp_hi = (uint32_t)stoul(next());
    }
    else if (a == "--ens-weights") cfg.ens_weights = next();
    else if (a == "--ens-stages") cfg.ens_stages = next();
    else if (a == "--ens-mode") {
      string m = next();
      ev.ens_mode = m == "min" ? 2 : m == "replace" ? 3 : 1;
    }
    else if (a == "--ens-stage-depth") {  // max depth per stage of the second network (replace mode)
      string v = next();
      for (size_t p = 0; p < v.size();) {
        size_t q = v.find(',', p);
        if (q == string::npos) q = v.size();
        cfg.ens_stage_depth.push_back(stoi(v.substr(p, q - p)));
        p = q + 1;
      }
    }
    else if (a == "--ens-from-stage") ev.ens_from_stage = stoi(next());
    else if (a == "--root-downgrade-gap") cfg.root_down_gap = stoi(next());
    else if (a == "--root-downgrade-skip") {
      cfg.root_down_skip_lo = stol(next());
      cfg.root_down_skip_hi = stol(next());
    }
    else if (a == "--stage-depth") {  // a later --stage-depth replaces an earlier one
      string v = next();
      cfg.stage_depth.clear();
      for (size_t p = 0; p < v.size();) {
        size_t q = v.find(',', p);
        if (q == string::npos) q = v.size();
        cfg.stage_depth.push_back(stoi(v.substr(p, q - p)));
        p = q + 1;
      }
    }
    else if (a == "--no-downgrade") cfg.downgrade = false;
    else if (a == "--min-gap") cfg.min_gap = stoi(next());
    else if (a == "--leaf-view") {
      ev.view_top = stoi(next());
      ev.view_gap = stoi(next());
    } else if (a == "--leaf-view-max-sum") ev.view_max_sum = (uint32_t)stoul(next());
    else if (a == "--leaf-view-safe") ev.view_safe = true;
    else if (a == "--gradient") {  // --gradient MODE MIN_RANK MAX_SUM DEPTH PROB_CUT: while the root holds a tile of
      cfg.grad_mode = stoi(next());  // rank >= MIN_RANK and its tile sum is below MAX_SUM, search with the gradient
      cfg.grad_min_rank = stoi(next());  // heuristic (1: rows left to right, 2: snake rows) at the leaves instead of
      cfg.grad_max_sum = stol(next());   // the network, to DEPTH with probability cut PROB_CUT
      cfg.grad_depth = stoi(next());
      cfg.grad_prob_cut = stof(next());
    }
    else if (a == "--tt-bits") cfg.tt_bits = stoi(next());
    else if (a == "--record") cfg.record = next();
    else if (a == "--start") cfg.start = next();
    else if (a == "--collect") cfg.collect = next();
    else if (a == "--collect-when") cfg.collect_when = next();
    else if (a == "--quiet") cfg.quiet = true;
    else if (a == "--quantize") cfg.quantize = true;
    else if (a == "--stop-at") cfg.stop_at = stoi(next());
    else if (a == "--watch") cfg.watch = stoi(next()), cfg.games = 1, cfg.threads = 1;
    else { fprintf(stderr, "unknown option %s\n", a.c_str()); return 1; }
  }
  if (cfg.weights.empty()) { fprintf(stderr, "--weights required\n"); return 1; }
  if (!cfg.start.empty()) {
    FILE* f = fopen(cfg.start.c_str(), "rb");
    if (!f) { fprintf(stderr, "cannot read %s\n", cfg.start.c_str()); return 1; }
    board_t b;
    while (fread(&b, sizeof b, 1, f) == 1) starts.push_back(b);
    fclose(f);
    printf("%zu start positions from %s\n", starts.size(), cfg.start.c_str());
  }
  if (cfg.quantize) {
    nt::load_quantized(cfg.weights, qnet);
    ev.qnet = &qnet;
  } else {
    net.load(cfg.weights);
    ev.net = &net;
  }
  ev.downgrade = cfg.downgrade;
  ev.min_gap = cfg.min_gap;
  if (!cfg.stages.empty()) ev.stages = StageFn::parse(cfg.stages);
  if (!ev.stages.sums.empty()) ev.downgrade = false;  // downgrading would change the tile sum
  if (!cfg.ens_weights.empty()) {
    nt::load_quantized(cfg.ens_weights, qnet2);
    ev.qnet2 = &qnet2;
    if (!cfg.ens_stages.empty()) ev.stages2 = StageFn::parse(cfg.ens_stages);
    if (!ev.ens_mode) ev.ens_mode = 1;
    printf("ensemble with %s (%s, %s)\n", cfg.ens_weights.c_str(), nt::pattern_string(qnet2.pats).c_str(),
           ev.ens_mode == 3 ? "replace" : ev.ens_mode == 2 ? "min" : "mean");
  }
  if (!cfg.dump_train.empty()) {
    dump_file = fopen(cfg.dump_train.c_str(), "ab");
    if (!dump_file) { fprintf(stderr, "cannot write %s\n", cfg.dump_train.c_str()); return 1; }
  }
  ev_grad = ev;
  ev_grad.gradient = cfg.grad_mode;
  ev_grad.grad_max_sum = 0;
  if (cfg.grad_mode)
    printf("gradient search: roots with a tile >= rank %d and sum < %ld, depth %d, prob cut %g (%s rows)\n",
           cfg.grad_min_rank, cfg.grad_max_sum, cfg.grad_depth, cfg.grad_prob_cut, cfg.grad_mode == 2 ? "snake" : "plain");
  if (ev.stages.count() != ev.nstages()) {
    fprintf(stderr, "stage function has %d stages but weights have %d\n", ev.stages.count(), ev.nstages());
    return 1;
  }
  printf("weights %s (%s, %d stages)  depth %d..%d budget %ld (close %g: %ld) prob_cut %g beam %d  games %ld threads %d\n",
         cfg.weights.c_str(), ev.patterns().c_str(), ev.nstages(), cfg.sp.min_depth, cfg.sp.max_depth,
         cfg.sp.budget, cfg.sp.close, cfg.sp.budget_hi, cfg.sp.prob_cut, cfg.sp.beam, cfg.games, cfg.threads);
  fflush(stdout);
  for (auto& l : cfg.lts) {
    auto& tabs = l.real ? ltabs_real : ltabs;
    (l.real ? ltr_rank_lo : lt_rank_lo).push_back(l.rank_lo);
    (l.real ? ltr_rank_hi : lt_rank_hi).push_back(l.rank_hi);
    tabs.emplace_back(new lt::Table(lt::snake_spec(l.k, l.r, l.caps), l.file));
    if (!tabs.back()->ok()) {
      fprintf(stderr, "cannot open layered table %s\n", l.file.c_str());
      return 1;
    }
    printf("layered table %s: k=%d r=%d, %.3g states, played when p >= %.2f (largest tile rank %d-%d%s)\n",
           l.file.c_str(), l.k, l.r, (double)tabs.back()->index().total(), cfg.lt_min, l.rank_lo,
           std::min(l.rank_hi, cfg.lt_max_rank), l.real ? ", real board" : "");
  }
  if (!cfg.block_dir.empty()) {
    int n = btabs.load(cfg.block_dir);
    printf("block tables: %d loaded from %s, played when p >= %.2f and no snake table decided\n", n,
           cfg.block_dir.c_str(), cfg.block_min);
    if (n == 0) return 1;
  }
  if (cfg.endgame > 0) {
    // goal ranks with tables: 6 locked -> up to 512 (10 free cells, ~1.5 GB), 7 or 8 locked -> 256
    int max_rank[17] = {0};
    for (int k = 6; k <= 16; k++) max_rank[k] = std::min(16 - k, k == 6 ? 9 : 8);
    endgame.reset(new eg::Snake(cfg.endgame, max_rank, cfg.endgame_full));
    if (!cfg.endgame_dir.empty())
      printf("endgame tables: %d loaded from %s\n", endgame->load(cfg.endgame_dir), cfg.endgame_dir.c_str());
    printf("endgame tables: snake endings with >= %d locked tiles%s, played when p >= %.2f\n", cfg.endgame,
           cfg.endgame_full == 1 ? " (complete collapses only)" : cfg.endgame_full == 2 ? " (complete collapses, or into the cell next to the corner)" : "", cfg.endgame_min);
  }
  if (!cfg.collect.empty()) {
    collect_fn = StageFn::parse(cfg.collect_when.empty() ? "14+" : cfg.collect_when);
    collect_file = fopen(cfg.collect.c_str(), "ab");
  }
  if (!cfg.analyze.empty()) {
    board_t b = 0;
    for (int i = 0; i < 16 && i < (int)cfg.analyze.size(); i++) {
      char c = cfg.analyze[i];
      int v = c <= '9' ? c - '0' : c - 'a' + 10;
      b |= (board_t)v << (4 * i);
    }
    for (int r = 0; r < 4; r++) {
      for (int c = 0; c < 4; c++) {
        int v = bb::cell(b, r * 4 + c);
        printf("%7d", v ? 1 << v : 0);
      }
      printf("\n");
    }
    printf("stage %d  sum %u\n", ev.stages.of(b), tile_sum(b));
    Searcher search(ev, cfg.tt_bits);
    for (int d = 1; d <= cfg.sp.max_depth; d++) {
      float v[4];
      search.move_values(b, d, v, cfg.sp);
      printf("depth %d:", d);
      for (int m = 0; m < 4; m++) printf("  %c %10.0f", DIRS[m], v[m]);
      printf("\n");
    }
    for (int m = 0; m < 4; m++) {
      uint32_t r;
      board_t a = bb::move(b, m, r);
      if (a != b) printf("%c: reward %u  V(afterstate) %.0f\n", DIRS[m], r, ev(a));
    }
    return 0;
  }
  vector<thread> th;
  for (int i = 0; i < cfg.threads; i++) th.emplace_back(worker, i);
  for (auto& t : th) t.join();
  if (collect_file) {
    fclose(collect_file);
    printf("collected %ld positions into %s\n", collected, cfg.collect.c_str());
  }
  if (dump_file) fclose(dump_file);
  summary();
  if (endgame && !cfg.endgame_dir.empty() && !cfg.endgame_nosave) {
    endgame->save(cfg.endgame_dir);
    printf("endgame tables saved to %s\n", cfg.endgame_dir.c_str());
  }
  return 0;
}
