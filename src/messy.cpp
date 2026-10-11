// Messy-position generator: plays games with imperfect policies and samples positions from them, as test and training
// sets for analysis of human-like positions (the engine's own games only cover tidy formations).
//
//   build/messy --preset best [engine flags] --policy SPEC --games N --per-game K --out PREFIX
//               [--threads T] [--seed S] [--min-sum A] [--max-sum B] [--max-moves M]
//
// SPEC is a sequence of phases "P1@SUM1,P2@SUM2,...,Pn": policy P1 plays until the tile sum reaches SUM1, then P2, ...
// Each policy is NAME[:eps=E][:second=Q]: with probability E a uniformly random legal move, else with probability Q
// the policy's second choice (a plausible mistake), else its first choice. Names:
//   random   uniformly random legal moves
//   greedy   largest immediate merge reward (ties at random) - the "merge whatever you can" beginner
//   corner   beginner corner strategy: two home directions (most merges first), the third if neither is legal,
//            the fourth only when forced; the home corner is drawn per game
//   heur     1-ply on a hand-made heuristic (empty cells, merges, monotonicity)
//   net      1-ply on the engine's network
//   engine   the full engine (search + tables)
//   soft     human-like mistakes: move m with probability ~ exp(-relative loss(m) / t) (option :t=, default 0.01),
//            losses by the network at 1 ply; soft2: losses by expectimax at depth 2
//   human    the human move model of src/human.h (fitted to the curated human data; option :th= skill theta,
//            default 0; tier medians: novice -0.86, intermediate -0.24, strong -0.25, expert -0.46); weights from
//            --human-model FILE (scripts/hm_export.py output), else the built-in ones; :net=S plays the 1-ply argmax
//            with probability S instead (a more structured player)
// "@LO-HI" draws the switch sum per game from [LO, HI); "@+N" switches N above the sum where the phase started (e.g.
// "engine@16000-30000,soft:t=0.01@+300,engine": a clean engine game with a lapse of human-like play in the 16384
// phase). --record-switch also records the first position of every later
// phase (e.g. "net:eps=0.1@500-12000,engine" records where the engine takes over a messy game: the game's outcome is
// then the engine's outcome from that position). --values adds the engine's analysis of every recorded position.
// Output: PREFIX.bin (8-byte boards, the pool format of train/play --start) and PREFIX.tsv (one line per position:
// index, game, move number, tile sum, max tile, score so far, the policy phase, switch flag, the game's final max
// tile, score and length, the board, and with --values the best move's value, the engine move's value, the analysis
// depth, the engine's move, what decided it and the deciding table's probability).
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "engine.h"
#include "human.h"

using namespace std;

struct Policy {
  string name;
  double eps = 0, second = 0, temp = 0.01;
  double theta = 0;  // human: skill
  double net_mix = 0;  // human: probability of playing the 1-ply argmax instead (option :net=)
  double theta_s = NAN;  // human: structure skill (option :ths=; default: theta)
  // human: care in danger (workstream hm3) - on a board with at most :de= empty cells (default 2), with probability
  // :dq= the engine's move is played instead (:dm=0: the 1-ply argmax, 1 (default): the engine's search, 2: the best
  // move by depth-2 search among those that keep the largest tile in its corner, when it is in one - human structure)
  double danger_q = 0;
  int danger_e = 2, danger_m = 1;
  long until_sum = -1;  // -1: to the end
  long until_hi = -1;   // "@LO-HI": the switch sum is drawn uniformly from [LO, HI) per game
  bool relative = false;  // "@+N": switch N above the tile sum at which this phase started (a lapse of ~N/2.2 moves)
};

static vector<Policy> parse_spec(const string& spec) {
  vector<Policy> out;
  size_t p = 0;
  while (p < spec.size()) {
    size_t q = spec.find(',', p);
    if (q == string::npos) q = spec.size();
    string part = spec.substr(p, q - p);
    Policy pol;
    size_t at = part.find('@');
    if (at != string::npos) {
      string t = part.substr(at + 1);
      if (!t.empty() && t[0] == '+') pol.relative = true, t = t.substr(1);
      size_t dash = t.find('-');
      pol.until_sum = stol(t.substr(0, dash));
      if (dash != string::npos) pol.until_hi = stol(t.substr(dash + 1));
      part = part.substr(0, at);
    }
    size_t c = part.find(':');
    pol.name = part.substr(0, c);
    while (c != string::npos) {
      size_t c2 = part.find(':', c + 1);
      string kv = part.substr(c + 1, c2 == string::npos ? string::npos : c2 - c - 1);
      size_t eq = kv.find('=');
      string k = kv.substr(0, eq);
      double v = stod(kv.substr(eq + 1));
      if (k == "eps") pol.eps = v;
      else if (k == "second") pol.second = v;
      else if (k == "t") pol.temp = v;
      else if (k == "th") pol.theta = v;
      else if (k == "net") pol.net_mix = v;
      else if (k == "ths") pol.theta_s = v;
      else if (k == "dq") pol.danger_q = v;
      else if (k == "de") pol.danger_e = (int)v;
      else if (k == "dm") pol.danger_m = (int)v;
      else {
        fprintf(stderr, "unknown policy option %s\n", k.c_str());
        exit(1);
      }
      c = c2;
    }
    static const char* known[] = {"random", "greedy", "corner", "heur", "net", "engine", "soft", "soft2", "human"};
    bool ok = false;
    for (auto k : known) ok |= pol.name == k;
    if (!ok) {
      fprintf(stderr, "unknown policy %s\n", pol.name.c_str());
      exit(1);
    }
    out.push_back(pol);
    p = q + 1;
  }
  return out;
}

static Engine E;
static hm::Model HM;  // the human policy's weights
static bool need_engine = false;
static vector<Policy> phases;
static long games = 100, per_game = 10, min_sum = 0, max_sum = 1L << 30, max_moves = 0;
static bool record_switch = false, values = false;
// --checkpoints S1,S2,...: also record each game's first position with tile sum >= S_i (kind 2). Unlike the random
// per-game samples (kind 0: uniform over a game's moves, which over-represents short, failing games among early
// positions), checkpoints count every game once per stage it reaches: unbiased for P(outcome | alive at sum S).
static vector<long> checkpoints;
static uint64_t seed = 1;
static atomic<long> next_game{0}, written{0};
static mutex mu;
static FILE *fbin, *ftsv, *ftrace = nullptr;  // --trace: every game's boards (hex, one per line, blank line between games)

// Moves ranked best first by the policy (at most 4); n = number of legal moves.
static int rank_moves(const Policy& pol, board_t b, EngineThread* et, bb::Rng& rng, int home, int order[4],
                      const hm::History* hist = nullptr) {
  int legal[4], n = 0;
  uint32_t rw[4];
  board_t as[4];
  for (int d = 0; d < 4; d++) {
    uint32_t r;
    board_t a = bb::move(b, d, r);
    if (a != b) legal[n] = d, rw[n] = r, as[n] = a, n++;
  }
  if (n == 0) return 0;
  double key[4];
  if (pol.name == "random") {
    for (int i = 0; i < n; i++) key[i] = rng.uniform();
  } else if (pol.name == "greedy") {
    for (int i = 0; i < n; i++) key[i] = rw[i] + rng.uniform() * 0.5;
  } else if (pol.name == "corner") {
    // home directions: (home & 1 ? DOWN : UP) and (home & 2 ? LEFT : RIGHT); then the other horizontal/vertical
    int v = home & 1 ? DOWN : UP, h = home & 2 ? LEFT : RIGHT;
    int third = home & 4 ? (h ^ 2) : (v ^ 2), fourth = home & 4 ? (v ^ 2) : (h ^ 2);
    for (int i = 0; i < n; i++) {
      int d = legal[i];
      double base = d == v || d == h ? 2000 : d == third ? 1000 : d == fourth ? 0 : 0;
      key[i] = base + rw[i] * 1e-3 + rng.uniform() * 1e-4;
    }
  } else if (pol.name == "heur") {
    for (int i = 0; i < n; i++) key[i] = rw[i] + bb::heuristic(as[i]) + rng.uniform() * 1e-3;
  } else if (pol.name == "net") {
    for (int i = 0; i < n; i++) {
      board_t av = E.view(as[i]);
      key[i] = rw[i] + E.ev(av) + rng.uniform() * 1e-3;
    }
  } else if (pol.name == "soft" || pol.name == "soft2") {
    // human-like mistakes: move m is chosen with probability ~ exp(-relative loss / t), the loss measured by the
    // network at 1 ply (soft) or by expectimax at depth 2 (soft2) - slightly worse moves often, bad ones rarely
    board_t v = E.view(b);
    float q[4];
    if (pol.name == "soft2") {
      float mv[4];
      et->search->move_values(v, 2, mv, E.params(v));
      for (int i = 0; i < n; i++) q[i] = mv[legal[i]];
    } else {
      for (int i = 0; i < n; i++) q[i] = rw[i] + E.ev(E.view(as[i]));
    }
    float best = q[0];
    for (int i = 1; i < n; i++) best = max(best, q[i]);
    double w[4], tot = 0;
    for (int i = 0; i < n; i++) tot += w[i] = exp(-(best - q[i]) / (max(1.0f, fabsf(best)) * pol.temp));
    double u = rng.uniform() * tot;
    int pick = n - 1;
    for (int i = 0; i < n; i++) {
      if (u < w[i]) {
        pick = i;
        break;
      }
      u -= w[i];
    }
    for (int i = 0; i < n; i++) key[i] = q[i] + (i == pick ? 1e30 : 0);
  } else if (pol.name == "human") {
    double p[4];
    hm::probs(E, HM, b, hist ? *hist : hm::History(), pol.theta, p, pol.theta_s);
    double u = rng.uniform(), acc = 0;
    int pick = n - 1;
    for (int i = 0; i < n; i++) {
      acc += p[legal[i]];
      if (u < acc) {
        pick = i;
        break;
      }
    }
    if (pol.net_mix > 0 && rng.uniform() < pol.net_mix) {  // the 1-ply argmax (structured play)
      double bq = -1e300;
      for (int i = 0; i < n; i++) {
        double qi = rw[i] + E.ev(E.view(as[i]));
        if (qi > bq) bq = qi, pick = i;
      }
    }
    if (pol.danger_q > 0 && bb::count_empty(b) <= pol.danger_e && rng.uniform() < pol.danger_q) {  // care in danger
      if (pol.danger_m == 0 || !et) {
        double bq = -1e300;
        for (int i = 0; i < n; i++) {
          double qi = rw[i] + E.ev(E.view(as[i]));
          if (qi > bq) bq = qi, pick = i;
        }
      } else if (pol.danger_m == 2) {
        // keep the corner: among the moves after which the largest tile still sits in a corner (if it does now)
        auto in_corner = [](board_t x) {
          int m = bb::max_rank(x);
          return bb::cell(x, 0) == m || bb::cell(x, 3) == m || bb::cell(x, 12) == m || bb::cell(x, 15) == m;
        };
        bool keep = in_corner(b);
        float mv[4];
        board_t vb = E.view(b);
        et->search->move_values(vb, 2, mv, E.params(vb));
        double bq = -1e300;
        int bk = -1;
        for (int pass = 0; pass < 2 && bk < 0; pass++)
          for (int i = 0; i < n; i++) {
            if (pass == 0 && keep && !in_corner(as[i])) continue;
            double qi = std::isnan(mv[legal[i]]) ? -1e299 : mv[legal[i]];
            if (qi > bq) bq = qi, bk = i;
          }
        if (bk >= 0) pick = bk;
      } else {
        int d = et->choose(b);
        for (int i = 0; i < n; i++)
          if (legal[i] == d) pick = i;
      }
    }
    for (int i = 0; i < n; i++) key[i] = p[legal[i]] + (i == pick ? 1e30 : 0);
  } else {  // engine: its move first, then the rest by search value
    int d = et->choose(b);
    float v[4];
    et->search->move_values(E.view(b), 2, v, E.params(E.view(b)));
    for (int i = 0; i < n; i++) key[i] = legal[i] == d ? 1e30 : (std::isnan(v[legal[i]]) ? -1e30 : v[legal[i]]);
  }
  int idx[4] = {0, 1, 2, 3};
  sort(idx, idx + n, [&](int x, int y) { return key[x] > key[y]; });
  for (int i = 0; i < n; i++) order[i] = legal[idx[i]];
  return n;
}

static void worker() {
  unique_ptr<EngineThread> et;
  if (need_engine) et.reset(new EngineThread(E));
  for (;;) {
    long id = next_game.fetch_add(1);
    if (id >= games) break;
    bb::Rng rng(seed * 1000003 + 0x9E3779B97F4A7C15ULL * (id + 1));
    if (et) et->reset_search();  // every game starts from an empty search cache (a game does not depend on the last)
    int home = (int)rng.below(8);
    board_t b = bb::initial_board(rng);
    uint64_t score = 0;
    long moves = 0;
    size_t ph = 0;
    struct Pos {
      board_t b;
      long move;
      uint64_t score;
      int phase;
    };
    vector<Pos> traj, switches, cps;
    size_t next_cp = 0;
    hm::History hist;  // the game's recent moves (the human policy's habits)
    vector<board_t> trace;
    vector<long> until(phases.size());
    for (size_t i = 0; i < phases.size(); i++) {
      until[i] = phases[i].until_sum;
      if (phases[i].until_hi > phases[i].until_sum)
        until[i] += (long)rng.below((uint32_t)(phases[i].until_hi - phases[i].until_sum));
    }
    for (;;) {
      size_t ph0 = ph;
      while (ph + 1 < phases.size() && until[ph] >= 0 && (long)tile_sum(b) >= until[ph]) {
        ph++;
        if (phases[ph].relative) until[ph] += (long)tile_sum(b);  // relative to where the phase starts
      }
      if (ph != ph0 && record_switch && bb::can_move(b)) switches.push_back(Pos{b, moves, score, (int)ph});
      while (next_cp < checkpoints.size() && (long)tile_sum(b) >= checkpoints[next_cp]) {
        if (bb::can_move(b)) cps.push_back(Pos{b, moves, score, (int)ph});
        next_cp++;
      }
      long ts = (long)tile_sum(b);
      int order[4];
      const Policy& pol = phases[ph];
      int n = rank_moves(pol, b, et.get(), rng, home, order, &hist);
      if (n == 0) break;
      if (ts >= min_sum && ts < max_sum) traj.push_back(Pos{b, moves, score, (int)ph});
      if (ftrace) trace.push_back(b);
      int d = order[0];
      double u = rng.uniform();
      if (u < pol.eps) d = order[rng.below(n)];
      else if (u < pol.eps + pol.second && n > 1) d = order[1];
      uint32_t r;
      b = bb::move(b, d, r);
      hist.push(d);
      score += r;
      moves++;
      b = bb::spawn(b, rng);
      if (max_moves && moves >= max_moves) break;
    }
    // K positions of this game, uniformly without replacement
    vector<size_t> pick(traj.size());
    for (size_t i = 0; i < pick.size(); i++) pick[i] = i;
    size_t k = min((size_t)per_game, traj.size());
    for (size_t i = 0; i < k; i++) swap(pick[i], pick[i + rng.below((uint32_t)(pick.size() - i))]);
    sort(pick.begin(), pick.begin() + k);
    vector<pair<Pos, int>> rec;  // (position, kind: 0 random sample, 1 phase switch, 2 checkpoint)
    for (auto& p : switches) rec.push_back({p, 1});
    for (auto& p : cps) rec.push_back({p, 2});
    for (size_t i = 0; i < k; i++) rec.push_back({traj[pick[i]], 0});
    vector<string> extra(rec.size());
    if (values)
      for (size_t i = 0; i < rec.size(); i++) {
        et->reset_search();  // values as build/analyze computes them (a fresh search per position)
        Analysis A = et->analyze(rec[i].first.b);
        float best = NAN;
        for (int d = 0; d < 4; d++)
          if (A.mv[d].legal && (std::isnan(best) || A.mv[d].value > best)) best = A.mv[d].value;
        char buf[256];
        snprintf(buf, sizeof buf, "\t%.1f\t%.1f\t%d\t%c\t%s\t%.4f", best,
                 A.engine_move >= 0 ? A.mv[A.engine_move].value : NAN, A.depth,
                 A.engine_move >= 0 ? kDirChar[A.engine_move] : '-', A.source, A.table_state_p);
        extra[i] = buf;
      }
    lock_guard<mutex> lk(mu);
    if (ftrace) {
      trace.push_back(b);  // the final (dead or cut-off) board
      for (board_t x : trace) fprintf(ftrace, "%s\n", board_hex(x).c_str());
      fprintf(ftrace, "\n");
    }
    for (size_t i = 0; i < rec.size(); i++) {
      const Pos& p = rec[i].first;
      fwrite(&p.b, sizeof p.b, 1, fbin);
      long idx = written++;
      const Policy& pp = phases[p.phase];
      int engine_future = p.phase + 1 == (int)phases.size() && pp.name == "engine" && pp.eps == 0 && pp.second == 0;
      fprintf(ftsv, "%ld\t%ld\t%ld\t%u\t%d\t%llu\t%d\t%d\t%d\t%d\t%llu\t%ld\t%s%s\n", idx, id, p.move,
              tile_sum(p.b), 1 << bb::max_rank(p.b), (unsigned long long)p.score, p.phase, rec[i].second,
              engine_future, 1 << bb::max_rank(b), (unsigned long long)score, moves, board_hex(p.b).c_str(),
              extra[i].c_str());
    }
    if (id % 50 == 0 || id + 1 == games) {
      fprintf(stderr, "game %ld: max %d score %llu moves %ld, %ld positions so far\n", id, 1 << bb::max_rank(b),
              (unsigned long long)score, moves, (long)written);
    }
  }
}

int main(int argc, char** argv) {
  string spec = "net", out, preset;
  int threads = 16;
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
      preset = next();
      E.cfg.preset_best(".", preset == "best");
    } else if (E.cfg.parse(i, argc, argv)) {
    } else if (a == "--policy") spec = next();
    else if (a == "--human-model") {
      string f = next();
      if (!HM.load(f)) {
        fprintf(stderr, "cannot read %s\n", f.c_str());
        return 1;
      }
    }
    else if (a == "--games") games = stol(next());
    else if (a == "--per-game") per_game = stol(next());
    else if (a == "--out") out = next();
    else if (a == "--threads") threads = stoi(next());
    else if (a == "--seed") seed = stoull(next());
    else if (a == "--min-sum") min_sum = stol(next());
    else if (a == "--max-sum") max_sum = stol(next());
    else if (a == "--max-moves") max_moves = stol(next());
    else if (a == "--record-switch") record_switch = true;
    else if (a == "--checkpoints") {
      string v = next();
      for (size_t p = 0; p < v.size();) {
        size_t q = v.find(',', p);
        if (q == string::npos) q = v.size();
        checkpoints.push_back(stol(v.substr(p, q - p)));
        p = q + 1;
      }
      sort(checkpoints.begin(), checkpoints.end());
    }
    else if (a == "--values") values = true;
    else if (a == "--trace") {
      ftrace = fopen(next().c_str(), "w");
      if (!ftrace) {
        fprintf(stderr, "cannot write the trace file\n");
        return 1;
      }
    }
    else {
      fprintf(stderr, "unknown option %s\n", a.c_str());
      return 1;
    }
  }
  if (out.empty()) {
    fprintf(stderr, "--out PREFIX required\n");
    return 1;
  }
  phases = parse_spec(spec);
  for (auto& p : phases) need_engine |= p.name == "engine" || p.name == "net" || p.name == "soft" || p.name == "soft2" || p.name == "human";
  need_engine |= values;
  if (need_engine && !E.load()) return 1;
  fbin = fopen((out + ".bin").c_str(), "wb");
  ftsv = fopen((out + ".tsv").c_str(), "w");
  if (!fbin || !ftsv) {
    fprintf(stderr, "cannot write %s.*\n", out.c_str());
    return 1;
  }
  fprintf(ftsv, "idx\tgame\tmove\tsum\tmax\tscore\tphase\tswitch\tengine_future\tfinal_max\tfinal_score\tfinal_moves"
                "\tboard%s\n",
          values ? "\tvalue\tengine_value\tdepth\tengine_move\tsource\ttable_p" : "");
  vector<thread> th;
  for (int t = 0; t < threads; t++) th.emplace_back(worker);
  for (auto& t : th) t.join();
  fclose(fbin);
  fclose(ftsv);
  if (ftrace) fclose(ftrace);
  fprintf(stderr, "%ld positions written to %s.bin/.tsv\n", (long)written, out.c_str());
  return 0;
}
