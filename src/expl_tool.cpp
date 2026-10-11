// Counterfactual faithfulness of the analysis' reasons (workstream expl, 2026-10-07).
//
// For a position, a worse move d, the reference move bv and one of the reasons analyze gave for d, the afterstate of d
// is edited to remove exactly the stated defect (e.g. "moves your biggest tile out of its corner": the biggest tile is
// swapped back into the corner it keeps after bv) and re-evaluated. The share of d's loss against bv that the edit
// recovers says how much of the loss the reason explains. A placebo applies the same kind of edit somewhere unrelated
// (the same tile to a random cell, the same filling at random empty cells, ...): the baseline a faithful reason must
// beat. Values: afterstate value = mean over the spawns of the best move value at depth --eval-depth (default 2) on the
// engine's view board (as EngineThread::spawns), the same for every board compared.
//
// input lines:  ID HEX D BV CODE      (HEX: 16 rank digits, cell 0 first, as analyze's "hex"; D, BV: 0-3 = up right down
//                                      left; CODE: a reason code, risk split into risk_dead / risk_bad)
//               ID HEX D BV probe     the loss's location: the single-cell restorations from bv's afterstate (cell c of
//                                      d's afterstate set to bv's) ranked by the share they recover (exploration)
// output (TSV): id code L0 gain placebo ok note
//   L0 = value(bv) - value(d) incl. rewards; gain = value(edited d) - value(d); placebo = mean gain of 4 placebo edits;
//   ok = 0 when the edit cannot be built (note says why) or the reason is not testable by an edit (later, shape)
// usage: expl_tool [engine flags, --preset best|best-notables] [--eval-depth K] [--rollouts K --horizon H]
//                  [--threads N] < in > out
// (with --rollouts, output: id code L0r gain_r se_L0 se_gain ok note: mean playout loss of the move and mean gain of
// the edit, with their paired standard errors)
#include <algorithm>
#include <atomic>
#include <functional>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "engine.h"
#include "explain.h"
#include "expl.h"

using namespace std;

static Engine E;
static int DV = 2;

struct Line {
  string id, code;
  board_t b = 0;
  int d = -1, bv = -1;
};

struct Worker {
  EngineThread T;
  explicit Worker(const Engine& e) : T(e) {}
  vector<EngineThread::Spawn> spawns(board_t a) { return T.spawns(a, DV); }
  double aval(board_t a) {
    double v = 0;
    for (auto& s : spawns(a)) v += s.prob * s.value;
    return v;
  }
};

using namespace xp;

// --rollouts K --horizon H: the outcome check - K playouts of the engine (common random numbers) from the reference
// afterstate, the move's afterstate and the edited afterstate, H moves each plus the network value at the horizon
static int RK = 0, RH = 300;
static double playout(Worker& W, board_t after, uint64_t seed) {
  W.T.reset_search();
  bb::Rng rng(seed);
  board_t last = after;
  double total = 0;
  bool dead = false;
  for (int step = 0; step < RH; step++) {
    board_t s = bb::spawn(last, rng);
    int d = W.T.choose(s);
    if (d < 0) {
      dead = true;
      break;
    }
    uint32_t r;
    last = bb::move(s, d, r);
    total += r;
  }
  return total + (dead ? 0.0 : (double)E.ev(E.view(last)));
}

static string process(Worker& W, const Line& L) {
  char buf[512];
  uint32_t rb = 0, rm = 0;
  board_t ab = bb::move(L.b, L.bv, rb), am = bb::move(L.b, L.d, rm);
  if (ab == L.b || am == L.b) return L.id + "\t" + L.code + "\t0\t0\t0\t0\tillegal move";
  if (RK > 0) {  // outcome check of the edit
    bb::Rng rng0(std::hash<string>()(L.id + L.code) | 1);
    board_t e;
    if (!xp::fix(L.code, L.b, ab, am, rng0, &e)) return L.id + "\t" + L.code + "\tnan\tnan\tnan\tnan\t0\tno edit";
    double sl = 0, sl2 = 0, sg = 0, sg2 = 0;
    uint64_t base = std::hash<string>()(L.id) * 0x9E3779B97F4A7C15ULL;
    for (int k = 0; k < RK; k++) {
      uint64_t seed = base + (uint64_t)k * 7919;
      double vb = rb + playout(W, ab, seed), vm = rm + playout(W, am, seed), ve = rm + playout(W, e, seed);
      sl += vb - vm, sl2 += (vb - vm) * (vb - vm), sg += ve - vm, sg2 += (ve - vm) * (ve - vm);
    }
    double ml = sl / RK, mg = sg / RK;
    double sel = sqrt(max(0.0, sl2 / RK - ml * ml) / RK), seg = sqrt(max(0.0, sg2 / RK - mg * mg) / RK);
    snprintf(buf, sizeof buf, "%s\t%s\t%.1f\t%.1f\t%.1f\t%.1f\t1\trollouts", L.id.c_str(), L.code.c_str(), ml, mg, sel, seg);
    return buf;
  }
  double vb = rb + W.aval(ab), vm = rm + W.aval(am), L0 = vb - vm;
  bb::Rng rng(std::hash<string>()(L.id + L.code) | 1);
  if (L.code == "later" || L.code == "shape" || L.code == "table" || L.code == "block") {
    snprintf(buf, sizeof buf, "%s\t%s\t%.1f\t0\t0\t0\tnot testable by an edit", L.id.c_str(), L.code.c_str(), L0);
    return buf;
  }
  if (L.code == "probe") {  // single-cell restorations from bv's afterstate, the 3 best
    vector<pair<double, int>> g;
    for (int c = 0; c < 16; c++)
      if (bb::cell(am, c) != bb::cell(ab, c)) g.push_back({rm + W.aval(bb::set_cell(am, c, bb::cell(ab, c))) - vm, c});
    sort(g.rbegin(), g.rend());
    string s = L.id + "\tprobe\t" + to_string(L0) + "\t";
    for (size_t i = 0; i < g.size() && i < 3; i++)
      s += to_string(g[i].second) + ":" + to_string(g[i].first) + (i + 1 < min<size_t>(3, g.size()) ? "," : "");
    return s + "\t0\t1\tcells";
  }
  if (L.code == "risk_dead" || L.code == "risk_bad") {
    // the move made only as risky as the reference: the mass of the deadly (or clearly bad) next tiles reduced to the
    // reference's share, the rest renormalized; placebo: the same reweighting of a random set of spawns
    auto sm = W.spawns(am), sb = W.spawns(ab);
    double mm = 0, mb_ = 0;
    for (auto& s : sm) mm += s.prob * s.value;
    for (auto& s : sb) mb_ += s.prob * s.value;
    bool dead = L.code == "risk_dead";
    auto bad = [&](const EngineThread::Spawn& s, double mean) {
      return dead ? s.value <= 0 : s.value < mean - 0.05 * fabs(mean);
    };
    double pm = 0, pb = 0;
    for (auto& s : sm) pm += bad(s, mm) ? s.prob : 0;
    for (auto& s : sb) pb += bad(s, mb_) ? s.prob : 0;
    if (pm <= pb || pm >= 0.999) {
      snprintf(buf, sizeof buf, "%s\t%s\t%.1f\t0\t0\t0\tno excess risk at this depth", L.id.c_str(), L.code.c_str(), L0);
      return buf;
    }
    auto reweighted = [&](const vector<char>& sel, double share) {
      double ps = 0;
      for (size_t i = 0; i < sm.size(); i++) ps += sel[i] ? sm[i].prob : 0;
      if (ps <= 0 || ps >= 1) return mm;
      double ks = share / ps, kr = (1 - share) / (1 - ps), v = 0;
      for (size_t i = 0; i < sm.size(); i++) v += sm[i].prob * (sel[i] ? ks : kr) * sm[i].value;
      return v;
    };
    vector<char> sel(sm.size());
    int nsel = 0;
    for (size_t i = 0; i < sm.size(); i++) sel[i] = bad(sm[i], mm), nsel += sel[i];
    double gain = reweighted(sel, pb) - mm, pg = 0;
    for (int k = 0; k < 4; k++) {  // placebo: as many random spawns, their mass reduced by the same factor
      vector<char> rs(sm.size(), 0);
      for (int j = 0; j < nsel; j++) rs[rng.next() % sm.size()] = 1;
      double ps = 0;
      for (size_t i = 0; i < sm.size(); i++) ps += rs[i] ? sm[i].prob : 0;
      pg += reweighted(rs, ps * pb / pm) - mm;
    }
    snprintf(buf, sizeof buf, "%s\t%s\t%.1f\t%.1f\t%.1f\t1\tmass %.3f->%.3f", L.id.c_str(), L.code.c_str(), L0, gain,
             pg / 4, pm, pb);
    return buf;
  }
  if (L.code == "area") {
    int a = worst_area(E, ab, am);
    if (a < 0) {
      snprintf(buf, sizeof buf, "%s\tarea\t%.1f\t0\t0\t0\tno area", L.id.c_str(), L0);
      return buf;
    }
    double gain = rm + W.aval(copy_area(am, ab, a)) - vm, pg = 0;
    int n = 0;
    for (int k = 0; k < 4; k++) {
      int o = rng.next() % 9;
      if (o == a) continue;
      pg += rm + W.aval(copy_area(am, ab, o)) - vm, n++;
    }
    snprintf(buf, sizeof buf, "%s\tarea\t%.1f\t%.1f\t%.1f\t1\tarea %d", L.id.c_str(), L0, gain, n ? pg / n : 0.0, a);
    return buf;
  }
  Edit ed{L.b, ab, am, rng, "", {}};
  board_t out = am;
  bool ok = false;
  const string& c = L.code;
  double pg = 0;
  int np = 0;
  for (int k = 0; k < 4; k++) {  // 4 placebo draws (the edit itself is deterministic)
    board_t o = am, p = am;
    bool okk = c == "corner" ? ed.corner(&o, &p) : c == "chain" ? ed.chain(&o, &p) : c == "chain_len" ? ed.chain_len(&o, &p)
             : c == "missed_merge" ? ed.missed_merge(&o, &p) : c == "danger" ? ed.danger(&o, &p) : c == "edge" ? ed.edge(&o, &p)
             : c == "trapped" ? ed.trapped(&o, &p) : c == "center" ? ed.center(&o, &p)
             : c == "toward_corner" ? ed.toward_corner(&o, &p) : c == "exposed" ? ed.exposed(&o, &p)
             : c == "space" ? ed.space(&o, &p) : (ed.note = "unknown code", false);
    if (!okk) break;
    ok = true, out = o;
    if (p != am) pg += rm + W.aval(p) - vm, np++;
  }
  if (!ok) {
    snprintf(buf, sizeof buf, "%s\t%s\t%.1f\t0\t0\t0\t%s", L.id.c_str(), c.c_str(), L0, ed.note.c_str());
    return buf;
  }
  double gain = rm + W.aval(out) - vm;
  // the locus test: the cells the reason is about restored from the best move's afterstate (as they are there);
  // placebo: as many other differing cells restored
  vector<int> loc;
  for (int k : ed.touched)
    if (bb::cell(am, k) != bb::cell(ab, k) && find(loc.begin(), loc.end(), k) == loc.end()) loc.push_back(k);
  double rg = NAN, rp = NAN;
  if (!loc.empty()) {
    board_t x = am;
    for (int k : loc) x = bb::set_cell(x, k, bb::cell(ab, k));
    rg = rm + W.aval(x) - vm;
    vector<int> other;
    for (int k = 0; k < 16; k++)
      if (bb::cell(am, k) != bb::cell(ab, k) && find(loc.begin(), loc.end(), k) == loc.end()) other.push_back(k);
    if (!other.empty()) {
      double sum = 0;
      for (int t = 0; t < 4; t++) {
        for (size_t i = other.size(); i > 1; i--) swap(other[i - 1], other[rng.next() % i]);
        board_t y = am;
        for (size_t i = 0; i < min(loc.size(), other.size()); i++) y = bb::set_cell(y, other[i], bb::cell(ab, other[i]));
        sum += rm + W.aval(y) - vm;
      }
      rp = sum / 4;
    }
  }
  snprintf(buf, sizeof buf, "%s\t%s\t%.1f\t%.1f\t%.1f\t1\t%s\t%.1f\t%.1f\t%d", L.id.c_str(), c.c_str(), L0, gain,
           np ? pg / np : 0.0, np ? (ed.note.empty() ? "-" : ed.note.c_str()) : "no placebo", rg, rp, (int)loc.size());
  return buf;
}

int main(int argc, char** argv) {
  int threads = 8;
  E.cfg.preset_best(".", true);
  for (int i = 1; i < argc; i++) {
    string a = argv[i];
    if (a == "--preset" && i + 1 < argc) {
      string p = argv[++i];
      E.cfg = EngineConfig();
      E.cfg.preset_best(".", p == "best");
    } else if (a == "--eval-depth" && i + 1 < argc) {  // (before the engine flags: they have their own --depth)
      DV = stoi(argv[++i]);
    } else if (a == "--rollouts" && i + 1 < argc) {
      RK = stoi(argv[++i]);
    } else if (a == "--horizon" && i + 1 < argc) {
      RH = stoi(argv[++i]);
    } else if (E.cfg.parse(i, argc, argv)) {
    } else if (a == "--threads" && i + 1 < argc) threads = stoi(argv[++i]);
    else {
      fprintf(stderr, "unknown option %s\n", a.c_str());
      return 1;
    }
  }
  vector<Line> lines;
  string s;
  while (getline(cin, s)) {
    istringstream in(s);
    Line L;
    string hex;
    if (!(in >> L.id >> hex >> L.d >> L.bv >> L.code) || hex.size() != 16) continue;
    for (int c = 0; c < 16; c++) L.b = bb::set_cell(L.b, c, (int)strtol(string(1, hex[c]).c_str(), nullptr, 16));
    lines.push_back(L);
  }
  if (!E.load(false)) return 1;
  vector<string> out(lines.size());
  atomic<size_t> next{0};
  auto work = [&]() {
    Worker W(E);
    for (;;) {
      size_t k = next.fetch_add(1);
      if (k >= lines.size()) break;
      out[k] = process(W, lines[k]);
    }
  };
  vector<thread> th;
  for (int i = 0; i < threads; i++) th.emplace_back(work);
  for (auto& t : th) t.join();
  if (RK > 0) printf("id\tcode\tL0r\tgain_r\tse_L0\tse_gain\tok\tnote\n");
  else printf("id\tcode\tL0\tgain\tplacebo\tok\tnote\trestore\trplacebo\tnloc\n");
  for (auto& o : out) printf("%s\n", o.c_str());
  return 0;
}
