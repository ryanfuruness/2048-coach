// Position analysis and game review with the full engine (v0).
//
//   build/analyze --preset best [engine flags] [--depth D] [--json] BOARD...   analyze positions
//   build/analyze --preset best --stdin                                       one board per input line -> one JSON line
//                                                                              (a line may start with options and '|':
//                                                                              "depth=4 risk=1 line=10 | BOARD"; with
//                                                                              --stdin-player also "skill=-0.5 hist=LDR")
//   build/analyze --preset best --review FILE [--json]                         review a game: FILE holds consecutive
//                                                                              boards, one per line; the moves between
//                                                                              two boards are inferred (up to --max-gap
//                                                                              moves, default 3, for skipped frames)
//                                                                              (--review-moves: "BOARD U" lines give
//                                                                              the move played from a board)
// A BOARD is 16 tile values (row by row, 0 = empty, any separators) or 16 hex rank digits. --preset best-notables
// runs without the 88 GB of exact tables. Values are in points: the move's merge reward plus the expected future
// reward with the engine playing on (expectimax at the engine's depth over the network's values). Loss = best value -
// the move's value. Where an exact endgame table applies, p = the table's success probability after the move.
// Each move gets plain-word reasons (explain.h); --risk D adds what the random tile can do after each move (every
// spawn valued by expectimax at depth D). --calib MODEL.txt (scripts/fit_calib.py) adds calibrated odds of reaching
// the next tiles and calibrated expected future points. --personal T adds "personal odds": the share of playouts by a
// human-like player of skill temperature T (see --review's skill estimate) that reach the next tiles; with a skill map
// in the personal model (--personal-model FILE, default weights/calib/personal.txt), T is read on the review's scale
// and converted to the softmax player that reviews like it.
#include <chrono>
#include <cstdio>
#include <cstring>
#include <array>
#include <atomic>
#include <iostream>
#include <map>
#include <mutex>
#include <thread>
#include <sstream>
#include <string>
#include <vector>
#include "engine.h"
#include "explain.h"
#include "calib.h"
#include "human.h"
#include "hplayer.h"
#include "hvalue.h"
#include "expl.h"

using namespace std;
using Clock = chrono::steady_clock;

static string fmt(double v, int prec = 1) {
  if (std::isnan(v)) return "null";
  char buf[64];
  snprintf(buf, sizeof buf, "%.*f", prec, v);
  return buf;
}

// The reference move that losses are measured against: the engine's move when an exact table decided it, else the
// best-valued legal move among those the engine's corner lock allows (a corner-breaking move can carry a higher raw
// value, but the engine never plays it: the lock exists because those values are unreliable).
static int best_legal(const Analysis& A) {
  if (A.engine_move >= 0 && string(A.source) != "search") return A.engine_move;
  int b = -1;
  for (int d = 0; d < 4; d++)
    if (A.mv[d].legal && !A.mv[d].lock_skip && (b < 0 || A.mv[d].value > A.mv[b].value)) b = d;
  if (b < 0)
    for (int d = 0; d < 4; d++)
      if (A.mv[d].legal && (b < 0 || A.mv[d].value > A.mv[b].value)) b = d;
  return b;
}

// The block formation (src/block.h): some experts keep their biggest tiles in a 3x2 block in a corner instead of a
// snake along an edge. The engine plays snakes; in block positions its values carry no information about the moves
// (expert disputes: claimed 21% value loss -> real -1%; claim vs real loss r ~ 0 for every network tried), so there it
// judges moves only where the exact block tables (--block-tables) decide, and otherwise not at all. Only from a real
// 16384 on: on smaller boards short chains that happen to sit in a corner block fire the detector (4% of strong
// players' 8192 positions), and there the engine's judgement is fine.
static bool block_position(board_t b) {
  return ex::display_rank[bb::max_rank(b)] >= 14 && blk::block_formation(b, 0, ex::display_rank);
}
static bool not_judged(const Analysis& A) { return strcmp(A.source, "search") == 0 && block_position(A.board); }
// The plan line in block positions: the block itself (the snake plans of explain.h do not apply there).
static string block_plan(board_t b) {
  int r[16];
  blk::ranks_of(b, r, ex::display_rank);  // real ranks
  int p = blk::block_placement(r);
  static const char* corner[8] = {"top-left",    "top-right",   "bottom-left", "bottom-right",
                                  "top-left",    "bottom-left", "top-right",   "bottom-right"};
  string s = string("Your biggest tiles form a block in the ") + (p >= 0 ? corner[p] : "a") + " corner";
  if (p >= 0) {
    vector<int> t;
    for (int c : blk::kPlacements[p])
      if (r[c]) t.push_back(r[c]);
    sort(t.rbegin(), t.rend());
    s += " (";
    for (size_t i = 0; i < t.size(); i++) s += (i ? ", " : "") + to_string(1L << t[i]);
    s += ")";
  }
  return s + ": build each next tile next to the block's smallest tile so that it can merge into it.";
}

// The plan as data (for an app: which cells to highlight): type (as ex::Plan, or "block"), the chain's cells (0 =
// top-left, row by row) and tiles, the next cell, the tile it needs, what is there, and what the chain merges into.
// The plan sentence: the block line in block positions, else ex::plan with the engine's best move (a merge the plan
// names but the best move does not make is not phrased as an instruction).
static string plan_text(const Analysis& A) {
  if (block_position(A.board)) return block_plan(A.board);
  int bv = best_legal(A);
  return ex::plan(A.board, bv, bv >= 0 ? kDirName[bv] : nullptr);
}
static string plan_json(board_t b) {
  if (block_position(b)) return "{\"type\":\"block\"}";
  ex::Plan P = ex::plan_info(b);
  string s = "{\"type\":\"" + (P.type.empty() ? string("none") : P.type) + "\"";
  if (P.step != P.type && !P.step.empty()) s += ",\"step\":\"" + P.step + "\"";
  if (P.type == "pair") s += ",\"biggest_cell\":" + to_string(P.pair_cell);
  if (P.corner_cell >= 0) s += ",\"corner_cell\":" + to_string(P.corner_cell);
  if (P.len > 0) {
    s += ",\"chain\":[";
    for (int i = 0; i < P.len; i++) s += (i ? "," : "") + to_string(P.chain.cells[i]);
    s += "],\"tiles\":[";
    for (int i = 0; i < P.len; i++) s += (i ? "," : "") + ex::tile(P.chain.ranks[i]);
    s += "]";
  }
  if (P.next_cell >= 0) {
    s += ",\"next_cell\":" + to_string(P.next_cell) + ",\"needs\":" + ex::tile(P.end) +
         ",\"there\":" + (P.there ? ex::tile(P.there) : string("0"));
    if (P.step != "blocked") s += ",\"merges_into\":" + ex::real_tile(P.made_real);
  } else if (P.step == "single" && P.chain.orient >= 0) {  // the cell next to the corner and what it must become
    int c1 = ex::path_cell(P.chain.orient, 1), v1 = bb::cell(b, c1), cr = bb::cell(b, P.corner_cell);
    s += ",\"next_cell\":" + to_string(c1) + ",\"there\":" + (v1 ? ex::tile(v1) : string("0")) + ",\"needs\":" +
         (P.type == "pair" ? ex::tile(cr) : ex::real_tile(ex::real_rank(cr) - 1));
  }
  return s + "}";
}
static string jstr(const string& t) {
  string o = "\"";
  for (char c : t) {
    if (c == '"' || c == '\\') o += '\\';
    o += c;
  }
  return o + "\"";
}

static double rel_value_loss(const Analysis& A, int d, int bv);
static EngineThread* reason_thread = nullptr;  // for spawn-based reasons
static int reason_only = -1;  // >= 0 (reviews): the expensive reasons (risk, look-ahead, attribution) only for this move
static const Engine* heat_engine = nullptr;     // for attribution-based reasons and --heat
// The part of a move's value deficit due to its risk: the move made only as risky as the reference (the mass of its
// deadly - or clearly bad - next tiles reduced to the reference's share, the rest renormalized; spawn values at depth
// 2); NaN without excess risk.
static double risk_gain(const vector<EngineThread::Spawn>& sm, const vector<EngineThread::Spawn>& sb, double vm,
                        double vb, bool dead) {
  auto bad = [&](const EngineThread::Spawn& x, double mean) {
    return dead ? x.value <= 0 : x.value < mean - 0.05 * fabs(mean);
  };
  double pm = 0, pb = 0;
  for (auto& x : sm) pm += bad(x, vm) ? x.prob : 0;
  for (auto& x : sb) pb += bad(x, vb) ? x.prob : 0;
  if (pm <= pb || pm >= 0.999) return NAN;
  double ks = pb / pm, kr = (1 - pb) / (1 - pm), v = 0;
  for (auto& x : sm) v += x.prob * (bad(x, vm) ? ks : kr) * x.value;
  return v - vm;
}
// Reasons per legal move: strengths for the best move, weaknesses vs the best for the others.
static vector<vector<ex::Reason>> reasons(const Analysis& A) {
  vector<vector<ex::Reason>> out(4);
  int bv = best_legal(A);
  if (bv < 0) return out;
  if (not_judged(A)) {  // block formation: the engine's concepts are a snake player's; no verdicts, only a suggestion
    out[bv].push_back({"block", "only a suggestion: the engine plays a different formation (a snake along an edge) and "
                                "does not judge moves in this block formation"});
    return out;
  }
  // an exact table decided: its success chances are the most faithful reason (first in the list); in the block
  // formation the only one (the concepts below are a snake player's)
  vector<vector<ex::Reason>> tab(4);
  if (strcmp(A.source, "search") != 0 && A.mv[bv].table_p >= 0) {
    bool block = strcmp(A.source, "block") == 0;
    string what = block ? "block" : "chain";
    for (int d = 0; d < 4; d++)
      if (A.mv[d].legal && d != bv && A.mv[d].table_p >= 0 && A.mv[bv].table_p - A.mv[d].table_p >= 0.02)
        tab[d].push_back({"table", "leaves a " + to_string((int)lround(100 * A.mv[d].table_p)) +
                                       "% chance to build the tile your " + what + " needs next (exact table; " +
                                       to_string((int)lround(100 * A.mv[bv].table_p)) + "% after " + kDirName[bv] + ")"});
    if (block) {
      tab[bv].push_back({"table", "keeps a " + to_string((int)lround(100 * A.mv[bv].table_p)) +
                                      "% chance to build the tile your block needs next (exact table)"});
      // a move that leaves the block's shape: the tables say nothing about it, but say what it gives up
      for (int d = 0; d < 4; d++)
        if (A.mv[d].legal && d != bv && A.mv[d].table_p < 0)
          tab[d].push_back({"table", string("breaks your block: the exact tables no longer apply after it (") +
                                         kDirName[bv] + " keeps a " + to_string((int)lround(100 * A.mv[bv].table_p)) +
                                         "% chance to build the tile your block needs next)"});
      return tab;
    }
  }
  vector<board_t> others;
  for (int d = 0; d < 4; d++)
    if (A.mv[d].legal && d != bv) {
      others.push_back(A.mv[d].after);
      // near-equal moves get no weaknesses: a concept difference that costs nothing would mislead
      if (rel_value_loss(A, d, bv) >= 0.02) out[d] = ex::compare(A.board, A.mv[bv].after, A.mv[d].after);
    }
  out[bv] = ex::strengths(A.board, A.mv[bv].after, others);
  // a clearly worse move with no concept-level reason: first what the random tile can do (from the search itself),
  // else say honestly that it is the engine's look-ahead
  double best_bad = -1, best_dead = 0;
  for (int d = 0; d < 4; d++) {
    if (!A.mv[d].legal || d == bv) continue;
    if (reason_only >= 0 && d != reason_only) continue;
    double rel = rel_value_loss(A, d, bv);
    if (rel < 0.03 || A.mv[d].lock_skip) continue;  // small losses need no reason; "breaks the corner" is shown already
    if (reason_thread) {
      // what the random tile can do after each move: share of new tiles that leave the position clearly worse off
      auto bad_share = [&](board_t after, double* dead) {
        auto sp = reason_thread->spawns(after, 1);
        double mean = 0, bad = 0;
        *dead = 0;
        for (auto& x : sp) mean += x.prob * x.value;
        for (auto& x : sp) {
          bad += (mean - x.value > 0.05 * fabs(mean)) ? x.prob : 0;
          *dead += x.value <= 0 ? x.prob : 0;  // no legal move after that tile: game over
        }
        return bad;
      };
      double dm, db;
      if (best_bad < 0) best_bad = bad_share(A.mv[bv].after, &db), best_dead = db;
      double bm = bad_share(A.mv[d].after, &dm);
      if (bm >= best_bad + 0.15) {
        string text = dm >= 0.2 && dm >= best_dead + 0.15
                          ? "lets the next tile end the game in " + to_string((int)lround(100 * dm)) + "% of cases (vs " +
                                to_string((int)lround(100 * best_dead)) + "% after " + kDirName[bv] + ")"
                          : "is riskier: " + to_string((int)lround(100 * bm)) +
                                "% of the possible new tiles leave you clearly worse off (vs " +
                                to_string((int)lround(100 * best_bad)) + "% after " + kDirName[bv] + ")";
        ex::Reason r{"risk", text};
        if (bm >= best_bad + 0.3) out[d].insert(out[d].begin(), r);  // a large gap is the main reason
        else out[d].push_back(r);
      }
    }
    // each reason checked in this very position (workstream expl, 2026-10-07): the edit that removes exactly the defect
    // it names (xp::fix; for the risk reason: the move made only as risky as the reference) must recover a real share
    // of the move's loss; reasons recovering less than 10% are dropped and the rest ordered by that share. On 708 real
    // (position, move) pairs the fixed order's first reason was the biggest cause in only 45% of them, and the edits
    // for "exposed", "center" and "toward_corner" made the position worse in 36-39% of their cases.
    if (reason_thread && !out[d].empty()) {
      auto sm = reason_thread->spawns(A.mv[d].after, 2), sb = reason_thread->spawns(A.mv[bv].after, 2);
      double vm = 0, vb = 0;
      for (auto& x : sm) vm += x.prob * x.value;
      for (auto& x : sb) vb += x.prob * x.value;
      double L0 = (A.mv[bv].reward + vb) - (A.mv[d].reward + vm);
      if (L0 > 0.005 * max(100000.0, (double)fabsf(A.mv[bv].value))) {
        bb::Rng rng(A.board ^ (0x9E3779B97F4A7C15ULL * (uint64_t)(d + 1)));
        vector<ex::Reason> kept;
        for (auto& r : out[d]) {
          double gain = NAN;
          if (r.code == "risk") {
            gain = risk_gain(sm, sb, vm, vb, r.text.rfind("lets the next tile", 0) == 0);
          } else {
            board_t e;
            if (xp::fix(r.code, A.board, A.mv[bv].after, A.mv[d].after, rng, &e)) {
              double ve = 0;
              for (auto& x : reason_thread->spawns(e, 2)) ve += x.prob * x.value;
              gain = ve - vm;
            }
          }
          if (std::isnan(gain)) continue;
          r.share = gain / L0;
          if (r.share >= 0.10) kept.push_back(r);
        }
        stable_sort(kept.begin(), kept.end(), [](const ex::Reason& a, const ex::Reason& b) { return a.share > b.share; });
        out[d] = kept;
      }
    }
    if (!out[d].empty()) continue;
    // (the area reason comes before the look-ahead one: copying the named area from the reference move's afterstate
    // recovers the whole loss in the median case - 79% of cases at least half - while "a few moves later ..." cannot be
    // checked by an edit; workstream expl, 2026-10-07)
    // where the engine's evaluation sees the difference: the 2x2 area with the largest value deficit (per-cell
    // attribution of the network value, move minus best), named by its biggest tiles before the move
    if (heat_engine) {
      float hm[16], hb[16];
      heat_engine->ev.attribute(heat_engine->view(A.mv[d].after), hm);
      heat_engine->ev.attribute(heat_engine->view(A.mv[bv].after), hb);
      float total = 0, worst = 0;
      int wr = -1, wc = -1;
      for (int c = 0; c < 16; c++) total += hm[c] - hb[c];
      for (int r = 0; r < 3; r++)
        for (int c = 0; c < 3; c++) {
          float x = 0;
          for (int dr = 0; dr < 2; dr++)
            for (int dc = 0; dc < 2; dc++) x += hm[(r + dr) * 4 + c + dc] - hb[(r + dr) * 4 + c + dc];
          if (x < worst) worst = x, wr = r, wc = c;
        }
      if (total < 0 && wr >= 0 && worst < 0.5f * total) {
        int t1 = 0, t2 = 0;  // the two biggest tiles of the area on the board before the move
        for (int dr = 0; dr < 2; dr++)
          for (int dc = 0; dc < 2; dc++) {
            int v = bb::cell(A.board, (wr + dr) * 4 + wc + dc);
            if (v > t1) t2 = t1, t1 = v;
            else if (v > t2) t2 = v;
          }
        static const char* vert[3] = {"top", "middle", "bottom"};
        static const char* hor[3] = {"left", "center", "right"};
        string area = string(vert[wr]) + (wc == 1 ? "" : string("-") + hor[wc]) + " area";
        if (wr == 1 && wc == 1) area = "center of the board";
        int mx = bb::max_rank(A.board), keep = max(4, mx - 5);  // name only tiles that matter (>= 16, >= max/32)
        if (t2 < keep) t2 = 0;
        string tiles = t1 >= keep ? "your " + ex::tile(t1) + (t2 && t2 != t1 ? " and " + ex::tile(t2) : (t2 == t1 ? "s" : "")) : "";
        out[d].push_back({"area", "weakens the " + area + (tiles.empty() ? "" : " around " + tiles) +
                                      ": that is where the engine's evaluation drops most"});
        continue;
      }
    }
    // the consequences a few moves later: the engine plays 6 moves after each move (4 seeds, the same random tiles for
    // both); the validated concept that differs most on average names the difference. The moves come from a fixed
    // depth-3 search, not the engine's budgeted one: that took up to 1.7-4 s per analysis in open late positions (48
    // searches), and on 200 real positions the depth-3 look-ahead names the same concept in 28 of 29 cases (fuzz study).
    if (reason_thread) {
      auto future = [&](board_t after, uint64_t seed) {
        bb::Rng rng(seed);
        board_t x = bb::spawn(after, rng);
        for (int k = 0; k < 6; k++) {
          board_t xv = reason_thread->E.view(x);
          SearchParams sp = reason_thread->E.params(xv);
          sp.budget = 0, sp.max_depth = sp.min_depth = std::min(sp.max_depth, 3);
          int mv = reason_thread->search->best_move(xv, sp, &reason_thread->st);
          if (mv < 0) break;
          x = bb::spawn(bb::move(x, mv), rng);
        }
        return x;
      };
      double dch = 0, dex = 0, dce = 0, dtr = 0, dco = 0, chm = 0, chb = 0;
      const int K = 4;
      for (int k = 0; k < K; k++) {
        uint64_t seed = A.board * 2654435761ULL + k;
        ex::Features fm = ex::features(future(A.mv[d].after, seed)), fb = ex::features(future(A.mv[bv].after, seed));
        dch += fb.chain_len - fm.chain_len, chm += fm.chain_len, chb += fb.chain_len;
        dex += fm.exposed - fb.exposed, dce += fm.big_off_edge - fb.big_off_edge, dtr += fm.trapped - fb.trapped;
        dco += (int)fb.corner - (int)fm.corner;
      }
      dch /= K, dex /= K, dce /= K, dtr /= K, dco /= K, chm /= K, chb /= K;
      string why;
      if (dco >= 0.5) why = "your biggest tile usually ends up out of its corner";
      else if (dch >= 1.5) why = "your chain is typically shorter (" + to_string((int)lround(chm)) + " vs " + to_string((int)lround(chb)) + " tiles)";
      else if (dex >= 1.0) why = "more cells next to your big tiles are open for small tiles";
      else if (dce >= 0.75) why = "big tiles tend to drift into the middle of the board";
      else if (dtr >= 0.75) why = "small tiles tend to get stuck between big ones";
      if (!why.empty()) {
        out[d].push_back({"later", "a few moves later " + why});
        continue;
      }
    }
    out[d].push_back({"shape", string("gives up long-term chances: the engine's look-ahead prefers ") + kDirName[bv]});
  }
  for (int d = 0; d < 4; d++) out[d].insert(out[d].begin(), tab[d].begin(), tab[d].end());
  return out;
}

// Spawn risk per legal move (with --risk): probability that the new tile costs more than 5% of the move's expected
// value, and the worst spawn.
struct Risk {
  bool on = false;
  float bad_prob = 0, worst_loss = 0, worst_prob = 0;
  int worst_cell = -1, worst_rank = 0;
};
static int risk_depth = 0;
static bool want_features = false;
static bool want_heat = false;  // --heat: per-cell value attribution of each move's afterstate minus the reference move's  // --features: concept features of every afterstate in the JSON (explanation study)
static vector<Risk> risks(EngineThread& T, const Analysis& A) {
  vector<Risk> out(4);
  if (risk_depth <= 0) return out;
  for (int d = 0; d < 4; d++) {
    if (!A.mv[d].legal) continue;
    auto sp = T.spawns(A.mv[d].after, risk_depth);
    double mean = 0;
    for (auto& x : sp) mean += x.prob * x.value;
    Risk& r = out[d];
    r.on = true;
    for (auto& x : sp) {
      float loss = (float)(mean - x.value);
      if (loss > 0.05 * fabs(mean)) r.bad_prob += x.prob;
      if (r.worst_cell < 0 || loss > r.worst_loss) r.worst_loss = loss, r.worst_cell = x.cell, r.worst_rank = x.rank, r.worst_prob = x.prob;
    }
  }
  return out;
}

static Calib calib;
// relative value loss of move d (normalized by max(|best value|, 100k), as in the calibration fits) and its estimated
// real loss (the judge study's map; without a map the value loss itself)
static double rel_value_loss(const Analysis& A, int d, int bv) {
  return max(0.0, (double)(A.mv[bv].value - A.mv[d].value)) / max(100000.0, (double)fabsf(A.mv[bv].value));
}
// positions with a real tile of 2048 or more use the late map (damage there is repaired less), 16384 or more the top
// map when the model has one
static double rel_real_loss(const Analysis& A, int d, int bv) {
  if (not_judged(A)) return NAN;  // block formation without a deciding table: no verdict
  // a table decided the position and both moves have the exact success probability: the table's verdict (mapped to
  // the real loss: failing the table's sub-goal is partly repaired) - the network values can miss what the table sees
  bool played_review = reason_only >= 0 && d == reason_only;  // a player's own move in a review
  if (strcmp(A.source, "search") != 0) {
    double t = calib.table_real_loss(A.mv[bv].table_p, A.mv[d].table_p, played_review);
    if (t >= 0) return d == bv ? 0.0 : t;
  }
  int real_max = ex::display_rank[bb::max_rank(A.board)];
  // in reviews (reason_only = the played move), a player's own choice in expert territory gets the expert map
  bool played_expert = reason_only >= 0 && d == reason_only && real_max >= 14;
  return calib.real_loss(rel_value_loss(A, d, bv), real_max >= 14 ? 2 : real_max >= 11 ? 1 : 0, played_expert);
}
// "{"4096":0.99,...}" for the targets above the board's largest tile, or "" without a model
// Immediate danger the value-based model under-weighs (near-dead boards are rare in its data): odds are scaled by the
// share of next tiles after the move that do NOT end the game (set per position/move by survival()).
static EngineThread* survive_thread = nullptr;
// Also returns (if surv_value is given) the mean value of the positions after the spawns that do not end the game, so
// that the odds model's value term does not count the same danger a second time.
static double survival(board_t after, double* surv_value = nullptr) {
  if (!survive_thread) return 1.0;
  auto sp = survive_thread->spawns(after, 1);
  double dead = 0, live_p = 0, live_v = 0;
  for (auto& x : sp) {
    if (x.value <= 0) dead += x.prob;
    else live_p += x.prob, live_v += x.prob * x.value;
  }
  if (surv_value && live_p > 0) *surv_value = live_v / live_p;
  return 1.0 - dead;
}
// The odds models take the REAL board's largest tile (which targets are still open) and tile sum (the stage): big
// tiles may be stored lowered in the engine's board (map_search_board), ex::display_rank maps them back. (The value
// stays the network's value of the engine's board; expected_future keeps the engine board's sum, the value's scale.)
static int real_max_tile(board_t b) { return 1 << ex::display_rank[bb::max_rank(b)]; }
static double real_tile_sum(board_t b) {
  double s = 0;
  for (int c = 0; c < 16; c++) {
    int r = (int)((b >> (4 * c)) & 15);
    if (r) s += std::ldexp(1.0, ex::display_rank[r]);
  }
  return s;
}
// Formation features of the board the odds are read from (workstream anypos; scripts/anypos_feats.py): big tiles
// (rank >= the biggest's - 3) in rank order, each adding its distance - 1 to the nearest bigger-or-equal big tile.
static int far_of(board_t a) {
  int R = bb::max_rank(a);
  vector<int> big;
  for (int c = 0; c < 16; c++)
    if (bb::cell(a, c) > 0 && bb::cell(a, c) >= R - 3) big.push_back(c);
  stable_sort(big.begin(), big.end(), [&](int x, int y) { return bb::cell(a, x) > bb::cell(a, y); });
  int far = 0;
  for (size_t i = 1; i < big.size(); i++) {
    int d = 99;
    for (size_t j = 0; j < i; j++) d = min(d, abs(big[i] / 4 - big[j] / 4) + abs(big[i] % 4 - big[j] % 4));
    far += max(0, d - 1);
  }
  return far;
}
// far_of breaks ties between equal big tiles by cell order, so it differs between mirror images of a board: the odds
// use its minimum over the 8 symmetries (found by workstream expl's symmetry check: P(16384) 0.071 vs 0.026 on a
// board and its mirror with three 4096s)
static int far_sym(board_t a) {
  int best = far_of(a);
  for (int j = 1; j < 8; j++) best = min(best, far_of(eg::sym(a, j)));
  return best;
}
// The odds' formation correction (calib.h ocorr) for the afterstate a: exposed cells next to big tiles beyond 2, the
// biggest tile 2+ steps from its corner on a crowded board, big tiles stranded 2+ cells beyond touching.
static double shape_shift(board_t b, board_t a) {
  if (calib.ocorr.empty()) return 0;
  ex::Features f = ex::features(a);
  double crowd = min(1.0, max(0.0, 1.0 - f.empty / 12.0));
  return calib.shape_shift(real_tile_sum(b), {{"exposed_g", max(0, f.exposed - 2) / 2.0},
                                               {"corner_g", max(0, f.corner_dist - 1) / 2.0 * crowd},
                                               {"far_g3", max(0, far_sym(a) - 2) / 3.0}});
}
// Positions whose formation lies outside what the odds were calibrated on (largest real tile >= 4096 and: 3+ exposed
// cells next to big tiles, 2+ trapped small tiles, the biggest tile 2+ steps from its corner on a crowded board, big
// tiles stranded apart; from 8192 also the biggest tile out of its corner): there the odds' error is 2-3x larger
// (workstream anypos: odd positions flagged MAE ~0.2-0.3 vs 0.05 unflagged; real positions 0.17 vs 0.08) - a caveat.
static bool odds_caveat(board_t b, board_t a) {
  long top = real_max_tile(b);
  if (top < 4096) return false;
  ex::Features f = ex::features(a);
  return f.exposed >= 3 || f.trapped >= 2 || (f.empty <= 6 && f.corner_dist >= 2) || far_sym(a) >= 2 ||
         (top >= 8192 && !f.corner);
}
static map<int, double> odds_of(board_t b, float value, board_t after) {
  double v = value;
  double sv = survival(after, &v);
  auto o = calib.odds(real_max_tile(b), real_tile_sum(b), v, shape_shift(b, after));
  for (auto& kv : o) kv.second *= sv;
  return o;
}
static string odds_json(board_t b, float value, board_t after) {
  if (!calib.ok() || std::isnan(value)) return "";
  string s;
  for (auto& t : odds_of(b, value, after))
    s += (s.empty() ? "{" : ",") + string("\"") + to_string(t.first) + "\":" + fmt(t.second, 3);
  return s.empty() ? "" : s + "}";
}

// A sample continuation (with --line N): the engine plays N moves from the position with random new tiles (fixed seed,
// so the same position always shows the same line) - the 2048 counterpart of a principal variation.
static int line_len = 0;
static vector<pair<int, board_t>> continuation(EngineThread& T, board_t b) {
  vector<pair<int, board_t>> out;
  bb::Rng rng(b ^ 0x2048ULL);
  for (int i = 0; i < line_len; i++) {
    int d = T.choose(b);
    if (d < 0) break;
    board_t a = bb::move(b, d);
    b = bb::spawn(a, rng);
    out.push_back({d, b});
  }
  return out;
}
static vector<pair<int, board_t>> cur_line;

// Personal odds (with --personal T): share of N playouts by the soft:T player (a human-like player whose skill is the
// temperature, e.g. fitted by --review) that reach each tile above the board's largest, per thread-parallel playouts.
static double personal_t = 0;
static int personal_n = 200, personal_threads = 4;
// The player's skill on the human move model's scale (src/human.h; --skill THETA, or derived from --personal T through
// the personal model's skill and theta maps); NaN: unknown. With a skill, every move gets the probability that a
// player of that skill plays it (find_prob) and the position its error risk and hint flag (workstream hm2).
static double human_theta = NAN;
static hm::History cur_hist;  // the player's previous moves (filled by reviews; empty for single positions)
// The review's phases by the real largest tile (0: up to 512, 1: 1024-2048, 2: 4096-8192, 3: 16384+); a skill t from a
// review is a per-phase quantity, converted to the soft player of the personal model by its skill map (pskillmap).
static int skill_phase(board_t b) {
  int r = ex::display_rank[bb::max_rank(b)];
  return r <= 9 ? 0 : r <= 11 ? 1 : r <= 13 ? 2 : 3;
}
// The loss-map stage of a position (as rel_real_loss: 0 up to 1024, 1 from 2048, 2 from 16384; real tiles).
static int map_stage(board_t b) {
  int r = ex::display_rank[bb::max_rank(b)];
  return r >= 14 ? 2 : r >= 11 ? 1 : 0;
}
// "Your cost" of move d: the share of a human-like player's OWN chances of reaching the next milestone (the next
// doubling of the largest tile) that the move costs against the engine's move (Calib::own_cost, fitted on the coach
// study's playouts: players repair less than the engine, and the cost barely depends on their skill). Where no map
// applies (16384+: no human-like players reach it; table-decided positions) the engine's real loss stands in. NaN
// where moves are not judged.
static double player_theta(board_t b);
static double your_cost(const Analysis& A, int d, int bv) {
  double rl = rel_real_loss(A, d, bv);
  if (std::isnan(rl)) return NAN;
  if (d == bv) return 0.0;
  // by skill band when the player's skill is known (--skill, or --personal T converted); else the phase map
  double c = strcmp(A.source, "search") == 0
                 ? calib.own_cost(rel_value_loss(A, d, bv), skill_phase(A.board), player_theta(A.board))
                 : -1;
  return c >= 0 ? c : rl;
}
// Would an app warn before move d is committed? The coach study: a warning just before a bad move (with the engine's
// move offered instead) helps human-like players far more per intervention than hints shown in advance; the
// thresholds are relative value losses per phase (the model's "warn" line; defaults 0.15 up to 512, 0.05 for
// 1024-8192, 0.30 from 16384, where the current networks overstate losses). Where a table decided, its verdict is
// compared with the real loss the threshold stands for.
static bool warn_move(const Analysis& A, int d, int bv) {
  if (bv < 0 || d == bv || !A.mv[d].legal || not_judged(A)) return false;
  double thr = calib.warn[skill_phase(A.board)];
  if (strcmp(A.source, "search") != 0) {
    double t = calib.table_real_loss(A.mv[bv].table_p, A.mv[d].table_p);
    // the table's own verdict: a real loss of 10% or more (a table loss of ~15%). Comparing it with the value maps'
    // real loss at the threshold made table losses of 0.1-5% warn: 220 of 731 warnings in 100 real stretches, false
    // alarms at the random-move rate (workstream review, 2026-10-07)
    if (t >= 0) return t >= 0.10;
  }
  return rel_value_loss(A, d, bv) >= thr;
}
// Personal odds by playouts of the simulated player the personal model was fitted on: the softmax player at
// temperature `key`, or (personal v3, "player human") the human move model at skill s = -ln(100 key) with structure
// skill min(s, 0.4), as build/rollout --human plays it.
static hm::Model human_model;
// plan_q / plan_e / plan_m: care in danger (personal v5, PersonalModel::plan_q): on a board with at most plan_e empty
// cells, with probability plan_q, the best depth-2 move that keeps the largest tile in its corner (plan_m 2; 1: the
// engine's move, 0: the 1-ply argmax), as build/messy's human policy plays it (:dq= :de= :dm=).
static map<int, double> personal_odds(const Engine& E, board_t b0, double key, bool human, double plan_q = 0,
                                      int plan_e = 2, int plan_m = 2) {
  int top = bb::max_rank(b0);
  double s_skill = human ? -std::log(100.0 * std::max(key, 1e-9)) : 0.0;
  vector<long> reach(20, 0);
  atomic<int> next{0};
  mutex m;
  auto in_corner = [](board_t x) {
    int r = bb::max_rank(x);
    return bb::cell(x, 0) == r || bb::cell(x, 3) == r || bb::cell(x, 12) == r || bb::cell(x, 15) == r;
  };
  auto work = [&]() {
    vector<long> loc(20, 0);
    unique_ptr<EngineThread> et;
    if (human && plan_q > 0) et.reset(new EngineThread(E));
    for (;;) {
      int k = next.fetch_add(1);
      if (k >= personal_n) break;
      bb::Rng rng(b0 * 31 + (uint64_t)k * 0x9E3779B97F4A7C15ULL + 7);
      board_t b = b0;
      int mx = top;
      hm::History hist;
      for (long step = 0; step < 200000 && mx < top + 4; step++) {
        int d = human ? hm::move(E, human_model, b, hist, s_skill, rng, std::min(s_skill, 0.4)) : soft_move(E, b, key, rng);
        if (d < 0) break;
        if (et && bb::count_empty(b) <= plan_e && rng.uniform() < plan_q) {  // care in danger
          if (plan_m == 1) {
            d = et->choose(b);
          } else {
            bool keep = in_corner(b);
            float mv[4];
            board_t vb = E.view(b);
            if (plan_m == 2) et->search->move_values(vb, 2, mv, E.params(vb));
            double bq = -1e300;
            int bk = -1;
            for (int pass = 0; pass < 2 && bk < 0; pass++)
              for (int dd = 0; dd < 4; dd++) {
                uint32_t rw;
                board_t a = bb::move(b, dd, rw);
                if (a == b || (pass == 0 && plan_m == 2 && keep && !in_corner(a))) continue;
                double q = plan_m == 2 ? (std::isnan(mv[dd]) ? -1e299 : (double)mv[dd]) : rw + (double)E.ev(E.view(a));
                if (q > bq) bq = q, bk = dd;
              }
            if (bk >= 0) d = bk;
          }
          if (d < 0) break;
        }
        hist.push(d);
        b = bb::spawn(bb::move(b, d), rng);
        mx = max(mx, bb::max_rank(b));
      }
      for (int r = top + 1; r <= mx && r < 20; r++) loc[r]++;
    }
    lock_guard<mutex> lk(m);
    for (int r = 0; r < 20; r++) reach[r] += loc[r];
  };
  vector<thread> th;
  for (int i = 0; i < personal_threads; i++) th.emplace_back(work);
  for (auto& t : th) t.join();
  map<int, double> out;
  int real_top = ex::display_rank[top];  // a new rank above the largest continues its real rank
  for (int r = top + 1; r <= min(top + 4, 17); r++) out[1 << (real_top + r - top)] = (double)reach[r] / personal_n;
  return out;
}
static map<int, double> cur_personal;
static PersonalModel pmodel;            // fast personal odds (weights/calib/personal.txt), else playouts
static bool personal_force_playouts = false;
static string personal_model = "weights/calib/personal.txt";  // --personal-model FILE
static bool want_odds_inputs = false;                           // --odds-inputs: JSON "odds_in" (calibration fits)
static const char* personal_method = "playouts";

// The human move model's view of a position (workstream hm2): find_prob = the probability that a player of the given
// skill plays each move (src/human.h, the fitted move model at that skill, with the player's recent moves); error
// risk = the expected share of the player's own chances of the next tile that the move they make costs (sum over the
// moves of find_prob x your_cost); hint = the risk reaches the phase's threshold (the personal model's "phint" line,
// chosen from the coach study's runs with human-model players): an app would show the engine's move before the player
// moves. Off without a skill; no risk or hint where the moves are not judged (block formation).
struct HumanView {
  bool on = false;
  double theta = NAN;
  double p[4] = {0, 0, 0, 0};
  double risk = NAN;
  bool hint = false;
};
static HumanView cur_human;
static const Engine* human_engine = nullptr;
static double player_theta(board_t b) {
  if (!std::isnan(human_theta)) return human_theta;
  if (personal_t > 0) return pmodel.theta_of_t(personal_t, skill_phase(b));  // a reviewed softmax t (pthetat lines)
  return NAN;
}
// The error risk of a position at the probabilities p (NaN where a move has no cost estimate).
static double error_risk(const Analysis& A, const double p[4]) {
  int bv = best_legal(A);
  if (bv < 0 || not_judged(A)) return NAN;
  double r = 0;
  for (int d = 0; d < 4; d++) {
    if (!A.mv[d].legal) continue;
    double yc = your_cost(A, d, bv);
    if (std::isnan(yc)) return NAN;
    r += p[d] * yc;
  }
  return r;
}
static bool hint_at(board_t b, double risk) {
  double thr = pmodel.hint[skill_phase(b)];
  return thr >= 0 && !std::isnan(risk) && risk >= thr;
}
// The engine's relative search losses for the human model's late hinge (tile sums >= 20480; nullptr below that or
// without a reference move).
static const double* late_search_losses(const Analysis& A, double out[4]) {
  int bv = best_legal(A);
  if (bv < 0 || real_tile_sum(A.board) < 20480) return nullptr;
  for (int d = 0; d < 4; d++) out[d] = A.mv[d].legal ? rel_value_loss(A, d, bv) : NAN;
  return out;
}
static HumanView human_view(const Analysis& A, double theta, const hm::History& hist) {
  HumanView h;
  if (std::isnan(theta) || !human_engine) return h;
  hm::Terms T;
  double sl[4];
  if (!hm::terms(*human_engine, human_model, A.board, hist, T, late_search_losses(A, sl))) return h;
  hm::probs_from_terms(human_model, T, theta, h.p);
  h.on = true, h.theta = theta;
  h.risk = error_risk(A, h.p);
  h.hint = hint_at(A.board, h.risk);
  return h;
}

// YOUR CHANCE (workstream yc, 2026-10-10): the player's own chance of the next milestone (2048, then each doubling of
// the largest tile) if they play on themselves - not the engine. The engine repairs almost anything early on, so its
// odds stay near 100% and its losses near 0 for moves that cost a human player a lot (a 2048 or 4096 out of its
// corner: about a fifth of a human's chance). Measured with the simulated human players of the personal odds
// (src/hplayer.h: the human move model + care in danger, keys mapped to real players' skill), learned by TD into small
// n-tuple networks (src/hvalue.h, weights/calib/chance.hv; scripts/yc_*.py, results/yc/REPORT.md). Up to a largest
// tile of 8192 (no simulated players get further).
//   q[d]  your chance after move d (the networks, at the player's skill: the key of their theta, else the in-between
//         default -0.5 the app assumes until a review measures them; never below that default: the simulated players
//         of novice-level keys never reach 2048 - real novices rarely do either - and a chance of 0 everywhere would
//         say nothing about their moves)
//   now   your chance from here: the player's own move probabilities (the same simulated player) x q
//   loss  the best move's q - q[d]; costly when it is 20% or more of the best q and at least 2 points (the warning)
static hv::Family chance_fam;
static string chance_model;  // --chance-model FILE (e.g. weights/calib/chance.hv; off by default since app v3)
static EngineThread* chance_thread = nullptr;  // its own search (the careful move on crowded boards): the analysis'
                                               // reasons keep their transposition table to themselves
static const double kDefaultTheta = -0.5;
static double chance_warn_rel = 0.20, chance_warn_abs = 0.02;
struct ChanceView {
  bool on = false;
  int target = 0;  // the milestone tile (real value)
  double key = NAN, theta = NAN;
  double q[4] = {NAN, NAN, NAN, NAN};
  double now = NAN, best = NAN;
  int best_move = -1;
};
static ChanceView cur_chance;
static ChanceView chance_view(EngineThread& T, const Analysis& A, double theta, const hm::History& hist) {
  ChanceView c;
  if (!chance_fam.ok() || not_judged(A) || hv::stage_of(A.board) < 0) return c;
  if (bb::max_rank(A.board) > 13 || ex::display_rank[bb::max_rank(A.board)] != bb::max_rank(A.board)) return c;
  int bvl = best_legal(A);
  if (bvl < 0) return c;
  c.theta = std::isnan(theta) ? kDefaultTheta : std::max(theta, kDefaultTheta);
  c.key = pmodel.has_theta_skill() ? pmodel.key_of_theta(c.theta, skill_phase(A.board)) : 0.016;
  if (!(c.key > 0)) c.key = 0.016;
  int M = hv::milestone_rank(A.board);
  c.target = 1 << M;
  for (int d = 0; d < 4; d++) {
    if (!A.mv[d].legal) continue;
    c.q[d] = hp::with_survival(chance_fam.v(A.mv[d].after, M, c.key), A.mv[d].after);
    if (c.best_move < 0 || c.q[d] > c.best) c.best = c.q[d], c.best_move = d;
  }
  hp::Player pl(c.key);
  double p[4];
  if (hp::probs(chance_thread ? *chance_thread : T, human_model, pl, A.board, hist, p)) {
    c.now = 0;
    for (int d = 0; d < 4; d++)
      if (A.mv[d].legal) c.now += p[d] * c.q[d];
  }
  c.on = true;
  return c;
}
static double chance_loss(const ChanceView& c, int d) { return c.on && !std::isnan(c.q[d]) ? std::max(0.0, c.best - c.q[d]) : NAN; }
static bool chance_costly(const ChanceView& c, int d) {
  double l = chance_loss(c, d);
  return !std::isnan(l) && l >= chance_warn_abs && l >= chance_warn_rel * c.best;
}

// THE COACH'S MOVE (workstream yc): what an app offers as "the coach's move" (and plays on autoplay). Up to a largest
// tile of 512 the engine's own move often looks arbitrary to people (it does not care where the biggest tile is: early
// on it repairs anything) while many moves are equally good, for the engine and for a human player's chance; there the
// coach plays the corner strategy - the move a strong human would make (the human move model at a high skill, with the
// player's recent moves: biggest tile in its corner, the edge line, three directions) among the moves the engine rates
// nearly equal (value loss below 3%, where a deeper search still picks them 5-16% of the time, and real loss below
// 0.5%). From 1024 on the engine's move (it keeps the corner itself there: 20 of 21 positions at 512, all at 1024-4096
// in the ground truth, results/yc/REPORT.md).
static double coach_theta = 0.5;
struct CoachPick {
  int move = -1;
  string why;  // "" when it is the engine's move for its own reasons
};
static CoachPick cur_coach;
static CoachPick coach_pick(const Analysis& A, const ChanceView& C, const hm::History& hist) {
  CoachPick c;
  int bv = best_legal(A);
  c.move = bv;
  if (bv < 0 || not_judged(A) || !human_engine) return c;
  if (ex::display_rank[bb::max_rank(A.board)] > 9) return c;  // 1024 and up: the engine's move
  double p[4];
  if (!hm::probs(*human_engine, human_model, A.board, hist, coach_theta, p)) return c;
  int pick = -1;
  for (int d = 0; d < 4; d++) {
    if (!A.mv[d].legal) continue;
    double rl = rel_real_loss(A, d, bv);
    if (std::isnan(rl) || rl > 0.005 || rel_value_loss(A, d, bv) >= 0.03) continue;
    if (C.on && chance_loss(C, d) > 0.01) continue;
    if (pick < 0 || p[d] > p[pick]) pick = d;
  }
  if (pick < 0 || pick == bv) return c;
  c.move = pick;
  board_t ap = A.mv[pick].after, ab = A.mv[bv].after;
  int top = bb::max_rank(A.board);
  string tile = to_string(1 << top);
  if (hp::max_in_corner(A.board) && hp::max_in_corner(ap) && !hp::max_in_corner(ab))
    c.why = "keeps your " + tile + " in its corner";
  else if (!hp::max_in_corner(A.board) && hp::max_in_corner(ap))
    c.why = "moves your " + tile + " into a corner";
  return c;
}

// MOVE GRADES (2026-10-10, the user's simplification; results/grades/REPORT.md): what an app shows for every move.
//   best          the coach's move, or one the engine cannot tell from it (value loss below 0.5%: a deeper search picks
//                 such moves about 1 time in 4)
//   good          fine, but the coach would play something else (value loss 0.5-5%)
//   questionable  the coach would never play it: value loss 5%+ (a deeper search picks such moves 2% of the time or
//                 less; 10%+ from 16384, where the engine's values overstate small losses), or it pulls a big tile
//                 (a quarter of the biggest) off the edge while a fine move keeps it there
//   blunder       an obvious, nameable mistake: the biggest tile leaves its corner, or the biggest or second-biggest
//                 tile is pulled off the edge, while a fine move (value loss below 5%, no danger) avoids it; 10%+ of the
//                 new tiles end the game while another move is at least 10 points safer; or the engine measures a big
//                 loss (real loss 10%+). Judged by the board, not by the engine's value: the engine repairs a 2048 out
//                 of its corner and calls it cheap, a person does not.
// The free stretch (largest tile up to 256): no corner or edge verdicts - early on such moves cost nothing, even for
// human-like players (results/yc/REPORT.md) - only danger and big losses.
// pick: how often the coach would play the move, from the engine's uncertainty: exp(-value loss / 0.015), normalized
// (fitted to which move a depth-5 search prefers on 2,400 real positions); the coach's move gets the top share.
// hint_cells: where the coach's move acts on the current board (its largest merge, else the plan's next cell);
// fault_cells: where a flagged move went wrong, on the board after it (the biggest tile's new cell and the corner it
// left, the cells where a new tile ends the game, the big tile pulled off the edge).
struct Grade {
  const char* grade = nullptr;  // nullptr: not graded (illegal, game over, not judged)
  string why;
  double pick = 0;
  vector<int> hint_cells, fault_cells;
};
static Grade cur_grades[4];
static const double kGoodRel = 0.005, kNeverRel = 0.05, kNeverRelLate = 0.10, kPickTau = 0.015;
struct MergeAt {
  int a, b, target, rank;  // the merging cells, the cell the new tile lands on, its rank
};
static vector<MergeAt> merges_of(board_t b, int d) {
  vector<MergeAt> out;
  for (int line = 0; line < 4; line++) {
    int cells[4];
    for (int i = 0; i < 4; i++)
      cells[i] = d == 0 ? i * 4 + line : d == 1 ? line * 4 + (3 - i) : d == 2 ? (3 - i) * 4 + line : line * 4 + i;
    int slot = 0, pend = -1, pend_cell = -1;
    for (int i = 0; i < 4; i++) {
      int v = bb::cell(b, cells[i]);
      if (!v) continue;
      if (pend == v) {
        out.push_back({pend_cell, cells[i], cells[slot], v + 1});
        slot++, pend = -1;
      } else {
        if (pend >= 0) slot++;
        pend = v, pend_cell = cells[i];
      }
    }
  }
  return out;
}
static bool on_edge(int c) { return c / 4 == 0 || c / 4 == 3 || c % 4 == 0 || c % 4 == 3; }
static bool is_corner(int c) { return c == 0 || c == 3 || c == 12 || c == 15; }
// cells holding big tiles (rank >= the biggest's - 2 and >= 64) away from every edge
static vector<int> big_off_edge_cells(board_t b) {
  vector<int> out;
  int big = std::max(6, bb::max_rank(b) - 2);
  for (int c = 0; c < 16; c++)
    if (bb::cell(b, c) >= big && !on_edge(c)) out.push_back(c);
  return out;
}
// empty cells of afterstate a where a new 2 ends the game
static vector<int> deadly_cells(board_t a) {
  vector<int> out;
  for (int c = 0; c < 16; c++) {
    if (bb::cell(a, c)) continue;
    board_t s = bb::set_cell(a, c, 1);
    bool any = false;
    for (int d = 0; d < 4 && !any; d++) any = bb::move(s, d) != s;
    if (!any) out.push_back(c);
  }
  return out;
}
static void grade_moves(const Analysis& A, int coach, Grade out[4]) {
  for (int d = 0; d < 4; d++) out[d] = Grade();
  int bv = best_legal(A);
  if (bv < 0 || not_judged(A)) return;
  board_t b = A.board;
  int top = bb::max_rank(b), top_real = ex::display_rank[top];
  bool free_stretch = top_real <= 8;
  double never = top_real >= 14 ? kNeverRelLate : kNeverRel;
  string tile = to_string(1L << top_real);
  bool corner_now = hp::max_in_corner(b);
  size_t edge_now = big_off_edge_cells(b).size();
  double rel[4], rl[4], death[4];
  bool corner_lost[4] = {}, edge_lost[4] = {};
  for (int d = 0; d < 4; d++) {
    if (!A.mv[d].legal) continue;
    board_t a = A.mv[d].after;
    rel[d] = rel_value_loss(A, d, bv);
    double r = rel_real_loss(A, d, bv);
    rl[d] = std::isnan(r) ? 0.0 : r;
    death[d] = hm::death_share(a);
    bool same_top = bb::max_rank(a) == top;  // a move that makes a new biggest tile is judged by its merge, not its corner
    corner_lost[d] = same_top && corner_now && !hp::max_in_corner(a);
    edge_lost[d] = same_top && big_off_edge_cells(a).size() > edge_now;
  }
  auto fine = [&](int f) { return A.mv[f].legal && rel[f] < never && death[f] < 0.02; };
  auto avoidable = [&](int d, const bool* defect) {
    for (int f = 0; f < 4; f++)
      if (f != d && fine(f) && !defect[f]) return true;
    return false;
  };
  double safest = 1.0;
  for (int f = 0; f < 4; f++)
    if (A.mv[f].legal) safest = std::min(safest, death[f]);
  vector<vector<ex::Reason>> rs;  // the engine's reasons, only when a flagged move needs one
  for (int d = 0; d < 4; d++) {
    if (!A.mv[d].legal) continue;
    Grade& g = out[d];
    board_t a = A.mv[d].after;
    if (d == coach) {
      g.grade = "best";
      continue;
    }
    vector<int> off = edge_lost[d] ? big_off_edge_cells(a) : vector<int>();
    int off_rank = 0;
    for (int c : off) off_rank = std::max(off_rank, (int)bb::cell(a, c));
    bool edge_avoidable = !free_stretch && edge_lost[d] && avoidable(d, edge_lost);
    if (death[d] >= 0.10 && safest <= death[d] - 0.10) {
      g.grade = "blunder";
      char buf[96];
      snprintf(buf, sizeof buf, "can end the game: %.0f%% of new tiles leave no move", 100 * death[d]);
      g.why = buf;
      g.fault_cells = deadly_cells(a);
    } else if (!free_stretch && corner_lost[d] && avoidable(d, corner_lost)) {
      g.grade = "blunder";
      g.why = "takes your " + tile + " out of its corner";
      for (int c = 0; c < 16; c++)
        if (bb::cell(a, c) == top && !is_corner(c)) g.fault_cells.push_back(c);
      for (int c : {0, 3, 12, 15})
        if (bb::cell(b, c) == top) g.fault_cells.push_back(c);
    } else if (edge_avoidable && off_rank >= top - 1) {
      g.grade = "blunder";
      g.why = "pulls your " + to_string(1L << ex::display_rank[off_rank]) + " off the edge";
      g.fault_cells = off;
    } else if (rl[d] >= 0.10) {
      g.grade = "blunder";
      if (rs.empty()) rs = reasons(A);
      g.why = rs[d].empty() ? "loses a lot: the coach would never play it" : rs[d][0].text;
    } else if (edge_avoidable) {
      g.grade = "questionable";
      g.why = "pulls your " + to_string(1L << ex::display_rank[off_rank]) + " off the edge";
      g.fault_cells = off;
    } else if (rel[d] >= never) {
      g.grade = "questionable";
      if (rs.empty()) rs = reasons(A);
      if (!rs[d].empty()) g.why = rs[d][0].text;
    } else {
      g.grade = rel[d] >= kGoodRel ? "good" : "best";
    }
  }
  // the coach's share of each move
  double w[4] = {}, tot = 0;
  int arg = -1;
  for (int d = 0; d < 4; d++)
    if (A.mv[d].legal) {
      tot += w[d] = std::exp(-rel[d] / kPickTau);
      if (arg < 0 || w[d] > w[arg]) arg = d;
    }
  if (coach >= 0 && arg >= 0 && coach != arg && A.mv[coach].legal) std::swap(w[coach], w[arg]);
  for (int d = 0; d < 4; d++)
    if (A.mv[d].legal) out[d].pick = w[d] / tot;
  // where the coach's move acts: its largest merge (the two tiles), else the plan's next cell
  if (coach >= 0 && A.mv[coach].legal) {
    vector<MergeAt> ms = merges_of(b, coach);
    const MergeAt* big = nullptr;
    for (auto& m : ms)
      if (!big || m.rank > big->rank) big = &m;
    if (big && big->rank >= 3) out[coach].hint_cells = {big->a, big->b};
    else {
      ex::Plan P = ex::plan_info(b);
      if (P.next_cell >= 0 && top_real >= 6) out[coach].hint_cells = {P.next_cell};
    }
  }
}

// One-paragraph headline: verdict on the position (odds vs the base rate at this stage), the best move with its main
// reason, and the move to avoid (estimated real loss >= 10%) with its main reason.
static string summary(const Analysis& A, const vector<vector<ex::Reason>>& rs) {
  int bv = best_legal(A);
  if (bv < 0) return "Game over: no move is possible.";
  string s;
  if (calib.ok()) {
    auto o = odds_of(A.board, A.mv[bv].value, A.mv[bv].after);
    std::vector<double> B;
    calib.hats(std::log2(std::max(real_tile_sum(A.board), 2.0)), B);
    auto base = calib.odds(real_max_tile(A.board), real_tile_sum(A.board), max(1.0, Calib::dot(B, calib.vbar)));
    // the target that says the most: the largest drop against the base rate if there is a clear one, else the
    // biggest tile with a real chance (5-95%)
    int pick = -1;
    double drop = 0.03;
    for (auto& kv : o) {
      double b = base.count(kv.first) ? base[kv.first] : kv.second;
      if (b - kv.second > drop) drop = b - kv.second, pick = kv.first;
    }
    if (pick < 0)
      for (auto& kv : o)
        if (kv.second >= 0.05 && kv.second <= 0.95) pick = kv.first;
    if (pick < 0 && !o.empty()) pick = o.rbegin()->first;
    for (auto& kv : o) {
      if (kv.first != pick) continue;
      double b = base.count(kv.first) ? base[kv.first] : kv.second;
      char buf[200];
      const char* verdict = kv.second >= b - 0.02 ? "about as good as a typical position at this stage"
                            : kv.second >= b - 0.10 ? "a bit worse than a typical position at this stage"
                                                    : "in trouble compared with a typical position at this stage";
      snprintf(buf, sizeof buf, "With best play from here, the %d tile comes %d%% of the time (%s). ", kv.first,
               (int)lround(100 * kv.second), verdict);
      s += buf;
      break;
    }
    // an unusual formation for the stage: the odds' error there is 2-3x larger (workstream anypos)
    if (!o.empty() && !not_judged(A) && odds_caveat(A.board, A.mv[bv].after))
      s += "Odds are less certain here: this formation is unusual for the stage. ";
  }
  if (not_judged(A)) {
    s += "Your biggest tiles sit in a 3x2 block in a corner (the block formation). The engine plays a different "
         "formation (a snake along an edge), so it does not judge moves here and the odds are rough; its suggestion: " +
         string(kDirName[bv]) + ".";
    return s;
  }
  s += string("Best move: ") + kDirName[bv];
  if (strcmp(A.source, "search") != 0 && A.mv[bv].table_p >= 0)  // an exact table decided: say so, with its chance
    s += string(" (exact ") + (strcmp(A.source, "block") == 0 ? "block" : "endgame") + " table: " +
         to_string((int)lround(100 * A.mv[bv].table_p)) + "% chance to build the tile your " +
         (strcmp(A.source, "block") == 0 ? "block" : "chain") + " needs next)";
  else if (!rs[bv].empty()) s += " (" + rs[bv][0].text + ")";
  s += ".";
  int worst = -1;
  double wl = 0;
  for (int d = 0; d < 4; d++)
    if (A.mv[d].legal && d != bv) {
      double rl = rel_real_loss(A, d, bv);
      if (rl >= 0.10 && rl > wl) wl = rl, worst = d;
    }
  if (worst >= 0) {
    s += string(" Avoid ") + kDirName[worst];
    if (!rs[worst].empty()) s += ": it " + rs[worst][0].text;
    s += ".";
  }
  return s;
}

static string to_json(const Analysis& A, Clock::time_point t0, int played, const vector<Risk>& rk) {
  int bv = best_legal(A);
  auto rs = reasons(A);
  string s = "{\"board\":" + board_tiles(A.board) + ",\"hex\":\"" + board_hex(A.board) + "\"";
  s += ",\"stage\":" + to_string(A.stage) + ",\"depth\":" + to_string(A.depth);
  s += ",\"engine_move\":" + string(A.engine_move >= 0 ? "\"" + string(kDirName[A.engine_move]) + "\"" : "null");
  s += ",\"source\":\"" + string(A.source) + "\"";
  if (A.table_state_p >= 0) s += ",\"table_p\":" + fmt(A.table_state_p, 4);
  if (block_position(A.board)) s += ",\"formation\":\"block\"";
  if (not_judged(A)) s += ",\"judged\":false";
  if (played >= 0) s += ",\"played\":\"" + string(kDirName[played]) + "\"";
  if (bv < 0) s += ",\"game_over\":true";
  if (bv >= 0 && calib.ok()) {
    string o = odds_json(A.board, A.mv[bv].value, A.mv[bv].after);
    if (!o.empty()) s += ",\"odds\":" + o;
    if (!o.empty() && odds_caveat(A.board, A.mv[bv].after)) s += ",\"odds_caveat\":true";
    if (want_odds_inputs) {  // the odds model's inputs, for calibration fits (scripts/fit_calib_real.py)
      double v = A.mv[bv].value, sv = survival(A.mv[bv].after, &v);
      s += ",\"odds_in\":{\"value\":" + fmt(v, 1) + ",\"survival\":" + fmt(sv, 4) + ",\"sum\":" +
           fmt(real_tile_sum(A.board), 0) + ",\"max\":" + to_string(real_max_tile(A.board)) +
           ",\"shape\":" + fmt(shape_shift(A.board, A.mv[bv].after), 4) + "}";
    }
    s += ",\"expected_future\":" + fmt(calib.future(tile_sum(A.board), A.mv[bv].value), 0);
  }
  if (cur_chance.on) {
    s += ",\"chance\":{\"target\":" + to_string(cur_chance.target) + ",\"now\":" + fmt(cur_chance.now, 4) +
         ",\"best\":" + fmt(cur_chance.best, 4) + ",\"skill\":" + fmt(cur_chance.theta, 3) + ",\"key\":" +
         fmt(cur_chance.key, 5) + "}";
  }
  if (cur_coach.move >= 0) {
    s += ",\"coach_move\":\"" + string(kDirName[cur_coach.move]) + "\"";
    if (!cur_coach.why.empty()) s += ",\"coach_why\":" + jstr(cur_coach.why);
  }
  s += ",\"plan\":" + jstr(plan_text(A));
  s += ",\"plan_info\":" + plan_json(A.board);
  s += ",\"summary\":" + jstr(summary(A, rs));
  s += ",\"moves\":[";
  bool first = true;
  for (int d = 0; d < 4; d++) {
    const MoveEval& m = A.mv[d];
    if (!m.legal) continue;
    s += first ? "{" : ",{";
    first = false;
    s += "\"move\":\"" + string(kDirName[d]) + "\",\"reward\":" + to_string(m.reward);
    // no loss for a move whose value beats the reference: a corner-breaking move, or (when an exact table decided)
    // a move the table rates worse than its pick ("p"); the value comparison is not trusted there
    double lossv = bv >= 0 && !(m.value > A.mv[bv].value) ? A.mv[bv].value - m.value : NAN;
    s += ",\"value\":" + fmt(m.value) + ",\"loss\":" + fmt(lossv);
    if (m.table_p >= 0) s += ",\"p\":" + fmt(m.table_p, 4);
    if (calib.ok()) {
      string o = odds_json(A.board, m.value, m.after);
      if (!o.empty()) s += ",\"odds\":" + o;
      if (calib.has_lossmap() && bv >= 0) {
        double rl = rel_real_loss(A, d, bv);
        s += ",\"real_loss\":" + fmt(rl, 4);
        // a player's own move in a review is judged by what players lose (at 16384+ far less than the engine's
        // continuation suggests, workstream cal7); also give the cost if the engine took over from there
        if (reason_only >= 0 && d == reason_only) {
          int saved = reason_only;
          reason_only = -1;
          double re = rel_real_loss(A, d, bv);
          reason_only = saved;
          if (!std::isnan(re) && !std::isnan(rl) && fabs(re - rl) > 1e-4) s += ",\"real_loss_engine\":" + fmt(re, 4);
        }
      }
    }
    if (bv >= 0 && !not_judged(A)) {
      // the coach study's advice: warn before this move; its cost to a human-like player's own chances
      double yc = your_cost(A, d, bv);
      // with your chance: warn where the move costs the player a fifth of their chance (and 2+ points), else the
      // engine-based rule of the coach study
      bool w = cur_grades[d].grade ? strcmp(cur_grades[d].grade, "blunder") == 0
                                   : cur_chance.on ? chance_costly(cur_chance, d) : warn_move(A, d, bv);
      s += ",\"warn\":" + string(w ? "true" : "false") + ",\"your_cost\":" + fmt(yc, 4);
      if (cur_chance.on && !std::isnan(cur_chance.q[d]))
        s += ",\"chance\":" + fmt(cur_chance.q[d], 4) + ",\"chance_loss\":" + fmt(chance_loss(cur_chance, d), 4);
      if (!cur_personal.empty() && !std::isnan(yc))  // the absolute drop in the personal odds of the next tile
        s += ",\"your_cost_abs\":" + fmt(yc * cur_personal.begin()->second, 4);
    }
    if (cur_human.on) s += ",\"find_prob\":" + fmt(cur_human.p[d], 4);  // a player of the given skill plays it
    if (cur_grades[d].grade) {
      const Grade& g = cur_grades[d];
      s += ",\"grade\":\"" + string(g.grade) + "\",\"pick\":" + fmt(g.pick, 4);
      if (!g.why.empty()) s += ",\"why\":" + jstr(g.why);
      auto cells = [&](const char* key, const vector<int>& v) {
        if (v.empty()) return;
        s += string(",\"") + key + "\":[";
        for (size_t i = 0; i < v.size(); i++) s += (i ? "," : "") + to_string(v[i]);
        s += "]";
      };
      cells("hint_cells", g.hint_cells);
      cells("fault_cells", g.fault_cells);
    }
    if (m.lock_skip) s += ",\"breaks_corner\":true";
    s += ",\"reasons\":[";
    for (size_t i = 0; i < rs[d].size(); i++)
      s += (i ? ",{" : "{") + string("\"code\":") + jstr(rs[d][i].code) + ",\"text\":" + jstr(rs[d][i].text) +
           (rs[d][i].share >= 0 ? ",\"share\":" + fmt(min(rs[d][i].share, 1.0), 2) : string("")) + "}";  // > 1: all of it
    s += "]";
    if (rk[d].on) {
      s += ",\"risk\":{\"bad_prob\":" + fmt(rk[d].bad_prob, 3) + ",\"worst_cell\":" + jstr(ex::cell_name(rk[d].worst_cell)) +
           ",\"worst_tile\":" + to_string(1 << rk[d].worst_rank) + ",\"worst_prob\":" + fmt(rk[d].worst_prob, 3) +
           ",\"worst_loss\":" + fmt(rk[d].worst_loss) + "}";
    }
    if (want_heat && heat_engine && bv >= 0) {
      float hm[16], hb[16];
      heat_engine->ev.attribute(heat_engine->view(m.after), hm);
      heat_engine->ev.attribute(heat_engine->view(A.mv[bv].after), hb);
      s += ",\"heat\":[";
      for (int c = 0; c < 16; c++) s += (c ? "," : "") + fmt(hm[c] - hb[c], 0);
      s += "]";
    }
    if (want_features) {
      ex::Features f = ex::features(m.after);
      ex::Chain c = ex::chain_of(m.after);
      s += ",\"features\":{\"corner\":" + to_string((int)f.corner) + ",\"chain\":" + to_string(f.chain_len) +
           ",\"chain_ranks\":" + to_string(f.chain_ranks) + ",\"collapse\":" + to_string(c.collapse) +
           ",\"empty\":" + to_string(f.empty) + ",\"merges\":" + to_string(f.merges) +
           ",\"trapped\":" + to_string(f.trapped) + ",\"center\":" + to_string(f.big_off_edge) +
           ",\"corner_dist\":" + to_string(f.corner_dist) + ",\"exposed\":" + to_string(f.exposed) +
           ",\"merge_rank\":" + to_string(ex::largest_merge(A.board, m.after)) + "}";
    }
    s += ",\"after\":\"" + board_hex(m.after) + "\"}";
  }
  s += "]";
  if (!cur_personal.empty()) {
    s += ",\"personal_odds\":{\"temperature\":" + fmt(personal_t, 4) + ",\"method\":\"" + personal_method + "\"";
    if (!pmodel.skillmap.empty() || !std::isnan(human_theta)) {  // the simulated player that plays like this skill
      double key = !std::isnan(human_theta) ? pmodel.key_of_theta(human_theta, skill_phase(A.board))
                                            : pmodel.soft_t(personal_t, skill_phase(A.board));
      if (pmodel.player == "human") s += ",\"human_skill\":" + fmt(-std::log(100.0 * std::max(key, 1e-9)), 3);
      else s += ",\"soft_temperature\":" + fmt(key, 4);
    }
    for (auto& kv : cur_personal) s += ",\"" + to_string(kv.first) + "\":" + fmt(kv.second, 3);
    s += "}";
  }
  if (cur_human.on) {
    s += ",\"player_skill\":" + fmt(cur_human.theta, 3);
    if (!std::isnan(cur_human.risk))
      s += ",\"error_risk\":" + fmt(cur_human.risk, 4) + ",\"hint\":" + (cur_human.hint ? "true" : "false");
  }
  if (!cur_line.empty()) {
    s += ",\"line\":[";
    for (size_t i = 0; i < cur_line.size(); i++)
      s += (i ? ",{" : "{") + string("\"move\":\"") + kDirName[cur_line[i].first] + "\",\"board\":\"" +
           board_hex(cur_line[i].second) + "\"}";
    s += "]";
  }
  double ms = 1000 * chrono::duration<double>(Clock::now() - t0).count();  // all the work, reasons included
  s += ",\"evals\":" + to_string(A.evals) + ",\"ms\":" + fmt(ms, 2) + "}";
  return s;
}

static void print_text(const Analysis& A, Clock::time_point t0, const vector<Risk>& rk);
static void print_line() {
  if (!cur_personal.empty()) {
    printf("personal odds (a player of skill temperature %.4f, %s):", personal_t, personal_method);
    for (auto& kv : cur_personal) printf("  %d: %.1f%%", kv.first, 100 * kv.second);
    printf("\n");
  }
  if (cur_line.empty()) return;
  printf("sample continuation:");
  for (auto& m : cur_line) printf(" %c", kDirChar[m.first]);
  printf("\n");
}
static void print_text(const Analysis& A, Clock::time_point t0, const vector<Risk>& rk) {
  print_board(stdout, A.board);
  int bv = best_legal(A);
  if (bv < 0) {
    printf("game over (no legal move)\n\n");
    return;
  }
  auto rs = reasons(A);
  string pl = plan_text(A);
  printf("summary: %s\n", summary(A, rs).c_str());
  if (!pl.empty()) printf("plan: %s\n", pl.c_str());
  printf("stage %d, depth %d, engine plays %s (%s", A.stage, A.depth,
         A.engine_move >= 0 ? kDirName[A.engine_move] : "-", A.source);
  if (A.table_state_p >= 0) printf(", table p %.3f", A.table_state_p);
  printf("), %ld evals, %.1f ms\n", A.evals, 1000 * chrono::duration<double>(Clock::now() - t0).count());
  if (calib.ok()) {
    printf("odds (engine plays on):");
    for (auto& t : odds_of(A.board, A.mv[bv].value, A.mv[bv].after))
      printf("  %d: %.1f%%", t.first, 100 * t.second);
    printf("   expected future points %.0f\n", calib.future(tile_sum(A.board), A.mv[bv].value));
  }
  if (cur_chance.on)
    printf("your chance of %d (a player of skill %.2f playing on): %.1f%% from here, %.1f%% with the best move for you\n",
           cur_chance.target, cur_chance.theta, 100 * cur_chance.now, 100 * cur_chance.best);
  if (cur_coach.move >= 0 && !cur_coach.why.empty())
    printf("the coach's move: %s (%s)\n", kDirName[cur_coach.move], cur_coach.why.c_str());
  int order[4], n = 0;
  for (int d = 0; d < 4; d++)
    if (A.mv[d].legal) order[n++] = d;
  sort(order, order + n, [&](int x, int y) { return A.mv[x].value > A.mv[y].value; });
  for (int i = 0; i < n; i++) {
    const MoveEval& m = A.mv[order[i]];
    if (m.value > A.mv[bv].value)
      printf("  %-5s value %10.0f  loss %9s", kDirName[order[i]], m.value, "n/a");  // see "breaks the corner"
    else
      printf("  %-5s value %10.0f  loss %9.0f", kDirName[order[i]], m.value, A.mv[bv].value - m.value);
    if (not_judged(A)) printf("  (not judged: block formation)");
    else {
      if (calib.has_lossmap()) printf("  (real ~%.1f%%", 100 * rel_real_loss(A, order[i], bv));
      double yc = your_cost(A, order[i], bv);
      if (calib.has_lossmap() && order[i] != bv) printf(", your chances ~%.1f%%", 100 * yc);
      if (calib.has_lossmap()) printf(")");
      if (warn_move(A, order[i], bv)) printf("  WARN");
    }
    if (m.table_p >= 0) printf("  p %.4f", m.table_p);
    if (m.lock_skip) printf("  (breaks the corner)");
    if (cur_chance.on && !std::isnan(cur_chance.q[order[i]]))
      printf("  [your chance %.1f%%%s]", 100 * cur_chance.q[order[i]], chance_costly(cur_chance, order[i]) ? ", costly" : "");
    if (cur_human.on) printf("  [played by %.0f%% of players at your level]", 100 * cur_human.p[order[i]]);
    printf("\n");
    for (auto& r : rs[order[i]]) printf("        %s %s\n", order[i] == bv ? "+" : "-", r.text.c_str());
    if (rk[order[i]].on)
      printf("        risk: %.0f%% of new tiles cost > 5%%; worst: a %d in the %s (%.1f%% chance, -%.0f)\n",
             100 * rk[order[i]].bad_prob, 1 << rk[order[i]].worst_rank, ex::cell_name(rk[order[i]].worst_cell).c_str(),
             100 * rk[order[i]].worst_prob, rk[order[i]].worst_loss);
  }
  if (cur_human.on && !std::isnan(cur_human.risk))
    printf("error risk at your level (skill %.2f): %.1f%% of your chances%s\n", cur_human.theta, 100 * cur_human.risk,
           cur_human.hint ? "  HINT: an app would show the engine's move here" : "");
  printf("\n");
}

// The most probable way from board a to board b in at most max_k moves (each followed by a random tile): the boards
// before each move and the moves. Empty if there is none (a frame of a video may skip moves, so b can be several moves
// after a). Paths are compared by the product of their new tiles' probabilities (0.9 for a 2, 0.1 for a 4), so the
// gap length that the tile sums suggest wins (a gap whose tile sum grew by 8 is far more likely four 2s than two 4s);
// the cell a tile lands on is not scored (any cell is equally likely, and the frames pin most of them down).
struct Step {
  board_t board;
  int move;
};
// Does move d from board a, followed by one new tile, give board b? (--review-moves: the move given with a frame)
static bool move_explains(board_t a, int d, board_t b) {
  board_t m = bb::move(a, d), diff = m ^ b;
  if (m == a || !diff) return false;
  int c = __builtin_ctzll(diff) / 4;
  if (diff >> (4 * c) >> 4) return false;
  return bb::cell(m, c) == 0 && (bb::cell(b, c) == 1 || bb::cell(b, c) == 2);
}
static vector<Step> infer_path(board_t a, board_t b, int max_k = 3) {
  struct Node {
    board_t s;
    double p;
    int parent, move;
  };
  vector<Node> nodes{{a, 1.0, -1, -1}};
  vector<int> frontier{0};
  int best = -1, best_move = -1;
  double best_p = 0;
  long target = (long)tile_sum(b);
  auto spawn_p = [](board_t m, board_t t, double* p) {  // t = m + one spawn?
    board_t diff = m ^ t;
    if (!diff) return false;
    int c = __builtin_ctzll(diff) / 4;
    if (diff >> (4 * c) >> 4) return false;
    if (bb::cell(m, c) != 0) return false;
    int v = bb::cell(t, c);
    if (v != 1 && v != 2) return false;
    *p = v == 1 ? 0.9 : 0.1;
    return true;
  };
  for (int k = 1; k <= max_k; k++) {
    vector<int> next;
    for (int id : frontier) {
      board_t s = nodes[id].s;
      long rest = target - (long)tile_sum(s);  // what the remaining spawns must add
      for (int d = 0; d < 4; d++) {
        board_t m = bb::move(s, d);
        if (m == s) continue;
        double p;
        if (rest <= 4 && spawn_p(m, b, &p) && nodes[id].p * p > best_p) best_p = nodes[id].p * p, best = id, best_move = d;
        if (k == max_k || rest < 4 || rest > 4L * (max_k - k + 1)) continue;  // no room for another move
        if (nodes[id].p * 0.9 * 0.9 <= best_p) continue;  // cannot beat the best path found
        uint64_t em = bb::empty_mask(m);
        for (uint64_t mm = em; mm; mm &= mm - 1) {
          uint64_t bit = mm & -mm;
          for (int r = 1; r <= 2; r++) {
            if (rest - (2L << (r - 1)) < 2) continue;
            board_t t = m | (bit * (board_t)r);
            nodes.push_back(Node{t, nodes[id].p * (r == 1 ? 0.9 : 0.1), id, d});
            next.push_back((int)nodes.size() - 1);
          }
        }
      }
    }
    frontier.swap(next);
    if (frontier.empty()) break;
  }
  vector<Step> path;
  if (best < 0) return path;
  path.push_back(Step{nodes[best].s, best_move});
  for (int id = best; nodes[id].parent >= 0; id = nodes[id].parent)
    path.push_back(Step{nodes[nodes[id].parent].s, nodes[id].move});
  reverse(path.begin(), path.end());
  return path;
}

// Invariants of the analysis library (analyze --selftest): returns the number of failures.
static int selftest(EngineThread& T, const Engine& E) {
  int fails = 0;
  auto check = [&](bool ok, const char* what) {
    printf("  %s %s\n", ok ? "ok  " : "FAIL", what);
    fails += !ok;
  };
  // 1. parsing: tile lists, hex, nonsense; the "0 0 0 2" ambiguity
  board_t b;
  check(parse_board("0 0 0 2 / 0 0 0 0 / 0 2 0 0 / 0 0 0 0", &b) && bb::cell(b, 3) == 1 && bb::cell(b, 9) == 1,
        "tile list parses (single-digit tiles are not hex)");
  check(parse_board("0001000001000000", &b) && bb::cell(b, 3) == 1, "16 hex digits parse");
  check(!parse_board("1 2 3", &b) && !parse_board("3 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0", &b), "non-boards are rejected");
  // 2. big tiles: 131072 and 65536 stay distinct (never clamped), real values are displayed
  check(parse_board("131072 65536 32768 16384 / 8192 4096 2048 1024 / 2 4 8 512 / 0 0 2 0", &b) &&
            bb::cell(b, 0) != bb::cell(b, 1) && display_tile(bb::cell(b, 0)) == 131072 && display_tile(bb::cell(b, 1)) == 65536,
        "65536+ boards map without clamping and show real tiles");
  for (int r = 0; r < 16; r++) g_display_rank[r] = r;
  // 3. move inference over skipped frames recovers a known 2-move path
  {
    bb::Rng rng(7);
    board_t a = bb::initial_board(rng), x = a;
    int n = 0;
    for (int d = 0; d < 4 && n < 2; d++) {
      board_t m = bb::move(x, d);
      if (m == x) continue;
      x = bb::spawn(m, rng), n++;
    }
    auto p = infer_path(a, x, 3);
    check(n == 2 && p.size() == 2 && bb::move(p[0].board, p[0].move) != p[0].board, "a 2-move gap is bridged");
  }
  // 4. attribution sums to the network value
  {
    parse_board("2 4 8 16 / 32 64 128 256 / 0 0 2 4 / 0 0 0 2", &b);
    float h[16], sum = 0;
    E.ev.attribute(b, h);
    for (float v : h) sum += v;
    check(fabs(sum - E.ev(b)) < 1e-3 * fabs(E.ev(b)) + 1, "per-cell attribution sums to the network value");
  }
  // 5. the analysis: legal moves only, the engine's move is legal, losses >= 0 for lock-allowed moves
  {
    parse_board("4 4 8 16 / 8 8 32 128 / 0 32 64 512 / 2 2 16 2048", &b);
    Analysis A = T.analyze(b);
    int bv = best_legal(A);
    bool ok = A.engine_move >= 0 && A.mv[A.engine_move].legal && bv >= 0;
    for (int d = 0; d < 4; d++)
      if (A.mv[d].legal && !A.mv[d].lock_skip) ok &= A.mv[bv].value - A.mv[d].value >= -1e-3;
    check(ok, "analysis: engine move legal, reference best among allowed moves");
    // a dead board has no move
    parse_board("2 4 16 2 / 8 32 64 4 / 16 128 512 8 / 4 2 256 16", &b);
    Analysis D = T.analyze(b);
    check(D.engine_move < 0 && best_legal(D) < 0, "a dead board reports no move");
  }
  // 6. odds: monotone in the target, survival-scaled odds never exceed the model's
  if (calib.ok()) {
    parse_board("2 4 16 2 / 8 32 64 4 / 16 128 512 8 / 4 2 256 0", &b);
    Analysis A = T.analyze(b);
    int bv = best_legal(A);
    auto o = odds_of(A.board, A.mv[bv].value, A.mv[bv].after);
    auto m = calib.odds(real_max_tile(b), real_tile_sum(b), A.mv[bv].value);
    bool mono = true, scaled = true;
    double prev = 1.0;
    for (auto& kv : o) mono &= kv.second <= prev + 1e-9, prev = kv.second, scaled &= kv.second <= m[kv.first] + 1e-9;
    check(mono && scaled && !o.empty(), "odds are non-increasing in the target and survival-scaled");
  }
  // 7. the block formation (3x2 corner block, real 16384+): no verdicts there without a deciding table; the same shape
  // with smaller tiles is judged normally
  {
    parse_board("2 1024 8192 32768 / 256 512 4096 2048 / 4 128 128 2 / 0 2 2 4", &b);
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    Analysis A = T.analyze(b);
    int bv = best_legal(A);
    bool none = bv >= 0 && block_position(b);
    for (int d = 0; d < 4; d++)
      if (A.mv[d].legal) none &= std::isnan(rel_real_loss(A, d, bv)) && std::isnan(your_cost(A, d, bv)) && !warn_move(A, d, bv);
    auto rs = reasons(A);
    none &= rs[bv].size() == 1 && rs[bv][0].code == "block";
    for (int d = 0; d < 4; d++) none &= d == bv || rs[d].empty();
    check(none || !E.btabs.empty(), "block formation at 32768: moves are not judged (no losses, warnings or verdicts)");
    parse_board("2 64 512 2048 / 16 32 256 128 / 4 8 8 2 / 0 2 2 4", &b);  // the same shape, largest tile 2048
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    Analysis S = T.analyze(b);
    int sb = best_legal(S);
    bool judged = sb >= 0 && !block_position(b);
    for (int d = 0; d < 4; d++)
      if (S.mv[d].legal) judged &= !std::isnan(rel_real_loss(S, d, sb)) && your_cost(S, d, sb) >= 0;
    check(judged, "the block shape with a 2048 is judged normally (the detector needs a real 16384+)");
  }
  // 8. warnings and your cost: none for the reference move; a move far worse than the threshold is warned about
  {
    parse_board("4 4 8 16 / 8 8 32 128 / 0 32 64 512 / 2 2 16 2048", &b);
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    Analysis A = T.analyze(b);
    int bv = best_legal(A);
    bool ok = bv >= 0 && !warn_move(A, bv, bv) && your_cost(A, bv, bv) == 0.0;
    for (int d = 0; d < 4; d++)
      if (A.mv[d].legal && d != bv) {
        double x = rel_value_loss(A, d, bv), yc = your_cost(A, d, bv);
        ok &= yc >= 0 && yc <= 1;
        if (strcmp(A.source, "search") == 0) ok &= warn_move(A, d, bv) == (x >= calib.warn[skill_phase(b)]);
      }
    check(ok, "warnings follow the phase threshold; your cost is in [0, 1] and 0 for the reference move");
  }
  // 9. the human move model's view (workstream hm2): the skill-free terms reproduce the model's probabilities; find_prob
  // sums to 1; the error risk is the find_prob-weighted your_cost and the hint follows the phase's threshold
  {
    parse_board("4 4 8 16 / 8 8 32 128 / 0 32 64 512 / 2 2 16 2048", &b);
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    hm::History hist;
    for (int d : {2, 1, 2, 2, 1, 3, 2, 1, 2, 1, 2}) hist.push(d);
    hm::Terms HT;
    hm::terms(E, human_model, b, hist, HT);
    double p1[4], p2[4], diff = 0;
    hm::probs(E, human_model, b, hist, 0.4, p1);
    hm::probs_from_terms(human_model, HT, 0.4, p2);
    for (int d = 0; d < 4; d++) diff = max(diff, fabs(p1[d] - p2[d]));
    check(diff < 1e-12, "the human model's skill-free terms reproduce its move probabilities");
    Analysis A = T.analyze(b);
    HumanView h = human_view(A, -0.2, hist);
    double sum = 0, risk = 0;
    int bv = best_legal(A);
    for (int d = 0; d < 4; d++)
      if (A.mv[d].legal) sum += h.p[d], risk += h.p[d] * your_cost(A, d, bv);
    check(h.on && fabs(sum - 1) < 1e-9 && fabs(risk - h.risk) < 1e-12 && h.risk >= 0 && h.risk <= 1 &&
              h.hint == (pmodel.hint[skill_phase(b)] >= 0 && h.risk >= pmodel.hint[skill_phase(b)]),
          "find_prob sums to 1, the error risk is the find_prob-weighted cost, the hint follows the threshold");
    // a late position (tile sum >= 20480): the late hinge on the search losses
    parse_board("16384 4096 2048 1024 / 8 16 512 256 / 4 2 32 64 / 0 2 4 0", &b);
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    Analysis L = T.analyze(b);
    double sl[4];
    HumanView hl = human_view(L, -0.2, hm::History());
    double lsum = 0;
    for (int d = 0; d < 4; d++)
      if (L.mv[d].legal) lsum += hl.p[d];
    check(hl.on && late_search_losses(L, sl) != nullptr && fabs(lsum - 1) < 1e-9,
          "late positions use the human model's search-loss hinge; find_prob still sums to 1");
  }
  // 10. the review's skill fit recovers the skill of moves drawn from the human model itself
  {
    const double theta0 = 0.0;
    bb::Rng rng(777);
    vector<hm::Terms> ts;
    vector<int> mv;
    board_t g = bb::spawn(bb::spawn(0, rng), rng);
    hm::History hist;
    while (mv.size() < 600) {
      hm::Terms HT;
      if (hm::terms(E, human_model, g, hist, HT) < 1) {  // game over: a new game
        g = bb::spawn(bb::spawn(0, rng), rng), hist.clear();
        continue;
      }
      double p[4];
      hm::probs_from_terms(human_model, HT, theta0, p);
      double u = rng.uniform(), acc = 0;
      int d = -1;
      for (int k = 0; k < 4; k++)
        if (p[k] > 0 && (acc += p[k]) > u && d < 0) d = k;
      if (d < 0)
        for (int k = 0; k < 4; k++)
          if (HT.legal[k]) d = k;
      if (HT.n >= 2) ts.push_back(HT), mv.push_back(d);
      hist.push(d);
      g = bb::spawn(bb::move(g, d), rng);
    }
    double best_th = 0, best_ll = -1e300;
    for (int k = 0; k <= 240; k++) {
      double th = -3.0 + 0.025 * k, ll = 0;
      for (size_t i = 0; i < ts.size(); i++) ll += hm::loglik(human_model, ts[i], mv[i], th);
      if (ll > best_ll) best_ll = ll, best_th = th;
    }
    check(fabs(best_th - theta0) <= 0.25, "the skill fit recovers the skill of moves drawn from the human model");
  }
  // 11. the plan (workstream plan, 2026-10-07): the 32768-next-to-a-16384-corner shape gets the pair plan, not "get your
  // biggest tile into a corner"; boards with lowered big tiles cut the chain at real 16x gaps (a 65536 with a 4096 next
  // to it keeps a chain of its own next to the corner) and never claim a wrong completion; a merge the best move does
  // not make is not an instruction
  {
    parse_board("2048 4096 32768 16384 / 8 16 32 128 / 2 8 16 2 / 0 0 2 2", &b);
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    ex::Plan P = ex::plan_info(b);
    string t = ex::plan(b);
    check(P.type == "pair" && P.corner_cell == 3 && P.pair_cell == 2 && t.find("Your 32768 sits next to the top-right corner, where your 16384 is") == 0,
          "plan: the biggest tile next to a corner holding half of it is the pair shape");
    parse_board("128 512 4096 65536 / 64 16 8 4 / 16 8 4 0 / 2 0 0 0", &b);
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    P = ex::plan_info(b);
    t = ex::plan(b);
    check(P.type == "single" && P.start == 1 && t.find("Keep the 65536 in the top-right corner; your chain 4096-512") == 0,
          "plan: a 65536 with a 4096 next to it plans the chain next to the corner (real-rank cut)");
    parse_board("128 512 8192 65536 / 64 64 0 0 / 8 0 2 0 / 4 0 0 0", &b);
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    t = ex::plan(b);
    check(t.find("below the 65536") == string::npos, "plan: no completion claim from compressed ranks");
    parse_board("2 4 64 64 / 2 8 64 128 / 0 4 16 256 / 0 0 4 512", &b);
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    Analysis A = T.analyze(b);
    int bv = best_legal(A);
    t = plan_text(A);
    bool merges = bv >= 0 && bb::cell(bb::move(b, bv), 3) == 7;  // the 64s merge onto the chain's end (top-right)
    check(bv >= 0 && (merges ? t.find("Merge the 64") != string::npos : t.find("can merge into it (the engine prefers") != string::npos),
          "plan: a named merge is an instruction only when the best move makes it");
  }
  // 12. move grades (app v3): the user's sanity cases. With a 2048 in its corner, a move that takes it out is a
  // blunder (the engine calls it cheap); pulling the 2048 next to a 4096 off the edge is one too; a move that lets most
  // new tiles end the game is one; in the free stretch (largest tile up to 256) leaving the corner is not flagged; the
  // coach's move is best and gets the top share; warnings are the blunders
  {
    hm::History hist;
    auto graded = [&](const char* bs) {
      parse_board(bs, &b);
      for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
      Analysis A = T.analyze(b);
      CoachPick cp = coach_pick(A, ChanceView(), hist);
      grade_moves(A, cp.move, cur_grades);
      return make_pair(A, cp.move);
    };
    auto g_of = [&](int d) { return string(cur_grades[d].grade ? cur_grades[d].grade : "-"); };
    auto [A1, c1] = graded("2048 1024 512 256 / 8 32 64 128 / 2 4 2 0 / 0 0 0 0");
    bool ok1 = g_of(2) == "blunder" && cur_grades[2].why.find("out of its corner") != string::npos && g_of(c1) == "best";
    double top_pick = 0;
    for (int d = 0; d < 4; d++) top_pick = max(top_pick, cur_grades[d].pick);
    ok1 &= c1 >= 0 && cur_grades[c1].pick == top_pick;
    check(ok1, "grades: a 2048 out of its corner is a blunder; the coach's move is best with the top share");
    graded("4096 2048 1024 512 / 16 64 128 256 / 4 8 2 0 / 2 0 0 0");
    check(g_of(2) == "blunder" && cur_grades[2].why.find("2048 off the edge") != string::npos,
          "grades: pulling the 2048 next to a 4096 off the edge is a blunder");
    graded("2 4 16 2 / 8 32 64 4 / 16 128 512 8 / 4 2 256 0");
    check(g_of(1) == "blunder" && cur_grades[1].why.find("end the game") != string::npos && !cur_grades[1].fault_cells.empty(),
          "grades: a move after which most new tiles end the game is a blunder, with the deadly cells");
    graded("128 64 16 4 / 8 4 2 0 / 2 0 0 0 / 0 0 0 0");
    check(g_of(2) != "blunder" && g_of(2) != "questionable", "grades: leaving the corner in the free stretch is not flagged");
  }
  // 13. your chance (workstream yc): chances in [0, 1], the best move for the player loses nothing and the chance from
  // here is at most that; in the opening the coach keeps the biggest tile in its corner where the engine's move would
  // take it out (the engine plays down here); from 1024 on the coach's move is the engine's
  if (chance_fam.ok()) {
    hm::History hist;
    parse_board("128 64 16 4 / 8 4 2 0 / 2 0 0 0 / 0 0 0 0", &b);
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    Analysis A = T.analyze(b);
    ChanceView c = chance_view(T, A, kDefaultTheta, hist);
    bool ok = c.on && c.target == 2048 && c.best_move >= 0 && c.now <= c.best + 1e-12 && c.now >= 0;
    for (int d = 0; d < 4; d++)
      if (A.mv[d].legal) ok &= c.q[d] >= 0 && c.q[d] <= 1 && chance_loss(c, d) >= 0 && (d != c.best_move || chance_loss(c, d) == 0);
    check(ok, "your chance: in [0, 1], 0 loss for the best move for the player, the chance from here at most the best");
    CoachPick cp = coach_pick(A, c, hist);
    check(cp.move >= 0 && hp::max_in_corner(bb::move(b, cp.move)),
          "the coach's opening move keeps the biggest tile in its corner");
    parse_board("4 4 8 16 / 8 8 32 128 / 0 32 64 512 / 2 2 16 2048", &b);
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    Analysis L = T.analyze(b);
    ChanceView cl = chance_view(T, L, kDefaultTheta, hist);
    check(coach_pick(L, cl, hist).move == best_legal(L) && cl.on && cl.target == 4096,
          "from 1024 on the coach's move is the engine's; with a 2048 the milestone is 4096");
  }
  for (int r = 0; r < 16; r++) ex::display_rank[r] = r, g_display_rank[r] = r;
  printf("%d failure(s)\n", fails);
  return fails;
}

int main(int argc, char** argv) {
  Engine E;
  E.cfg.preset_best(".", true);
  bool json = false, use_stdin = false, no_calib = false, want_selftest = false;
  bool stdin_player = false;  // --stdin-player: per-line skill= and hist= options in --stdin mode (app/server)
  bool review_moves = false;  // --review-moves: a review frame may name the move played from it (app/server)
  int depth = 0, max_gap = 3;
  string review;
  vector<string> boards;
  for (int i = 1; i < argc; i++) {
    string a = argv[i];
    if (a == "--preset") {
      if (i + 1 >= argc) return 1;
      string p = argv[++i];
      E.cfg = EngineConfig();
      E.cfg.preset_best(".", p == "best");
    } else if ((a == "--depth" || a == "--analysis-depth") && i + 1 < argc) {
      depth = stoi(argv[++i]);  // the analysis depth (the engine's own depth flags: --stage-depth, --min-depth, ...)
    } else if (E.cfg.parse(i, argc, argv)) {
    } else if (a == "--json") json = true;
    else if (a == "--stdin") use_stdin = true, json = true;
    else if (a == "--stdin-player") stdin_player = true;
    else if (a == "--review-moves") review_moves = true;
    else if (a == "--review" && i + 1 < argc) review = argv[++i];
    else if (a == "--risk" && i + 1 < argc) risk_depth = stoi(argv[++i]);
    else if (a == "--features") want_features = true;
    else if (a == "--no-calib") no_calib = true;
    else if (a == "--heat") want_heat = true;
    else if (a == "--selftest") want_selftest = true;
    else if (a == "--max-gap" && i + 1 < argc) max_gap = stoi(argv[++i]);
    else if (a == "--line" && i + 1 < argc) line_len = stoi(argv[++i]);
    else if (a == "--personal" && i + 1 < argc) personal_t = stod(argv[++i]);
    else if (a == "--skill" && i + 1 < argc) human_theta = stod(argv[++i]);  // human-model skill (a review's "skill")
    else if (a == "--personal-model" && i + 1 < argc) personal_model = argv[++i];
    else if (a == "--odds-inputs") want_odds_inputs = true;
    else if (a == "--chance-model" && i + 1 < argc) chance_model = argv[++i];
    else if (a == "--no-chance") chance_model.clear();
    else if (a == "--personal-playouts" && i + 1 < argc) personal_n = stoi(argv[++i]), personal_force_playouts = true;
    else if (a == "--threads" && i + 1 < argc) personal_threads = stoi(argv[++i]);
    else if (a == "--calib" && i + 1 < argc) {
      if (!calib.load(argv[++i])) {
        fprintf(stderr, "cannot read calibration model %s\n", argv[i]);
        return 1;
      }
    }
    else if (a.size() > 2 && a[0] == '-' && a[1] == '-') {
      fprintf(stderr, "unknown option %s\n", a.c_str());
      return 1;
    } else boards.push_back(a);
  }
  if (!E.load(!json)) return 1;
  if (!calib.ok() && !no_calib) calib.load("weights/calib/model.txt");  // the default odds model, if present
  pmodel.load(personal_model);                             // fast personal odds, if present
  if (!chance_model.empty() && !chance_fam.load(chance_model))
    fprintf(stderr, "cannot read the chance model %s\n", chance_model.c_str());
  EngineThread T(E);
  EngineThread TC(E);
  chance_thread = &TC;
  reason_thread = &T;
  survive_thread = &T;
  heat_engine = &E;
  human_engine = &E;
  if (want_selftest) return selftest(T, E) ? 1 : 0;
  if (getenv("CHECK_ATTRIBUTION")) {  // the cells must sum to the network value
    board_t tb;
    parse_board("2 4 8 16 / 32 64 128 256 / 0 0 2 4 / 0 0 0 2", &tb);
    float h[16], sum = 0;
    E.ev.attribute(tb, h);
    for (float x : h) sum += x;
    fprintf(stderr, "attribution check: sum of cells %.1f, network value %.1f\n", sum, E.ev(tb));
  }
  auto run = [&](board_t b, int played) {
    for (int r = 0; r < 16; r++) ex::display_rank[r] = g_display_rank[r];
    auto t0 = Clock::now();
    Analysis A = T.analyze(b, depth);
    auto rk = risks(T, A);
    cur_line = line_len > 0 ? continuation(T, b) : vector<pair<int, board_t>>();
    cur_personal.clear();
    // the personal model's key: from the human-model skill (--skill, through the theta map) or from a reviewed
    // softmax skill T (--personal, through the skill map)
    double pkey = !std::isnan(human_theta) ? (pmodel.has_theta_skill() ? pmodel.key_of_theta(human_theta, skill_phase(b)) : NAN)
                  : personal_t > 0 ? pmodel.soft_t(personal_t, skill_phase(b)) : NAN;
    if (pkey > 0) {
      if (pmodel.ok() && !personal_force_playouts) {
        int bvp = best_legal(A);
        if (bvp >= 0) {
          cur_personal = pmodel.odds(pkey, real_max_tile(b), real_tile_sum(b), A.mv[bvp].value);
          double sv = survival(A.mv[bvp].after);  // the next tile's danger, as for the engine's odds
          for (auto& kv : cur_personal) kv.second *= sv;
        }
        personal_method = "model";
      } else {
        cur_personal = personal_odds(E, b, pkey, pmodel.player == "human", pmodel.plan_q(pkey), pmodel.plan_e,
                                     pmodel.plan_m);
        personal_method = "playouts";
      }
    }
    cur_human = human_view(A, player_theta(b), cur_hist);
    cur_chance = chance_view(T, A, player_theta(b), cur_hist);
    cur_coach = coach_pick(A, cur_chance, cur_hist);
    grade_moves(A, cur_coach.move, cur_grades);
    if (json) printf("%s\n", to_json(A, t0, played, rk).c_str());
    else print_text(A, t0, rk), print_line();
    fflush(stdout);
    return A;
  };
  if (!review.empty()) {
    FILE* f = fopen(review.c_str(), "r");
    if (!f) {
      fprintf(stderr, "cannot read %s\n", review.c_str());
      return 1;
    }
    vector<board_t> seq;
    vector<array<int, 16>> seq_map;  // each frame's display map (games that reach 65536 change it along the way)
    vector<int> seq_move;            // --review-moves: the move played from each frame ("BOARD U"), -1 if none given
    char line[4096];
    while (fgets(line, sizeof line, f)) {
      int given = -1;
      if (review_moves) {  // a last token U/R/D/L after the board names the move played from it
        size_t e = strlen(line);
        while (e > 0 && isspace((unsigned char)line[e - 1])) e--;
        if (e >= 2 && isspace((unsigned char)line[e - 2]))
          for (int d = 0; d < 4; d++)
            if (line[e - 1] == kDirChar[d]) given = d, line[e - 1] = ' ';
      }
      board_t b;
      if (parse_board(line, &b)) {
        seq.push_back(b);
        array<int, 16> m;
        for (int r = 0; r < 16; r++) m[r] = g_display_rank[r];
        seq_map.push_back(m);
        seq_move.push_back(given);
      }
    }
    fclose(f);
    long n = 0, match = 0, unknown = 0, gaps = 0, same = 0, good = 0;
    long unjudged = 0, warnings = 0, own_mistakes = 0;  // moves in block positions; warnings an app would have shown
    double loss_sum = 0, rel_sum = 0;
    long inacc = 0, mistakes = 0, blunders = 0;
    vector<Step> steps;  // the game as (board before the move, move)
    vector<size_t> step_frame;  // the frame each step starts from (for its display map)
    for (size_t i = 0; i + 1 < seq.size(); i++) {
      if (seq[i] == seq[i + 1]) {
        same++;
        continue;
      }
      vector<Step> p;
      if (seq_move[i] >= 0 && move_explains(seq[i], seq_move[i], seq[i + 1]))
        p.push_back(Step{seq[i], seq_move[i]});  // the given move: an app knows it (0.7% of frame pairs are ambiguous)
      else p = infer_path(seq[i], seq[i + 1], max_gap);
      if (p.empty()) {
        unknown++;
        if (getenv("DEBUG_INFER")) fprintf(stderr, "no path: %s -> %s\n", board_hex(seq[i]).c_str(), board_hex(seq[i + 1]).c_str());
        continue;
      }
      gaps += p.size() > 1;
      steps.insert(steps.end(), p.begin(), p.end());
      step_frame.insert(step_frame.end(), p.size(), i);
    }
    // per move: relative losses of the legal moves and the played one, for the skill estimate
    struct Choice {
      double rel[4];
      bool legal[4];
      int played;
      int phase;  // 0: largest tile <= 512, 1: 1024-2048, 2: 4096-8192, 3: >= 16384 (real tiles)
    };
    // per phase: moves, mistakes (est. real loss 3-10%), blunders (>= 10%), log of chances kept
    struct PhaseStat {
      long moves = 0, mistakes = 0, blunders = 0;
      double kept_log = 0;
    } phase_stat[4];
    auto phase_of = [](board_t b) {
      int r = ex::display_rank[bb::max_rank(b)];
      return r <= 9 ? 0 : r <= 11 ? 1 : r <= 13 ? 2 : 3;
    };
    vector<Choice> choices;
    struct KeyMoment {
      long ply;
      board_t board;
      int played, engine;
      double real_loss, value_loss;
      string why;
      double your_cost;  // share of the player's own chances of the next milestone (your_cost())
    };
    vector<KeyMoment> key;
    // per judged move, for the human-model skill and the hint statistics (workstream hm2): the human move model's
    // terms of the position (with the player's previous moves), the played and reference moves, each move's your_cost
    struct HStep {
      hm::Terms terms;
      int played, bv, phase;
      long ply;
      double yc[4];
      board_t board;
    };
    vector<HStep> hsteps;
    cur_hist.clear();
    double acc_sum = 0, kept_log = 0;  // kept: product over moves of (1 - estimated real loss)
    long lost_at = -1;                 // first move at which the position was already lost
    long decisive = -1;                // the move with the largest estimated real loss before that
    double decisive_loss = 0;
    for (size_t i = 0; i < steps.size(); i++) {
      int d = steps[i].move;
      for (int r = 0; r < 16; r++) g_display_rank[r] = seq_map[step_frame[i]][r];
      reason_only = d;  // reviews explain the move that was played
      Analysis A = run(steps[i].board, d);
      hm::Terms HT;  // the human model's view of the position, with the player's moves so far
      double hsl[4];
      int hn = hm::terms(E, human_model, steps[i].board, cur_hist, HT, late_search_losses(A, hsl));
      cur_hist.push(d);
      if (not_judged(A)) {  // block formation: the engine does not judge these moves (no skill, accuracy, classes)
        unjudged++;
        continue;
      }
      if (hn >= 2 && HT.legal[d]) {
        HStep h;
        h.terms = HT, h.played = d, h.bv = best_legal(A), h.phase = phase_of(steps[i].board), h.ply = (long)i + 1;
        h.board = steps[i].board;
        bool ok = h.bv >= 0;
        for (int k = 0; k < 4; k++) {
          h.yc[k] = A.mv[k].legal ? your_cost(A, k, h.bv) : 0.0;
          ok &= !std::isnan(h.yc[k]);
        }
        if (ok) hsteps.push_back(h);
      }
      {
        int bvi = best_legal(A);
        Choice c;
        c.played = d;
        c.phase = phase_of(steps[i].board);
        int nl = 0;
        for (int k = 0; k < 4; k++) {
          c.legal[k] = A.mv[k].legal;
          nl += c.legal[k];
          c.rel[k] = c.legal[k] ? rel_value_loss(A, k, bvi) : 0;  // floored normalization, as in the batch review
        }
        if (nl >= 2) choices.push_back(c);
      }
      int bv = best_legal(A);
      double loss = A.mv[bv].value - A.mv[d].value;
      // classes by the estimated REAL loss (value losses of 1-10% are mostly repaired; see the judge study)
      double rel = rel_real_loss(A, d, bv);
      n++;
      match += d == A.engine_move;
      loss_sum += loss;
      rel_sum += rel;
      acc_sum += 103.1668 * exp(-0.04354 * 100 * rel) - 3.1669;  // lichess's accuracy formula on the real loss in %
      // the position counts as lost once even the best move's value is below 5% of a typical position's value at
      // this stage: "chances kept" stops there (moves in a lost position say little about the player)
      bool healthy = true;  // the position before the move still looked normal (best value >= half a typical one)
      if (calib.ok()) {
        std::vector<double> Bh;
        calib.hats(std::log2(std::max((double)tile_sum(steps[i].board), 2.0)), Bh);
        double typical = Calib::dot(Bh, calib.vbar);
        if (lost_at < 0 && typical > 0 && A.mv[bv].value < 0.05 * typical) lost_at = (long)i + 1;
        healthy = typical <= 0 || A.mv[bv].value >= 0.5 * typical;
      }
      if (lost_at < 0) kept_log += log(max(1e-6, 1.0 - rel));
      // the decisive moment: the largest loss made from a healthy position (moves in a dire position say little)
      if (healthy && rel > decisive_loss) decisive_loss = rel, decisive = (long)i + 1;
      {
        PhaseStat& ps = phase_stat[phase_of(steps[i].board)];
        ps.moves++, ps.mistakes += rel >= 0.03 && rel < 0.10, ps.blunders += rel >= 0.10;
        if (lost_at < 0) ps.kept_log += log(max(1e-6, 1.0 - rel));
      }
      {
        auto rs = reasons(A);
        string why;
        for (size_t k = 0; k < rs[d].size(); k++) why += (k ? "; " : "") + rs[d][k].text;
        double yc = your_cost(A, d, bv);
        key.push_back(KeyMoment{(long)i + 1, steps[i].board, d, A.engine_move, rel, loss, why, yc});
        own_mistakes += yc >= 0.03;
      }
      warnings += warn_move(A, d, bv);
      good += rel < 0.01;  // the best move or one as good as makes no real difference
      inacc += rel >= 0.01 && rel < 0.03;
      mistakes += rel >= 0.03 && rel < 0.10;
      blunders += rel >= 0.10;
      if (!json && rel >= 0.03)
        printf(">>> move %zu: played %s, engine %s, value loss %.0f, est. real loss %.1f%% (%s)\n\n", i + 1,
               kDirName[d], kDirName[A.engine_move], loss, 100 * rel, rel >= 0.10 ? "blunder" : "mistake");
    }
    // skill: the temperature t under which the played moves are most likely when move m is chosen with probability
    // ~ exp(-relative loss(m) / t) (the soft:t player of build/messy); smaller t = stronger play
    double best_t = 0, best_ll = -1e300;
    for (double t = 0.0003; t <= 1.0; t *= 1.1) {
      double ll = 0;
      for (auto& c : choices) {
        double z = 0;
        for (int k = 0; k < 4; k++)
          if (c.legal[k]) z += exp(-c.rel[k] / t);
        ll += -c.rel[c.played] / t - log(z);
      }
      if (ll > best_ll) best_ll = ll, best_t = t;
    }
    if (!choices.empty())
      fprintf(json ? stderr : stdout, "skill estimate: temperature %.4f over %zu choices (mean log-likelihood %.3f)\n",
              best_t, choices.size(), best_ll / choices.size());
    // skill per phase, with a bootstrap 80% interval (resampling the phase's moves)
    double phase_t[4] = {0, 0, 0, 0}, phase_lo[4] = {0, 0, 0, 0}, phase_hi[4] = {0, 0, 0, 0};
    for (int ph = 0; ph < 4; ph++) {
      vector<const Choice*> cs;
      for (auto& c : choices)
        if (c.phase == ph) cs.push_back(&c);
      if (cs.size() < 50) continue;  // too few choices for a skill estimate
      // log-likelihood terms per choice on the t grid, computed once
      vector<double> grid;
      for (double t = 0.0003; t <= 1.0; t *= 1.1) grid.push_back(t);
      vector<vector<double>> term(cs.size(), vector<double>(grid.size()));
      for (size_t i = 0; i < cs.size(); i++)
        for (size_t g = 0; g < grid.size(); g++) {
          double z = 0;
          for (int k = 0; k < 4; k++)
            if (cs[i]->legal[k]) z += exp(-cs[i]->rel[k] / grid[g]);
          term[i][g] = -cs[i]->rel[cs[i]->played] / grid[g] - log(z);
        }
      auto fit = [&](const vector<size_t>& idx) {
        size_t bg = 0;
        double bll = -1e300;
        for (size_t g = 0; g < grid.size(); g++) {
          double ll = 0;
          for (size_t i : idx) ll += term[i][g];
          if (ll > bll) bll = ll, bg = g;
        }
        return grid[bg];
      };
      vector<size_t> all(cs.size());
      for (size_t i = 0; i < all.size(); i++) all[i] = i;
      phase_t[ph] = fit(all);
      bb::Rng brng(12345 + ph);
      vector<double> boots;
      for (int r = 0; r < 60; r++) {
        vector<size_t> idx(cs.size());
        for (auto& x : idx) x = brng.below((uint32_t)cs.size());
        boots.push_back(fit(idx));
      }
      sort(boots.begin(), boots.end());
      phase_lo[ph] = boots[boots.size() / 10], phase_hi[ph] = boots[boots.size() * 9 / 10];
    }
    // human-model skill (workstream hm2): the theta under which the human move model (src/human.h) makes the played
    // moves most likely - over the game and per phase (>= 50 moves) with a bootstrap 80% interval, as the skill t
    // above; it is the "skill" of the personal model's theta map (--skill THETA analyses at that skill)
    vector<double> tgrid;
    for (int g = 0; g <= 240; g++) tgrid.push_back(-3.0 + 0.025 * g);
    vector<vector<float>> hterm(hsteps.size(), vector<float>(tgrid.size()));
    for (size_t i = 0; i < hsteps.size(); i++)
      for (size_t g = 0; g < tgrid.size(); g++)
        hterm[i][g] = (float)hm::loglik(human_model, hsteps[i].terms, hsteps[i].played, tgrid[g]);
    auto fit_theta = [&](const vector<size_t>& idx) {
      size_t bg = 0;
      double bll = -1e300;
      for (size_t g = 0; g < tgrid.size(); g++) {
        double ll = 0;
        for (size_t i : idx) ll += hterm[i][g];
        if (ll > bll) bll = ll, bg = g;
      }
      return tgrid[bg];
    };
    double theta_all = NAN, phase_th[4] = {NAN, NAN, NAN, NAN}, phase_th_lo[4] = {NAN, NAN, NAN, NAN},
           phase_th_hi[4] = {NAN, NAN, NAN, NAN};
    // the skill below 16384 only: from 16384 on the human move model over-predicts big errors (3.1 vs 1.5 per 100
    // moves; hm2) and the engine misjudges strong players' late moves, so an expert's late-game skill reads lower
    // than a novice's - not comparable, not reported
    {
      vector<size_t> all;
      for (size_t i = 0; i < hsteps.size(); i++)
        if (hsteps[i].phase < 3) all.push_back(i);
      if (all.size() >= 50) theta_all = fit_theta(all);
    }
    for (int ph = 0; ph < 3; ph++) {
      vector<size_t> idx;
      for (size_t i = 0; i < hsteps.size(); i++)
        if (hsteps[i].phase == ph) idx.push_back(i);
      if (idx.size() < 50) continue;
      phase_th[ph] = fit_theta(idx);
      bb::Rng brng(54321 + ph);
      vector<double> boots;
      for (int r = 0; r < 60; r++) {
        vector<size_t> bi(idx.size());
        for (auto& x : bi) x = idx[brng.below((uint32_t)idx.size())];
        boots.push_back(fit_theta(bi));
      }
      sort(boots.begin(), boots.end());
      phase_th_lo[ph] = boots[boots.size() / 10], phase_th_hi[ph] = boots[boots.size() * 9 / 10];
    }
    // at the fitted skill (the phase's, else the game's): hints an app would have shown before the move (error risk
    // at or above the phase's threshold), and the hard moments - risky positions (error risk >= 1%) whose best move
    // players at this level find less than 20% of the time, habits aside - and how many of them the player found
    long hints = 0, hard = 0, hard_found = 0;
    vector<long> hard_plies;
    for (auto& h : hsteps) {
      double th = !std::isnan(phase_th[h.phase]) ? phase_th[h.phase] : theta_all;
      if (std::isnan(th) || h.phase >= 3) continue;  // no skill reading (16384+, or too few moves below it)
      double hp[4];
      hm::probs_from_terms(human_model, h.terms, th, hp);
      double risk = 0;
      for (int k = 0; k < 4; k++)
        if (h.terms.legal[k]) risk += hp[k] * h.yc[k];
      hints += hint_at(h.board, risk);
      // difficulty is a property of the position: judged without the player's direction habits (a best move in the
      // direction a player never presses is a habit to break, not a hard move)
      hm::Terms nh = h.terms;
      for (int k = 0; k < 4; k++) nh.h[k] = 0;
      double hp0[4], risk0 = 0;
      hm::probs_from_terms(human_model, nh, th, hp0);
      for (int k = 0; k < 4; k++)
        if (nh.legal[k]) risk0 += hp0[k] * h.yc[k];
      if (risk0 >= 0.01 && hp0[h.bv] < 0.2) {
        hard++;
        if (h.played == h.bv) {
          hard_found++;
          if (hard_plies.size() < 5) hard_plies.push_back(h.ply);
        }
      }
    }
    static const char* phase_name[4] = {"up to 512", "1024-2048", "4096-8192", "16384+"};
    // key moments are ranked by the larger of the move's real loss (the engine playing on) and its cost to the
    // player's own chances of the next milestone (your_cost: human-like players repair less than the engine)
    auto weight = [&](const KeyMoment& k) { return max(k.real_loss, k.your_cost); };
    sort(key.begin(), key.end(), [&](const KeyMoment& a, const KeyMoment& b) { return weight(a) > weight(b); });
    if (key.size() > 5) key.resize(5);
    // moments below 3% (the larger of real loss and your cost) are at the noise level of the truth measurements
    // (workstream review: 60% of non-expert key moments were that small; 3-10%: a third cost >= 10% of the player's
    // chances, above 10%: 82%) - a review without such moments says so rather than listing noise
    key.erase(remove_if(key.begin(), key.end(), [&](const KeyMoment& k) { return weight(k) < 0.03; }), key.end());
    double accuracy = n ? min(100.0, max(0.0, acc_sum / n)) : 0;
    if (json) {
      string o = "{\"review\":{\"moves\":" + to_string(n) + ",\"match\":" + fmt(n ? (double)match / n : 0, 4) +
                 ",\"good\":" + fmt(n ? (double)good / n : 0, 4) +
                 ",\"accuracy\":" + fmt(accuracy, 1) + ",\"kept\":" + fmt(exp(kept_log), 4) +
                 (lost_at >= 0 ? ",\"lost_at\":" + to_string(lost_at) : string("")) +
                 (decisive >= 0 && decisive_loss >= 0.03 ? ",\"decisive_move\":" + to_string(decisive) +
                                                              ",\"decisive_loss\":" + fmt(decisive_loss, 4)
                                                        : string("")) +
                 ",\"mean_real_loss\":" + fmt(n ? rel_sum / n : 0, 5) +
                 ",\"inaccuracies\":" + to_string(inacc) + ",\"mistakes\":" + to_string(mistakes) +
                 ",\"blunders\":" + to_string(blunders) + ",\"skill_t\":" + (choices.empty() ? string("null") : fmt(best_t, 5)) +
                 ",\"mistakes_at_your_level\":" + to_string(own_mistakes) + ",\"warnings\":" + to_string(warnings) +
                 ",\"warnings_per_100\":" + fmt(n ? 100.0 * warnings / n : 0, 2) +
                 (!std::isnan(theta_all) ? ",\"skill\":" + fmt(theta_all, 3) : string("")) +
                 ",\"hints\":" + to_string(hints) + ",\"hints_per_100\":" + fmt(n ? 100.0 * hints / n : 0, 2) +
                 ",\"hard_moments\":" + to_string(hard) + ",\"hard_found\":" + to_string(hard_found) +
                 ",\"hard_found_plies\":[" + [&] {
                   string t;
                   for (size_t k = 0; k < hard_plies.size(); k++) t += (k ? "," : "") + to_string(hard_plies[k]);
                   return t;
                 }() + "]" +
                 (unjudged ? ",\"not_judged\":" + to_string(unjudged) : string("")) +
                 ",\"unknown_frames\":" + to_string(unknown) + ",\"bridged\":" + to_string(gaps) + ",\"phases\":[";
      bool firstp = true;
      for (int ph = 0; ph < 4; ph++) {
        const PhaseStat& q = phase_stat[ph];
        if (!q.moves) continue;
        o += (firstp ? "{" : ",{") + string("\"phase\":\"") + phase_name[ph] + "\",\"moves\":" + to_string(q.moves) +
             ",\"mistakes\":" + to_string(q.mistakes) + ",\"blunders\":" + to_string(q.blunders) +
             ",\"kept\":" + fmt(exp(q.kept_log), 4) +
             (phase_t[ph] > 0 ? ",\"skill_t\":" + fmt(phase_t[ph], 5) + ",\"skill_t_80\":[" + fmt(phase_lo[ph], 5) + "," +
                                    fmt(phase_hi[ph], 5) + "]"
                              : "") +
             (!std::isnan(phase_th[ph]) ? ",\"skill\":" + fmt(phase_th[ph], 3) + ",\"skill_80\":[" +
                                             fmt(phase_th_lo[ph], 3) + "," + fmt(phase_th_hi[ph], 3) + "]"
                                       : "") + "}";
        firstp = false;
      }
      o += "],\"key_moments\":[";
      for (size_t k = 0; k < key.size(); k++)
        o += (k ? ",{" : "{") + string("\"ply\":") + to_string(key[k].ply) + ",\"board\":\"" + board_hex(key[k].board) +
             "\",\"played\":\"" + kDirName[key[k].played] + "\",\"engine\":\"" +
             (key[k].engine >= 0 ? kDirName[key[k].engine] : "-") + "\",\"real_loss\":" + fmt(key[k].real_loss, 4) +
             ",\"your_cost\":" + fmt(key[k].your_cost, 4) +
             ",\"why\":" + jstr(key[k].why) + "}";
      o += "]}}";
      printf("%s\n", o.c_str());
    } else {
      printf("accuracy %.1f%%, chances kept %.1f%% (product over the moves of 1 - estimated real loss: the share of the "
             "engine-continuation chances the moves preserved%s)\n", accuracy, 100 * exp(kept_log),
             lost_at >= 0 ? (", until the position was lost at move " + to_string(lost_at)).c_str() : "");
      if (decisive >= 0 && decisive_loss >= 0.03)
        printf("decisive moment: move %ld (est. real loss %.1f%%: the largest loss from a still-healthy position)\n",
               decisive, 100 * decisive_loss);
      for (int ph = 0; ph < 4; ph++) {
        const PhaseStat& q = phase_stat[ph];
        if (!q.moves) continue;
        printf("  phase %-9s: %5ld moves, %3ld mistakes, %3ld blunders, chances kept %5.1f%%", phase_name[ph], q.moves,
               q.mistakes, q.blunders, 100 * exp(q.kept_log));
        if (phase_t[ph] > 0) printf(", skill t %.4f (80%%: %.4f-%.4f)", phase_t[ph], phase_lo[ph], phase_hi[ph]);
        if (!std::isnan(phase_th[ph])) printf(", skill %.2f (80%%: %.2f to %.2f)", phase_th[ph], phase_th_lo[ph], phase_th_hi[ph]);
        printf("\n");
      }
      for (auto& k : key)
        if (weight(k) >= 0.01) {
          char lvl[80] = "";
          snprintf(lvl, sizeof lvl, " (your own chances ~%.1f%%)", 100 * k.your_cost);
          printf("key moment: move %ld, played %s (engine %s), est. real loss %.1f%%%s%s%s\n", k.ply, kDirName[k.played],
                 k.engine >= 0 ? kDirName[k.engine] : "-", 100 * k.real_loss, lvl, k.why.empty() ? "" : ": ", k.why.c_str());
        }
      printf("mistakes at your level (moves costing >= 3%% of your own chances of the next tile): %ld; warnings an app "
             "would have shown: %ld (%.1f per 100 moves)\n", own_mistakes, warnings, n ? 100.0 * warnings / n : 0.0);
      if (unjudged)
        printf("not judged: %ld moves in the block formation (the engine plays a different formation)\n", unjudged);
      if (!std::isnan(theta_all))
        printf("skill %.2f (human move model; higher = stronger); hints an app would have shown before the move: %ld (%.1f "
               "per 100 moves); hard moments (best move found by < 20%% of players at your level): %ld, found %ld\n",
               theta_all, hints, n ? 100.0 * hints / n : 0.0, hard, hard_found);
    }
    fprintf(json ? stderr : stdout,
            "review: %ld moves (%ld frame pairs not understood, %ld bridged over skipped moves, %ld repeated frames), "
            "engine move played %.1f%%, best or good moves (est. real loss < 1%%) %.1f%%, mean value loss %.0f points, "
            "mean est. real loss %.2f%%, inaccuracies (1-3%%) %ld, "
            "mistakes (3-10%%) %ld, blunders (>10%%) %ld\n",
            n, unknown, gaps, same, 100.0 * match / max(1L, n), 100.0 * good / max(1L, n), loss_sum / max(1L, n),
            100 * rel_sum / max(1L, n), inacc,
            mistakes, blunders);
    return 0;
  }
  if (use_stdin) {
    // each line: a board, optionally preceded by per-request options and '|': "depth=4 risk=1 line=10 | 2 4 0 ..."
    string line;
    const int depth0 = depth, risk0 = risk_depth, line0 = line_len;
    // with --stdin-player (app/server), a line may also carry the player: "skill=-0.5 hist=LDDRL | BOARD" - the skill
    // on the human move model's scale (as --skill, for this line only) and the player's recent moves, oldest first
    // (the human model's history, as reviews fill it; the last hm::History::kLen count). Without the flag, both keys
    // are ignored as before.
    const double theta0 = human_theta;
    while (getline(cin, line)) {
      depth = depth0, risk_depth = risk0, line_len = line0;
      human_theta = theta0;
      string hist_moves;
      int played = -1;  // "played=U": the move the player made (echoed in the JSON, for batch reviews)
      size_t bar = line.find('|');
      if (bar != string::npos) {
        istringstream opts(line.substr(0, bar));
        string kv;
        while (opts >> kv) {
          size_t eq = kv.find('=');
          if (eq == string::npos) continue;
          string k = kv.substr(0, eq);
          int v = atoi(kv.c_str() + eq + 1);
          if (k == "played") {
            const char* mv = kv.c_str() + eq + 1;
            for (int d = 0; d < 4; d++)
              if (*mv == kDirChar[d] || *mv == kDirChar[d] + 32) played = d;
          } else if (k == "depth") depth = min(max(v, 0), 6);  // depth 7-8 on an open board takes minutes
          else if (k == "risk") risk_depth = min(max(v, 0), 3);
          else if (k == "line") line_len = min(max(v, 0), 200);
          else if (stdin_player && k == "skill") {
            double t = atof(kv.c_str() + eq + 1);
            if (std::isfinite(t)) human_theta = min(max(t, -3.0), 3.0);  // the human model's skill grid
          } else if (stdin_player && k == "hist") hist_moves = kv.substr(eq + 1);
        }
        line = line.substr(bar + 1);
      }
      board_t b;
      if (!parse_board(line, &b)) {
        printf("{\"error\":\"not a board\"}\n");
        fflush(stdout);
        continue;
      }
      T.reset_search();  // requests are independent: same answer, same cost, whatever came before
      cur_hist.clear();
      for (char c : hist_moves)
        for (int d = 0; d < 4; d++)
          if (c == kDirChar[d] || c == kDirChar[d] + 32) cur_hist.push(d);
      run(b, played);
    }
    return 0;
  }
  for (auto& s : boards) {
    board_t b;
    if (!parse_board(s, &b)) {
      fprintf(stderr, "not a board: %s\n", s.c_str());
      continue;
    }
    T.reset_search();
    cur_hist.clear();
    run(b, -1);
  }
  return 0;
}
