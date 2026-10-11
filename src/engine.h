// The full player (n-tuple networks + expectimax + exact endgame tables) as a reusable component, configured by the
// same flags as build/play. One Engine (read-only after load) is shared by all threads; each thread owns an
// EngineThread (its own search with its own transposition table). Used by the analysis tool, the position generator
// and the playout tools, so that all of them play exactly the engine that the analysis talks about.
#pragma once
#include <cmath>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>
#include "board.h"
#include "game.h"
#include "ntuple.h"
#include "search.h"
#include "endgame.h"
#include "layered.h"
#include "block.h"

struct EngineConfig {
  std::string weights, stages;
  bool quantize = true;
  std::string packed;  // --packed FILE: networks from a packed file (wpack.h) instead of --weights (serving builds)
  SearchParams sp;
  std::vector<int> stage_depth;  // max search depth per stage of the root (view) board
  int root_down = 0, root_down_gap = 5;
  int tt_bits = 20;
  int endgame = 0;  // k >= 6 snake tables (memoised; built on demand)
  float endgame_min = 0.1f;
  int endgame_full = 0;
  std::string endgame_dir;
  struct Lt {
    std::string file;
    int k = 5, r = 10;
    std::vector<int> caps;
  };
  std::vector<Lt> lts;  // layered on-disk tables
  float lt_min = 0.5f;
  bool lt_view = false;
  int view_top = 0, view_gap = 10;
  uint32_t view_max_sum = 0;
  // late-game experiments (workstream late, 2026-10-06; off by default): --exposed-pen W LO HI as in build/play
  float exposed_pen = 0;
  uint32_t exp_lo = 0, exp_hi = 0;
  bool root_safe = false;  // --root-view-safe: root view with safe gaps (search.h downgrade_view_safe_all)
  bool view_safe = false;  // --leaf-view-safe: leaf views with safe gaps (as build/play)
  // exact block tables (workstream pdf, 2026-10-07; off by default): --block-tables DIR (src/block.h), played when the
  // position matches one and its success probability is >= --block-min and no snake table decided
  std::string block_dir;
  float block_min = 0.0f;
  bool block_lock = false;  // --block-lock: in the block formation, the best searched move that keeps it (if any)
  int block_from = 0;  // --block-from R: block tables only when the board's largest tile has rank >= R (0: always)

  static std::vector<int> ints(const std::string& v) {
    std::vector<int> out;
    for (size_t p = 0; p < v.size();) {
      size_t q = v.find(',', p);
      if (q == std::string::npos) q = v.size();
      out.push_back(std::stoi(v.substr(p, q - p)));
      p = q + 1;
    }
    return out;
  }
  // The best player (best_v5bb: 559,754 average, 59.8% 32768 over 1000 games), files under `root`.
  // tables = false leaves out the exact tables (no 88 GB of layered tables needed; weaker from the 16384 phase on).
  void preset_best(const std::string& root, bool tables = true) {
    weights = root + "/weights/best_v5.w";
    stages = "sum:20480/14,24576,28672,36864";
    quantize = true;
    sp.max_depth = 4;
    sp.min_depth = 4;
    sp.budget = 20000;
    sp.corner_lock = 14;
    stage_depth = {3, 4, 8, 8, 4};
    root_down = 15;
    view_top = 14, view_gap = 6, view_max_sum = 24576;
    if (tables) {
      endgame = 6, endgame_full = 2, endgame_min = 0.5f;
      endgame_dir = root + "/weights/endgame_big";
      lts.clear();
      lts.push_back(Lt{root + "/weights/endgame_lt/k5r10.lt", 5, 10, {9, 9, 8, 8, 8, 9, 9, 7, 7, 7, 7}});
      lts.push_back(Lt{root + "/weights/endgame_lt/k5r9.lt", 5, 9, {8, 8, 7, 7, 7, 8, 8, 7, 7, 7, 7}});
      lt_min = 0.5f;
      lt_view = true;
      // exact block tables (workstream pdf) when a complete set is on disk; for the block formation of strong players
      // (src/block.h), only from a 16384 on (smaller boards that happen to fit a block shape are snake positions)
      if (block_tables_ready(root + "/weights/pdf")) block_dir = root + "/weights/pdf", block_min = 0.5f, block_from = 14;
    }
    // the engine switch (scripts/switch_engine.sh install): weights/best.cfg holds network flags as build/play takes
    // them (e.g. "--weights weights/best_v6.w"), applied on top of this preset; without the file the preset is best_v5
    apply_flags_file(root + "/weights/best.cfg");
  }
  // Applies the engine flags in a text file (whitespace-separated, '#' starts a comment); false if it cannot be read.
  bool apply_flags_file(const std::string& path) {
    FILE* f = fopen(path.c_str(), "r");
    if (!f) return false;
    std::vector<std::string> tok{"cfg"};
    char buf[4096];
    while (fgets(buf, sizeof buf, f)) {
      std::string line(buf);
      size_t h = line.find('#');
      if (h != std::string::npos) line.resize(h);
      size_t p = 0;
      while ((p = line.find_first_not_of(" \t\r\n", p)) != std::string::npos) {
        size_t q = line.find_first_of(" \t\r\n", p);
        tok.push_back(line.substr(p, q == std::string::npos ? std::string::npos : q - p));
        p = q;
      }
    }
    fclose(f);
    std::vector<char*> argv;
    for (auto& t : tok) argv.push_back(&t[0]);
    for (int i = 1; i < (int)argv.size(); i++)
      if (!parse(i, (int)argv.size(), argv.data())) fprintf(stderr, "%s: unknown engine flag %s\n", path.c_str(), argv[i]);
    return true;
  }
  // A block-table directory is usable when it holds at least one table and every table in it is complete (its
  // ".done" marker exists: a table still being written must not be read).
  static bool block_tables_ready(const std::string& dir) {
    int n = 0;
    for (int e : {6, 4})
      for (int r = 3; r <= 10; r++) {
        std::string f = dir + "/" + blk::table_name(e, r);
        bool has = access(f.c_str(), R_OK) == 0;
        if (has && access((f + ".done").c_str(), F_OK) != 0) return false;
        n += has;
      }
    return n > 0;
  }
  // Consumes the engine flag at argv[i] (same names as build/play); false if it is not one.
  bool parse(int& i, int argc, char** argv) {
    std::string a = argv[i];
    auto next = [&]() -> std::string {
      if (i + 1 >= argc) {
        fprintf(stderr, "missing value for %s\n", a.c_str());
        exit(1);
      }
      return argv[++i];
    };
    if (a == "--weights") weights = next();
    else if (a == "--packed") packed = next();
    else if (a == "--stages") stages = next();
    else if (a == "--quantize") quantize = true;
    else if (a == "--float") quantize = false;
    else if (a == "--depth") sp.max_depth = std::stoi(next());
    else if (a == "--min-depth") sp.min_depth = std::stoi(next());
    else if (a == "--budget") sp.budget = std::stol(next());
    else if (a == "--prob-cut") sp.prob_cut = std::stof(next());
    else if (a == "--corner-lock") sp.corner_lock = std::stoi(next());
    else if (a == "--stage-depth") stage_depth = ints(next());
    else if (a == "--root-downgrade") root_down = std::stoi(next());
    else if (a == "--root-downgrade-gap") root_down_gap = std::stoi(next());
    else if (a == "--tt-bits") tt_bits = std::stoi(next());
    else if (a == "--endgame") endgame = std::stoi(next());
    else if (a == "--endgame-min") endgame_min = std::stof(next());
    else if (a == "--endgame-full") endgame_full = std::stoi(next());
    else if (a == "--endgame-dir") endgame_dir = next();
    else if (a == "--endgame-nosave") {}  // never saved here
    else if (a == "--endgame-lt") lts.push_back(Lt{next(), 5, 10, {}});
    else if (a == "--lt-k" && !lts.empty()) lts.back().k = std::stoi(next());
    else if (a == "--lt-rank" && !lts.empty()) lts.back().r = std::stoi(next());
    else if (a == "--lt-caps" && !lts.empty()) lts.back().caps = ints(next());
    else if (a == "--lt-min") lt_min = std::stof(next());
    else if (a == "--lt-view") lt_view = true;
    else if (a == "--no-tables") endgame = 0, lts.clear();
    else if (a == "--leaf-view") {
      view_top = std::stoi(next());
      view_gap = std::stoi(next());
    } else if (a == "--leaf-view-max-sum") view_max_sum = (uint32_t)std::stoul(next());
    else if (a == "--map-safe") g_map_safe_gap = true;  // boards given as tile values: safe gaps (game.h)
    else if (a == "--root-view-safe") root_safe = true;
    else if (a == "--leaf-view-safe") view_safe = true;
    else if (a == "--exposed-pen") {
      exposed_pen = std::stof(next());
      exp_lo = (uint32_t)std::stoul(next());
      exp_hi = (uint32_t)std::stoul(next());
    }
    else if (a == "--block-tables") block_dir = next();
    else if (a == "--block-min") block_min = std::stof(next());
    else if (a == "--block-lock") block_lock = true;
    else if (a == "--block-from") block_from = std::stoi(next());
    else return false;
    return true;
  }
};

class Engine {
 public:
  EngineConfig cfg;
  Evaluator ev;
  std::unique_ptr<eg::Snake> snake;
  std::vector<std::unique_ptr<lt::Table>> ltabs;
  blk::Tables btabs;  // --block-tables

  // Loads networks and tables; returns false (with a message on stderr) on failure.
  bool load(bool verbose = true) {
    try {
      if (!cfg.packed.empty()) {
        pnet_.load(cfg.packed);
        ev.pnet = &pnet_;
      } else if (cfg.quantize) {
        nt::load_quantized(cfg.weights, qnet_);
        ev.qnet = &qnet_;
      } else {
        net_.load(cfg.weights);
        ev.net = &net_;
      }
    } catch (std::exception& e) {
      fprintf(stderr, "cannot load %s: %s\n", (cfg.packed.empty() ? cfg.weights : cfg.packed).c_str(), e.what());
      return false;
    }
    if (!cfg.stages.empty()) ev.stages = StageFn::parse(cfg.stages);
    ev.downgrade = ev.stages.sums.empty();
    ev.view_top = cfg.view_top, ev.view_gap = cfg.view_gap, ev.view_max_sum = cfg.view_max_sum;
    ev.exposed_pen = cfg.exposed_pen, ev.exp_lo = cfg.exp_lo, ev.exp_hi = cfg.exp_hi;
    ev.view_safe = cfg.view_safe;
    if (ev.stages.count() != ev.nstages()) {
      fprintf(stderr, "stage function has %d stages but weights have %d\n", ev.stages.count(), ev.nstages());
      return false;
    }
    for (auto& l : cfg.lts) {
      ltabs.emplace_back(new lt::Table(lt::snake_spec(l.k, l.r, l.caps), l.file));
      if (!ltabs.back()->ok()) {
        fprintf(stderr, "cannot open layered table %s\n", l.file.c_str());
        return false;
      }
    }
    if (cfg.endgame > 0) {
      int max_rank[17] = {0};
      for (int k = 6; k <= 16; k++) max_rank[k] = std::min(16 - k, k == 6 ? 9 : 8);
      snake.reset(new eg::Snake(cfg.endgame, max_rank, cfg.endgame_full));
      int n = cfg.endgame_dir.empty() ? 0 : snake->load(cfg.endgame_dir);
      if (verbose) fprintf(stderr, "endgame tables: %d loaded from %s\n", n, cfg.endgame_dir.c_str());
    }
    if (!cfg.block_dir.empty()) {
      int n = btabs.load(cfg.block_dir);
      if (verbose) fprintf(stderr, "block tables: %d loaded from %s (played when p >= %.2f)\n", n, cfg.block_dir.c_str(),
                           cfg.block_min);
      if (n == 0) {
        fprintf(stderr, "no block tables in %s\n", cfg.block_dir.c_str());
        return false;
      }
    }
    if (verbose)
      fprintf(stderr, "engine: %s (%d stages), %zu layered tables, k>=6 tables %s\n", cfg.weights.c_str(),
              ev.nstages(), ltabs.size(), snake ? "on" : "off");
    return true;
  }
  // The board the engine searches: the root view (32768 phase seen as the 16384 phase).
  board_t view(board_t real) const {
    if (!cfg.root_down) return real;
    return cfg.root_safe ? downgrade_view_safe_all(real, cfg.root_down, cfg.root_down_gap)
                         : downgrade_view(real, cfg.root_down, cfg.root_down_gap);
  }
  SearchParams params(board_t view_b) const {
    SearchParams sp = cfg.sp;
    if (!cfg.stage_depth.empty()) {
      int stg = ev.stages.of(view_b);
      sp.max_depth = cfg.stage_depth[std::min(stg, (int)cfg.stage_depth.size() - 1)];
      if (sp.min_depth > sp.max_depth) sp.min_depth = sp.max_depth;
    }
    return sp;
  }

 private:
  nt::Net<float> net_;
  nt::Net<int16_t> qnet_;
  wpack::PackedNet pnet_;
};

// Sub-game success probability after each move of b (afterstate value over the random tile) under the layered table
// and frame that match b with the highest state value; -1 for illegal moves and moves outside the sub-game (they move
// the chain). Returns the matching state's probability (-1: no table applies).
static inline float lt_move_values(const std::vector<std::unique_ptr<lt::Table>>& tabs, board_t b, float out[4]) {
  for (int d = 0; d < 4; d++) out[d] = -1.0f;
  float best = -1.0f;
  for (int t = 0; t < (int)tabs.size(); t++)
    for (int j = 0; j < 8; j++) {
      const lt::Spec& sp = tabs[t]->index().spec();
      board_t sj = eg::sym(b, j), s;
      if (!lt::shape(sj, sp, &s)) continue;
      int m = 0;
      float p = tabs[t]->lookup(s, &m);
      if (p <= best) continue;
      best = p;
      for (int d = 0; d < 4; d++) {
        out[d] = -1.0f;
        board_t ad = bb::move(b, d);
        if (ad == b) continue;
        board_t adj = eg::sym(ad, j);
        if (((adj ^ sj) & sp.lock_mask) != 0) continue;  // the chain moved: outside the sub-game
        board_t a = (adj & ~sp.lock_mask) | sp.chain;
        bool won = false;
        for (uint16_t g = sp.goal; g; g &= g - 1)
          if (bb::cell(a, __builtin_ctz(g)) == sp.goal_rank) won = true;
        if (won) {
          out[d] = 1.0f;
          continue;
        }
        if (tabs[t]->index().sum(a) < 0) {
          out[d] = 0.0f;
          continue;
        }
        uint64_t em = bb::empty_mask(a);
        int n = __builtin_popcountll(em);
        float sum = 0.0f;
        for (uint64_t mm = em; mm; mm &= mm - 1) {
          uint64_t bit = mm & -mm;
          int mv;
          float v2 = tabs[t]->lookup(a | bit, &mv), v4 = tabs[t]->lookup(a | (bit << 1), &mv);
          sum += 0.9f * (v2 > 0 ? v2 : 0.0f) + 0.1f * (v4 > 0 ? v4 : 0.0f);
        }
        out[d] = n ? sum / n : 0.0f;
      }
    }
  return best;
}

inline constexpr const char* kDirName[4] = {"up", "right", "down", "left"};
inline constexpr char kDirChar[4] = {'U', 'R', 'D', 'L'};

struct MoveEval {
  bool legal = false;
  uint32_t reward = 0;
  board_t after = 0;  // real-board afterstate
  float value = NAN;  // reward + expected future reward after the move (expectimax at the analysis depth)
  float table_p = -1; // endgame sub-game success probability after the move (-1: no table applies)
  bool lock_skip = false;  // the engine's corner lock rules this move out
};

struct Analysis {
  board_t board = 0, view = 0;
  int stage = 0, depth = 0;
  MoveEval mv[4];
  int engine_move = -1;   // the move the engine plays
  const char* source = "";  // what decided it: "search", "table" (k>=6) or "layered" (k=5)
  float table_state_p = -1; // the deciding table's success probability for the position
  long evals = 0;
};

class EngineThread {
 public:
  explicit EngineThread(const Engine& e) : E(e), search(new Searcher(e.ev, e.cfg.tt_bits)) {}
  const Engine& E;
  std::unique_ptr<Searcher> search;
  SearchStats st;
  // Starts the next search from an empty transposition table. A server answering unrelated requests should call it
  // per request: entries left by earlier requests make iterative deepening under-predict the next iteration's cost
  // (table hits are free) and search deeper and deeper (the same board asked again: depth 4, 5, 6, 7; 11 ms -> 17 s)
  // and the answer would depend on earlier requests. (~1 ms per call.)
  void reset_search() { search.reset(new Searcher(E.ev, E.cfg.tt_bits)); }

  // The engine's move for real board b (-1: no legal move). *source, if given, says what decided it.
  int choose(board_t real_b, const char** source = nullptr, float* table_p = nullptr) {
    board_t b = E.view(real_b);
    SearchParams sp = E.params(b);
    int d = -1;
    float pt = -1.0f;
    const char* src = "search";
    if (E.snake) {
      d = E.snake->suggest(b, &pt);
      if (d >= 0 && pt < E.cfg.endgame_min) d = -1;
      if (d >= 0) src = "table";
    }
    if (!E.ltabs.empty()) {
      float pl;
      int dl = lt::suggest(E.ltabs, E.cfg.lt_view ? b : real_b, &pl);
      if (dl >= 0 && pl >= E.cfg.lt_min && (d < 0 || pl > pt)) d = dl, pt = pl, src = "layered";
    }
    if (d < 0 && !E.btabs.empty() && bb::max_rank(real_b) >= E.cfg.block_from) {  // block tables: on the real board
      float pb;
      int db = blk::suggest(E.btabs, real_b, &pb);
      if (db >= 0 && pb >= E.cfg.block_min) d = db, pt = pb, src = "block";
    }
    if (d < 0) {
      d = search->best_move(b, sp, &st);
      pt = -1.0f;
      src = "search";
      if (E.cfg.block_lock && d >= 0 && search->last_n > 1) {
        float vals[4];
        for (int i = 0; i < search->last_n; i++) vals[i] = search->last_reward[i] + search->last_value[i];
        int bd = blk::lock_choice(real_b, search->last_n, search->last_dir, vals);
        if (bd >= 0) d = bd;
      }
    }
    if (source) *source = src;
    if (table_p) *table_p = pt;
    return d;
  }

  // Values of every legal move of real board b. depth 0: the depth the engine's own iterative deepening reaches
  // (at least min_depth); otherwise that fixed depth.
  Analysis analyze(board_t real_b, int depth = 0) {
    Analysis A;
    A.board = real_b;
    A.view = E.view(real_b);
    A.stage = E.ev.stages.of(A.view);
    long ev0 = st.evals;
    A.engine_move = choose(real_b, &A.source, &A.table_state_p);
    SearchParams sp = E.params(A.view);
    if (depth <= 0) {
      if (A.engine_move >= 0 && std::string(A.source) != "search") search->best_move(A.view, sp, &st);
      depth = std::max(st.depth, 1);
    }
    A.depth = depth;
    float v[4];
    search->move_values(A.view, depth, v, sp);
    int lr = lock_rank(A.view, sp.corner_lock);
    for (int d = 0; d < 4; d++) {
      MoveEval& m = A.mv[d];
      m.after = bb::move(real_b, d, m.reward);
      m.legal = m.after != real_b;
      if (!m.legal) continue;
      m.value = v[d];
      board_t av = bb::move(A.view, d);
      m.lock_skip = lr && corner_max(av) < lr;
    }
    if (lr) {  // the lock only binds if some legal move keeps the corner
      bool any = false;
      for (int d = 0; d < 4; d++) any |= A.mv[d].legal && !A.mv[d].lock_skip;
      if (!any)
        for (int d = 0; d < 4; d++) A.mv[d].lock_skip = false;
    }
    // table probabilities per move
    if (!E.ltabs.empty()) {
      float tv[4];
      if (lt_move_values(E.ltabs, E.cfg.lt_view ? A.view : real_b, tv) >= 0)
        for (int d = 0; d < 4; d++) A.mv[d].table_p = tv[d];
    }
    if (E.snake) {
      bool any = false;
      for (int d = 0; d < 4; d++) any |= A.mv[d].table_p >= 0;
      if (!any)
        for (int d = 0; d < 4; d++)
          if (A.mv[d].legal) A.mv[d].table_p = const_cast<eg::Snake&>(*E.snake).after_value(bb::move(A.view, d));
    }
    if (!E.btabs.empty() && bb::max_rank(real_b) >= E.cfg.block_from) {
      bool any = false;
      for (int d = 0; d < 4; d++) any |= A.mv[d].table_p >= 0;
      float bv[4];
      if (!any && blk::move_values(E.btabs, real_b, bv) >= 0)
        for (int d = 0; d < 4; d++) A.mv[d].table_p = bv[d];
    }
    A.evals = st.evals - ev0;
    return A;
  }

  // What the random tile can do after a move: for every spawn (cell, 2 or 4) of real afterstate `after`, its
  // probability and the value of the resulting position (best move by expectimax at `depth`; 0 if it is lost).
  struct Spawn {
    int cell, rank;
    float prob, value;
  };
  std::vector<Spawn> spawns(board_t after, int depth = 2) {
    std::vector<Spawn> out;
    uint64_t em = bb::empty_mask(after);
    int n = __builtin_popcountll(em);
    for (uint64_t m = em; m; m &= m - 1) {
      int c = __builtin_ctzll(m) / 4;
      for (int r = 1; r <= 2; r++) {
        board_t s = after | ((board_t)r << (4 * c));
        board_t v = E.view(s);
        float mv[4], best = 0;
        bool any = false;
        search->move_values(v, depth, mv, E.params(v));
        for (int d = 0; d < 4; d++)
          if (!std::isnan(mv[d]) && (!any || mv[d] > best)) best = mv[d], any = true;
        out.push_back(Spawn{c, r, (r == 1 ? 0.9f : 0.1f) / n, any ? best : 0.0f});
      }
    }
    return out;
  }
};

// The human-like softmax player (build/messy's soft:t): move m with probability ~ exp(-relative 1-ply loss(m) / t).
// Returns the move (-1: no legal move).
static inline int soft_move(const Engine& E, board_t b, double t, bb::Rng& rng) {
  int legal[4], n = 0;
  float q[4];
  for (int d = 0; d < 4; d++) {
    uint32_t r;
    board_t a = bb::move(b, d, r);
    if (a == b) continue;
    legal[n] = d;
    q[n] = r + E.ev(E.view(a));
    n++;
  }
  if (n == 0) return -1;
  float best = q[0];
  for (int i = 1; i < n; i++) best = std::max(best, q[i]);
  double w[4], tot = 0;
  for (int i = 0; i < n; i++) tot += w[i] = std::exp(-(best - q[i]) / (std::max(1.0f, std::fabs(best)) * t));
  double u = rng.uniform() * tot;
  for (int i = 0; i < n; i++) {
    if (u < w[i]) return legal[i];
    u -= w[i];
  }
  return legal[n - 1];
}

// ---- board input/output ----
// Real rank of each search rank for the board parsed last (identity unless it held tiles above 32768, which the
// search board stores lowered): every tile value shown to the user goes through it.
inline int g_display_rank[16] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
static inline long display_tile(int r) { return r ? 1L << g_display_rank[r] : 0; }
// Accepts 16 hex rank digits (cell 0 = top-left first, as build/play --analyze), or 16 tile values separated by any
// non-digit characters ("2 4 0 0 / 8 ..."), 0 = empty. Tiles above 32768 are mapped down like the real game's
// search board. Returns false if the text is not a board.
static inline bool parse_board(const std::string& text, board_t* out) {
  // hex only as a single 16-character token ("0 0 0 2 ..." with the spaces removed would look like hex too)
  size_t b0 = text.find_first_not_of(" \t\r\n"), b1 = text.find_last_not_of(" \t\r\n");
  std::string t = b0 == std::string::npos ? "" : text.substr(b0, b1 - b0 + 1);
  if (t.size() == 16 && t.find_first_not_of("0123456789abcdefABCDEF") == std::string::npos) {
    board_t b = 0;
    for (int i = 0; i < 16; i++) {
      char c = (char)tolower(t[i]);
      int v = c <= '9' ? c - '0' : c - 'a' + 10;
      b |= (board_t)v << (4 * i);
    }
    *out = b;
    for (int r = 0; r < 16; r++) g_display_rank[r] = r;
    return true;
  }
  std::vector<long> vals;
  long cur = -1;
  const long kHuge = 1L << 40;  // longer numbers saturate (no overflow) and are rejected below
  for (char c : text) {
    if (isdigit((unsigned char)c)) cur = cur < 0 ? c - '0' : cur > kHuge ? kHuge + 1 : cur * 10 + (c - '0');
    else if (cur >= 0) vals.push_back(cur), cur = -1;
  }
  if (cur >= 0) vals.push_back(cur);
  if (vals.size() != 16) return false;
  Game g;
  for (int i = 0; i < 16; i++) {
    long v = vals[i];
    if (v == 0) {
      g.r[i] = 0;
      continue;
    }
    // tiles above 2^30 cannot occur (a 4x4 game ends near 2^17) and would overflow map_search_board's rank arrays
    if (v < 2 || (v & (v - 1)) || v > (1L << 30)) return false;
    g.r[i] = (uint8_t)__builtin_ctzl((unsigned long)v);
  }
  int back[16];
  if (!map_search_board(g, out, back)) return false;
  for (int r = 0; r < 16; r++) g_display_rank[r] = back[r];
  return true;
}
static inline std::string board_hex(board_t b) {
  std::string s;
  for (int i = 0; i < 16; i++) s += "0123456789abcdef"[bb::cell(b, i)];
  return s;
}
static inline std::string board_tiles(board_t b) {  // "[[2,4,0,0],[...],...]"
  std::string s = "[";
  for (int r = 0; r < 4; r++) {
    s += r ? ",[" : "[";
    for (int c = 0; c < 4; c++) {
      int v = bb::cell(b, r * 4 + c);
      s += (c ? "," : "") + std::to_string(display_tile(v));
    }
    s += "]";
  }
  return s + "]";
}
static inline void print_board(FILE* f, board_t b) {
  for (int r = 0; r < 4; r++) {
    for (int c = 0; c < 4; c++) {
      int v = bb::cell(b, r * 4 + c);
      if (v) fprintf(f, "%7ld", display_tile(v));
      else fprintf(f, "%7s", ".");
    }
    fprintf(f, "\n");
  }
}
