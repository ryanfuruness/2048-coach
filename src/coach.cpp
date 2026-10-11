// Coach test: does the engine's advice help a human-like player recover from bad positions, and how much advice is
// enough? Players are the softmax players of build/messy (soft_move: move m with probability ~ exp(-relative 1-ply
// loss / t)); advice is the engine's move, with value losses from the engine's analysis at its own depth (the scale of
// build/analyze: (best - value) / max(|best|, 100000)).
//
//   build/coach --preset best-notables [engine flags] --in POS.tsv --mode advice|first|fit [--t T1,T2,...]
//               [--conds alone,engine,guard:X[:cC],crit:Y[:cC],stakes:Y[:cC]] [--playouts N] [--second]
//               [--max-moves M] [--threads K] [--seed S] --out FILE.tsv
//
// POS.tsv: a header line, then "id <TAB> hex [<TAB> played]" (hex: 16 rank digits, engine encoding; played: U/R/D/L).
// Milestones: target 1 = one rank above the start's largest tile, target 2 = two ranks above (with --second).
// Common random numbers: playout k of a position uses the same spawn stream and the same player stream under every
// condition and player (the player draws its own move every turn, also when advice overrides it; compliance draws
// come from a third stream).
//
// mode advice: one row per (position, player t, condition, playout):
//     id t cond k reached1 reached2 moves shown changed died
//   alone      the player's own moves
//   engine     the engine's moves (t ignored: run once, written as t=0)
//   guard:X    the player's move, unless the engine rates it >= X worse: then the engine's move (an app that warns
//              before the move is committed, or offers an undo); shown = changed = such moves
//   crit:Y     before the player moves, the engine shows its move when the player's expected loss (its softmax
//              probabilities over 1-ply values, losses by the engine's analysis) is >= Y; the player follows it
//   stakes:Y   the engine shows its move when the second-best move loses >= Y (skill-agnostic "only one good move")
//   risk:R     before the player moves, the engine shows its move when the position's error risk at the player's
//              level reaches R: sum over the moves of the human move model's probability (the fitted move model at
//              the player's theta: the personal model's theta map of the key, as analyze computes it for a reviewed
//              player; without a map the playout family's own probabilities) x the move's cost to the player's own
//              chances (Calib::own_cost of its value loss, weights/calib/model.txt) - analyze's "hint" (workstream hm2)
//   ...:cC     the player follows shown advice with probability C (default 1)
//   ...:kN     at most N hints per playout (the first N qualifying moments)
// --structured S: a more structured human model: the player plays the engine's move with probability S and its
//   softmax move otherwise (both drawn every turn, from separate streams)
//   shown = advice displayed, changed = moves where it changed the player's own choice
// mode first: one row per (position, continuation, playout): the outcome after each legal first move under the same
//     random streams: id cont k r1_U r1_R r1_D r1_L r2_U r2_R r2_D r2_L moves_U ... (-1 = illegal);
//     cont = the player's t, or 0 for the engine (--no-engine: players only)
// mode fit: one row per position: id played l_U l_R l_D l_L, the relative 1-ply losses on soft_move's scale
//     (nan = illegal), for fitting the players' t by maximum likelihood
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "calib.h"
#include "engine.h"
#include "human.h"

using namespace std;

static Engine E;

struct Pos {
  string id;
  board_t b;
  int played = -1;
};
static vector<Pos> pos;

struct Cond {
  string name;  // as given
  int kind;     // 0 alone, 1 engine, 2 guard, 3 crit, 4 stakes, 5 risk
  double x = 0, comply = 1;
  long budget = -1;  // ":kN": at most N hints per playout (-1: no limit)
};

static vector<double> ts;
static vector<Cond> conds;
static long playouts = 32, max_moves = 30000;
static bool second_target = false;
static double structured = 0;  // --structured S: the player plays the engine's move w.p. S, its softmax move otherwise
// --human: players are the human move model of src/human.h instead of softmax players; each --t value is then a
// personal-model key k (skill s = -ln(100 k): value skill s, structure skill min(s, 0.4), scripts/hm_personal.sh)
static bool human_players = false;
static hm::Model HM;
static double key_skill(double k) { return -std::log(100.0 * k); }
static Calib calib;          // own_cost (condition risk; --calib FILE, default weights/calib/model.txt)
static PersonalModel pmodel;  // theta map (condition risk; --personal-model FILE, default weights/calib/personal.txt)
static string calib_path = "weights/calib/model.txt", personal_path = "weights/calib/personal.txt";
static int phase_of(board_t s) {
  int r = bb::max_rank(s);
  return r <= 9 ? 0 : r <= 11 ? 1 : r <= 13 ? 2 : 3;
}
static bool engine_cont = true;  // mode first: also the engine's continuation (--no-engine: only the players)
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

static Cond parse_cond(const string& s) {
  Cond c;
  c.name = s;
  vector<string> f = split(s, ':');
  if (f[0] == "alone") c.kind = 0;
  else if (f[0] == "engine") c.kind = 1;
  else if (f[0] == "guard") c.kind = 2;
  else if (f[0] == "crit") c.kind = 3;
  else if (f[0] == "stakes") c.kind = 4;
  else if (f[0] == "risk") c.kind = 5;
  else {
    fprintf(stderr, "unknown condition %s\n", s.c_str());
    exit(1);
  }
  if (c.kind >= 2) {
    if (f.size() < 2) {
      fprintf(stderr, "condition %s needs a threshold\n", s.c_str());
      exit(1);
    }
    c.x = stod(f[1]);
  }
  for (size_t i = 2; i < f.size(); i++)
    if (!f[i].empty() && f[i][0] == 'c') c.comply = stod(f[i].substr(1));
    else if (!f[i].empty() && f[i][0] == 'k') c.budget = stol(f[i].substr(1));
  return c;
}

// The softmax player's probabilities (soft_move's formula) and relative 1-ply losses; returns the number of legal moves.
static int soft_probs(board_t b, double t, double p[4], double loss[4]) {
  float q[4];
  bool legal[4];
  float best = -1e30f;
  int n = 0;
  for (int d = 0; d < 4; d++) {
    uint32_t r;
    board_t a = bb::move(b, d, r);
    legal[d] = a != b;
    if (!legal[d]) continue;
    q[d] = r + E.ev(E.view(a));
    best = max(best, q[d]);
    n++;
  }
  double tot = 0;
  for (int d = 0; d < 4; d++) {
    p[d] = 0, loss[d] = NAN;
    if (!legal[d]) continue;
    loss[d] = (best - q[d]) / max(1.0f, fabsf(best));
    if (t > 0) tot += p[d] = exp(-loss[d] / t);
  }
  if (t > 0)
    for (int d = 0; d < 4; d++) p[d] /= tot;
  return n;
}

// The analysis' reference move (analyze.cpp best_legal) and the relative value losses of all moves.
static int engine_losses(EngineThread& T, board_t s, double rel[4], int* engine_move) {
  Analysis A = T.analyze(s);
  *engine_move = A.engine_move;
  int bv = -1;
  if (A.engine_move >= 0 && string(A.source) != "search") bv = A.engine_move;
  if (bv < 0)
    for (int d = 0; d < 4; d++)
      if (A.mv[d].legal && !A.mv[d].lock_skip && (bv < 0 || A.mv[d].value > A.mv[bv].value)) bv = d;
  if (bv < 0)
    for (int d = 0; d < 4; d++)
      if (A.mv[d].legal && (bv < 0 || A.mv[d].value > A.mv[bv].value)) bv = d;
  for (int d = 0; d < 4; d++)
    rel[d] = A.mv[d].legal && bv >= 0
                 ? max(0.0, (double)(A.mv[bv].value - A.mv[d].value)) / max(100000.0, (double)fabsf(A.mv[bv].value))
                 : NAN;
  return bv;
}

struct Outcome {
  bool r1 = false, r2 = false, died = false;
  long moves = 0, shown = 0, changed = 0;
};

static uint64_t stream_seed(size_t p, long k) { return seed * 0x9E3779B97F4A7C15ULL + p * 1000003ULL + (uint64_t)k * 7919ULL; }

// Plays from real board s0 (already after any forced first move: `last` is an afterstate, spawn comes first when
// `spawn_first`) until the final target, death or the move cap.
static Outcome play_out(EngineThread& T, board_t start, bool spawn_first, int target1, double t, const Cond& c,
                        bb::Rng& srng, bb::Rng& prng, bb::Rng& crng, bb::Rng& lrng) {
  Outcome o;
  int target2 = target1 + 1, final_target = second_target ? target2 : target1;
  board_t s = start;
  int top = bb::max_rank(s);
  o.r1 = top >= target1, o.r2 = top >= target2;
  if (top >= final_target) return o;
  bool need_spawn = spawn_first;
  hm::History hist;  // the human model's habits (its own last moves)
  for (;;) {
    if (need_spawn) s = bb::spawn(s, srng);
    need_spawn = true;
    if (o.moves >= max_moves) break;
    int d = -1;
    if (c.kind == 1) {
      d = T.choose(s);
    } else {
      int dp = human_players ? hm::move(E, HM, s, hist, key_skill(t), prng, std::min(key_skill(t), 0.4))
                             : soft_move(E, s, t, prng);  // always drawn: the player's own choice
      if (structured > 0) {               // a structured player: mostly the engine's move, softmax lapses
        double u = lrng.uniform();        // always drawn
        if (u < structured && dp >= 0) dp = T.choose(s);
      }
      d = dp;
      bool advise = c.budget < 0 || o.shown < c.budget;
      if (!advise) {
      } else if (dp >= 0 && c.kind == 2) {
        int de = T.choose(s);
        if (de >= 0 && de != dp) {
          double rel[4];
          int em;
          int bv = engine_losses(T, s, rel, &em);
          if (bv >= 0 && !std::isnan(rel[dp]) && rel[dp] >= c.x) {
            bool follow = c.comply >= 1 || crng.uniform() < c.comply;
            o.shown++;
            if (follow) d = bv, o.changed += bv != dp;
          }
        }
      } else if (dp >= 0 && c.kind == 5) {
        double rel[4];
        int em;
        int bv = engine_losses(T, s, rel, &em);
        if (bv >= 0) {
          int ph = phase_of(s);
          double th = pmodel.theta_of_key(t, ph), p[4], e = 0;
          if (!std::isnan(th)) hm::probs(E, HM, s, hist, th, p);
          else hm::probs(E, HM, s, hist, key_skill(t), p, std::min(key_skill(t), 0.4));
          for (int k = 0; k < 4; k++) {
            if (std::isnan(rel[k])) continue;
            double oc = k == bv ? 0.0 : calib.own_cost(rel[k], ph);
            e += p[k] * (oc >= 0 ? oc : rel[k]);
          }
          if (e >= c.x) {
            bool follow = c.comply >= 1 || crng.uniform() < c.comply;
            o.shown++;
            if (follow) d = bv, o.changed += bv != dp;
          }
        }
      } else if (dp >= 0 && (c.kind == 3 || c.kind == 4)) {
        double rel[4];
        int em;
        int bv = engine_losses(T, s, rel, &em);
        bool show = false;
        if (bv >= 0) {
          if (c.kind == 3) {
            double p[4], l1[4], e = 0;
            if (human_players)
              hm::probs(E, HM, s, hist, key_skill(t), p, std::min(key_skill(t), 0.4));
            else
              soft_probs(s, t, p, l1);
            if (structured > 0 && em >= 0)
              for (int k = 0; k < 4; k++) p[k] = (1 - structured) * p[k] + (k == em ? structured : 0.0);
            for (int k = 0; k < 4; k++)
              if (!std::isnan(rel[k])) e += p[k] * rel[k];
            show = e >= c.x;
          } else {
            double second = 1e30;
            int n = 0;
            for (int k = 0; k < 4; k++)
              if (!std::isnan(rel[k]) && k != bv) second = min(second, rel[k]), n++;
            show = n > 0 && second >= c.x;
          }
        }
        if (show) {
          bool follow = c.comply >= 1 || crng.uniform() < c.comply;
          o.shown++;
          if (follow) d = bv, o.changed += bv != dp;
        }
      }
    }
    if (d < 0) {
      o.died = true;
      break;
    }
    s = bb::move(s, d);
    hist.push(d);
    o.moves++;
    top = max(top, bb::max_rank(s));
    o.r1 |= top >= target1, o.r2 |= top >= target2;
    if (top >= final_target) break;
  }
  return o;
}

struct Item {
  size_t p;
  int ti;  // index into ts (-1: engine)
  int ci;  // index into conds (mode advice)
  long k0, k1;
};
static vector<Item> items;
static atomic<size_t> next_item{0};
static mutex mu;
static FILE* out_f;
static string mode = "advice";

static string fmt_t(double t) {
  char buf[32];
  snprintf(buf, sizeof buf, "%g", t);
  return buf;
}

static void worker() {
  EngineThread T(E);
  string buf;
  for (;;) {
    size_t w = next_item.fetch_add(1);
    if (w >= items.size()) break;
    const Item& it = items[w];
    const Pos& P = pos[it.p];
    int target1 = bb::max_rank(P.b) + 1;
    double t = it.ti >= 0 ? ts[it.ti] : 0.0;
    buf.clear();
    char line[512];
    if (mode == "advice") {
      const Cond& c = conds[it.ci];
      for (long k = it.k0; k < it.k1; k++) {
        uint64_t s0 = stream_seed(it.p, k);
        bb::Rng srng(s0), prng(s0 ^ 0xD1B54A32D192ED03ULL), crng(s0 ^ 0x8CB92BA72F3D8DD7ULL),
            lrng(s0 ^ 0x2545F4914F6CDD1DULL);
        Outcome o = play_out(T, P.b, false, target1, t, c, srng, prng, crng, lrng);
        snprintf(line, sizeof line, "%s\t%s\t%s\t%ld\t%d\t%d\t%ld\t%ld\t%ld\t%d\n", P.id.c_str(), fmt_t(t).c_str(),
                 c.name.c_str(), k, o.r1, o.r2, o.moves, o.shown, o.changed, o.died);
        buf += line;
      }
    } else {  // first
      Cond c;
      c.kind = it.ti >= 0 ? 0 : 1;
      for (long k = it.k0; k < it.k1; k++) {
        int r1[4], r2[4];
        long mv[4];
        for (int d = 0; d < 4; d++) {
          r1[d] = r2[d] = -1, mv[d] = -1;
          board_t a = bb::move(P.b, d);
          if (a == P.b) continue;
          uint64_t s0 = stream_seed(it.p, k);
          bb::Rng srng(s0), prng(s0 ^ 0xD1B54A32D192ED03ULL), crng(s0 ^ 0x8CB92BA72F3D8DD7ULL),
            lrng(s0 ^ 0x2545F4914F6CDD1DULL);
          Outcome o = play_out(T, a, true, target1, t, c, srng, prng, crng, lrng);
          r1[d] = o.r1, r2[d] = o.r2, mv[d] = o.moves;
        }
        snprintf(line, sizeof line, "%s\t%s\t%ld\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%ld\t%ld\t%ld\t%ld\n", P.id.c_str(),
                 it.ti >= 0 ? fmt_t(t).c_str() : "0", k, r1[0], r1[1], r1[2], r1[3], r2[0], r2[1], r2[2], r2[3],
                 mv[0], mv[1], mv[2], mv[3]);
        buf += line;
      }
    }
    lock_guard<mutex> lk(mu);
    fputs(buf.c_str(), out_f);
    fflush(out_f);
  }
}

int main(int argc, char** argv) {
  string in, out;
  int threads = 16;
  long chunk = 8;
  E.cfg.preset_best(".", false);
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
    } else if (a == "--in") in = next();
    else if (a == "--out") out = next();
    else if (a == "--mode") mode = next();
    else if (a == "--t") {
      ts.clear();
      for (auto& x : split(next(), ',')) ts.push_back(stod(x));
    } else if (a == "--conds") {
      conds.clear();
      for (auto& x : split(next(), ',')) conds.push_back(parse_cond(x));
    } else if (a == "--playouts") playouts = stol(next());
    else if (a == "--chunk") chunk = stol(next());
    else if (a == "--second") second_target = true;
    else if (a == "--no-engine") engine_cont = false;
    else if (a == "--structured") structured = stod(next());
    else if (a == "--human") human_players = true;
    else if (a == "--human-model") {
      string f = next();
      if (!HM.load(f)) {
        fprintf(stderr, "cannot read %s\n", f.c_str());
        return 1;
      }
    }
    else if (a == "--max-moves") max_moves = stol(next());
    else if (a == "--calib") calib_path = next();
    else if (a == "--personal-model") personal_path = next();
    else if (a == "--threads") threads = stoi(next());
    else if (a == "--seed") seed = stoull(next());
    else {
      fprintf(stderr, "unknown option %s\n", a.c_str());
      return 1;
    }
  }
  if (mode != "advice" && mode != "first" && mode != "fit") {
    fprintf(stderr, "unknown mode %s\n", mode.c_str());
    return 1;
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
    if (!parse_board(c[1], &p.b)) {
      fprintf(stderr, "bad board %s\n", c[1].c_str());
      return 1;
    }
    if (c.size() >= 3 && !c[2].empty()) {
      const char* dirs = "URDL";
      const char* q = strchr(dirs, toupper(c[2][0]));
      p.played = q ? (int)(q - dirs) : -1;
    }
    pos.push_back(p);
  }
  fclose(f);
  if (!E.load(false)) return 1;
  calib.load(calib_path);
  pmodel.load(personal_path);
  for (auto& c : conds)
    if (c.kind == 5 && (!calib.ok() || pmodel.thetamap.empty()))
      fprintf(stderr, "condition %s: %s\n", c.name.c_str(),
              !calib.ok() ? "no calibration model (own_cost)" : "no theta map: the playout family's own probabilities");
  out_f = out.empty() ? stdout : fopen(out.c_str(), "w");
  if (!out_f) {
    fprintf(stderr, "cannot write %s\n", out.c_str());
    return 1;
  }
  if (mode == "fit") {
    fprintf(out_f, "id\tplayed\tl_U\tl_R\tl_D\tl_L\n");
    for (auto& P : pos) {
      double p[4], l[4];
      soft_probs(P.b, 0, p, l);
      fprintf(out_f, "%s\t%c", P.id.c_str(), P.played >= 0 ? kDirChar[P.played] : '-');
      for (int d = 0; d < 4; d++) fprintf(out_f, std::isnan(l[d]) ? "\tnan" : "\t%.6g", l[d]);
      fprintf(out_f, "\n");
    }
    if (out_f != stdout) fclose(out_f);
    return 0;
  }
  // work items: the slow ones (engine-consulting conditions) first, so the tail is made of cheap items
  for (int pass = 0; pass < 2; pass++)
    for (size_t p = 0; p < pos.size(); p++)
      for (long k0 = 0; k0 < playouts; k0 += chunk) {
        long k1 = min(playouts, k0 + chunk);
        if (mode == "advice") {
          for (size_t ci = 0; ci < conds.size(); ci++) {
            bool slow = conds[ci].kind != 0;
            if (slow != (pass == 0)) continue;
            if (conds[ci].kind == 1) items.push_back(Item{p, -1, (int)ci, k0, k1});
            else
              for (size_t ti = 0; ti < ts.size(); ti++) items.push_back(Item{p, (int)ti, (int)ci, k0, k1});
          }
        } else {
          if (pass == 0) {
            if (engine_cont) items.push_back(Item{p, -1, -1, k0, k1});
          }
          else
            for (size_t ti = 0; ti < ts.size(); ti++) items.push_back(Item{p, (int)ti, -1, k0, k1});
        }
      }
  if (mode == "advice")
    fprintf(out_f, "id\tt\tcond\tk\treached1\treached2\tmoves\tshown\tchanged\tdied\n");
  else
    fprintf(out_f, "id\tcont\tk\tr1_U\tr1_R\tr1_D\tr1_L\tr2_U\tr2_R\tr2_D\tr2_L\tm_U\tm_R\tm_D\tm_L\n");
  fflush(out_f);
  fprintf(stderr, "%zu positions, %zu work items (%s), %d threads\n", pos.size(), items.size(), mode.c_str(), threads);
  vector<thread> th;
  for (int t = 0; t < threads; t++) th.emplace_back(worker);
  for (auto& t : th) t.join();
  if (out_f != stdout) fclose(out_f);
  fprintf(stderr, "done\n");
  return 0;
}
