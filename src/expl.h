// Counterfactual checks of the analysis' reasons (workstream expl, 2026-10-07): for a worse move's afterstate `am`, the
// reference move's afterstate `ab` and the position before `b`, the edit that removes exactly the defect a reason
// names (e.g. "moves your biggest tile out of its corner": the biggest tile swapped back into the corner it keeps after
// the reference move), and a placebo (the same kind of edit somewhere unrelated). analyze keeps a concept reason only
// when its edit recovers a real share of the move's loss (and orders the reasons by that share); build/expl_tool
// measures the shares and the placebos on samples of real positions.
#pragma once
#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "board.h"
#include "engine.h"
#include "explain.h"

namespace xp {
using std::max;
using std::min;
using std::pair;
using std::string;
using std::vector;
using std::swap;
using std::sort;

static inline board_t swapc(board_t x, int i, int j) {
  int a = bb::cell(x, i), c = bb::cell(x, j);
  x = bb::set_cell(x, i, c);
  return bb::set_cell(x, j, a);
}
static inline int dist(int a, int b) { return abs(a / 4 - b / 4) + abs(a % 4 - b % 4); }
static inline bool is_corner(int c) { return c == 0 || c == 3 || c == 12 || c == 15; }
static inline bool on_edge(int c) { return c / 4 == 0 || c / 4 == 3 || c % 4 == 0 || c % 4 == 3; }


// The edit that removes the stated defect, and a placebo (the same kind of edit somewhere unrelated). Returns false
// (with a note) when the edit cannot be built. Boards are in the engine's encoding (real ranks, lowered big tiles).
struct Edit {
  board_t b, ab, am;
  bb::Rng& rng;
  string note;
  vector<int> touched;

  // the biggest tile back into the corner it holds after the best move; placebo: the same tile to a random non-corner cell
  bool corner(board_t* out, board_t* pl) {
    int mxb = bb::max_rank(ab), cc = -1;
    for (int c : {0, 3, 12, 15})
      if (bb::cell(ab, c) == mxb) cc = c;
    int mxm = bb::max_rank(am), p = -1, bd = 99;
    for (int c = 0; c < 16; c++)
      if (bb::cell(am, c) == mxm && dist(c, cc < 0 ? 0 : cc) < bd) bd = dist(c, cc < 0 ? 0 : cc), p = c;
    if (cc < 0 || p < 0 || p == cc) return note = "no corner to restore", false;
    *out = swapc(am, p, cc);
    *pl = random_move_of(p, [&](int c) { return !is_corner(c) && c != p; });
    touched = {p, cc};
    return true;
  }
  // the chain tile that left its cell, back into it (from the nearest copy); placebo: that tile to a random other cell
  bool chain(board_t* out, board_t* pl) {
    ex::Chain c0 = ex::chain_of(b);
    int lost = -1;
    for (int i = 0; i < c0.len; i++)
      if (bb::cell(am, c0.cells[i]) < c0.ranks[i] && bb::cell(ab, c0.cells[i]) >= c0.ranks[i]) {
        lost = i;
        break;
      }
    if (lost < 0) return note = "no lost chain tile", false;
    int t = c0.cells[lost], r = c0.ranks[lost], q = -1, bd = 99;
    for (int c = 0; c < 16; c++)
      if (c != t && bb::cell(am, c) == r && dist(c, t) < bd) bd = dist(c, t), q = c;
    if (q < 0) return note = "lost tile not on the board", false;
    *out = swapc(am, q, t);
    *pl = random_move_of(q, [&](int c) { return c != t && c != q; });
    touched = {q, t};
    return true;
  }
  // the best move's chain order restored in d's afterstate (swaps of the chain ranks into the chain cells); placebo:
  // the same tiles swapped into random cells
  bool chain_len(board_t* out, board_t* pl) {
    ex::Chain cb = ex::chain_of(ab);
    if (cb.len < 2) return note = "no chain after the best move", false;
    board_t x = am, y = am;
    bool fixed[16] = {};
    int swaps = 0;
    for (int p = 0; p < cb.len; p++) {
      int t = cb.cells[p], r = cb.ranks[p];
      if (bb::cell(x, t) != r) {
        int q = -1, bd = 99;
        for (int c = 0; c < 16; c++)
          if (!fixed[c] && c != t && bb::cell(x, c) == r && dist(c, t) < bd) bd = dist(c, t), q = c;
        if (q < 0) break;
        x = swapc(x, q, t), swaps++;
        // placebo: the same tile from its cell in the placebo board to a random cell outside the chain path
        int qy = -1;
        for (int c = 0; c < 16; c++)
          if (bb::cell(y, c) == r) qy = c;
        if (qy >= 0) {
          int dest = random_cell([&](int c) { return c != qy && !in_path(cb, c); });
          if (dest >= 0) y = swapc(y, qy, dest);
        }
      }
      fixed[t] = true;
    }
    if (!swaps) return note = "chain already in order", false;
    *out = x, *pl = y;
    touched.clear();
    for (int c = 0; c < 16; c++)
      if (bb::cell(x, c) != bb::cell(am, c)) touched.push_back(c);
    return true;
  }
  static bool in_path(const ex::Chain& ch, int c) {
    for (int i = 0; i < ch.len; i++)
      if (ch.cells[i] == c) return true;
    return false;
  }
  // the merge the best move makes, made in d's afterstate (two tiles of that rank -> one of the next rank, at the cell
  // nearer to where the best move puts it); placebo: two equal smaller tiles merged instead (if any)
  bool missed_merge(board_t* out, board_t* pl) {
    int nb = 0, mb = ex::largest_merge(b, ab, &nb);
    if (mb < 2) return note = "no merge by the best move", false;
    int r = mb - 1, target = -1;
    for (int c = 0; c < 16; c++)
      if (bb::cell(ab, c) == mb && bb::cell(b, c) != mb) target = c;
    vector<int> cs;
    for (int c = 0; c < 16; c++)
      if (bb::cell(am, c) == r) cs.push_back(c);
    if (cs.size() < 2) return note = "the two tiles are gone", false;
    int i0 = 0, i1 = 1, best = 99;  // prefer an adjacent pair, then the pair nearest to the target
    for (size_t i = 0; i < cs.size(); i++)
      for (size_t j = i + 1; j < cs.size(); j++) {
        int s = (dist(cs[i], cs[j]) == 1 ? 0 : 50) + (target >= 0 ? min(dist(cs[i], target), dist(cs[j], target)) : 0);
        if (s < best) best = s, i0 = (int)i, i1 = (int)j;
      }
    int keep = cs[i0], drop = cs[i1];
    if (target >= 0 && dist(drop, target) < dist(keep, target)) swap(keep, drop);
    *out = bb::set_cell(bb::set_cell(am, keep, mb), drop, 0);
    touched = {keep, drop};
    if (target >= 0 && target != keep && target != drop) touched.push_back(target);
    // placebo: a pair of equal tiles of a smaller rank merged the same way
    vector<pair<int, int>> pairs;
    for (int c = 0; c < 16; c++)
      for (int e = c + 1; e < 16; e++)
        if (bb::cell(am, c) && bb::cell(am, c) == bb::cell(am, e) && bb::cell(am, c) < r) pairs.push_back({c, e});
    if (pairs.empty()) return note = "placebo: no smaller equal pair", *pl = am, true;
    auto pr = pairs[rng.next() % pairs.size()];
    *pl = bb::set_cell(bb::set_cell(am, pr.first, bb::cell(am, pr.first) + 1), pr.second, 0);
    return true;
  }
  // danger (almost no free cells, nothing to merge): the smallest tile removed (one free cell); placebo: two random
  // tiles swapped (no cell freed)
  bool danger(board_t* out, board_t* pl) {
    int sc = -1, sr = 99;
    for (int c = 0; c < 16; c++)
      if (bb::cell(am, c) && bb::cell(am, c) < sr) sr = bb::cell(am, c), sc = c;
    if (sc < 0) return note = "empty board", false;
    *out = bb::set_cell(am, sc, 0);
    *pl = random_swap(am);
    touched = {sc};
    return true;
  }
  // a gap in the home edge: filled from the tile the best move keeps there (moved in from its nearest copy, else a 2);
  // placebo: the same filling at a random empty cell off the edge
  bool edge(board_t* out, board_t* pl) {
    int e[4];
    if (!ex::home_edge(b, e)) return note = "no home edge", false;
    int gap = -1;
    for (int i = 0; i < 4; i++)
      if (!bb::cell(am, e[i]) && bb::cell(ab, e[i])) gap = e[i];
    if (gap < 0) return note = "no gap", false;
    int r = bb::cell(ab, gap), q = -1, bd = 99;
    for (int c = 0; c < 16; c++)
      if (bb::cell(am, c) == r && dist(c, gap) < bd && !(c == e[0] || c == e[1] || c == e[2] || c == e[3])) bd = dist(c, gap), q = c;
    *out = q >= 0 ? swapc(am, q, gap) : bb::set_cell(am, gap, 1);
    touched = {e[0], e[1], e[2], e[3]};
    int dest = random_cell([&](int c) { return !bb::cell(am, c) && c != gap && c != e[0] && c != e[1] && c != e[2] && c != e[3]; });
    if (dest < 0) return note = "placebo: no free cell", *pl = am, true;
    *pl = q >= 0 ? swapc(am, q, dest) : bb::set_cell(am, dest, 1);
    return true;
  }
  // small tiles stuck between big ones: the extra trapped tiles removed; placebo: as many untrapped small tiles removed
  bool trapped(board_t* out, board_t* pl) {
    auto trapped_cells = [](board_t x) {
      vector<int> t;
      for (int c = 0; c < 16; c++) {
        int v = bb::cell(x, c), r = c / 4, k = c % 4, big = 0;
        if (!v || v > 3) continue;
        if (k > 0 && bb::cell(x, c - 1) >= 7) big++;
        if (k < 3 && bb::cell(x, c + 1) >= 7) big++;
        if (r > 0 && bb::cell(x, c - 4) >= 7) big++;
        if (r < 3 && bb::cell(x, c + 4) >= 7) big++;
        if (big >= 2) t.push_back(c);
      }
      return t;
    };
    vector<int> tm = trapped_cells(am), tb = trapped_cells(ab);
    int extra = (int)tm.size() - (int)tb.size();
    if (extra <= 0) return note = "no extra trapped tile", false;
    board_t x = am;
    int done = 0;
    for (int c : tm) {
      bool also_b = false;
      for (int c2 : tb) also_b |= c2 == c;
      if (!also_b && done < extra) x = bb::set_cell(x, c, 0), done++;
    }
    for (int c : tm)
      if (done < extra && bb::cell(x, c)) x = bb::set_cell(x, c, 0), done++;
    *out = x;
    touched = tm;
    board_t y = am;
    for (int k = 0; k < extra; k++) {
      int c = random_cell([&](int c) {
        int v = bb::cell(y, c);
        bool t = false;
        for (int c2 : tm) t |= c2 == c;
        return v && v <= 3 && !t;
      });
      if (c >= 0) y = bb::set_cell(y, c, 0);
    }
    *pl = y;
    return true;
  }
  // a big tile in the middle: moved to the nearest edge cell (swap); placebo: the same tile to a random middle cell
  bool center(board_t* out, board_t* pl) {
    int mx = bb::max_rank(am), p = -1;
    ex::Features fb = ex::features(ab);
    (void)fb;
    for (int c = 0; c < 16; c++) {
      int v = bb::cell(am, c);
      if (!on_edge(c) && v >= 6 && v >= mx - 2 && (p < 0 || v > bb::cell(am, p))) p = c;
    }
    if (p < 0) return note = "no big tile in the middle", false;
    int q = -1, bd = 99;  // the edge cell next to it with the smallest tile
    for (int c = 0; c < 16; c++)
      if (on_edge(c) && dist(c, p) == 1 && (q < 0 || bb::cell(am, c) < bb::cell(am, q))) q = c, bd = 1;
    (void)bd;
    if (q < 0) return note = "no edge neighbour", false;
    *out = swapc(am, p, q);
    touched = {p, q};
    int dest = random_cell([&](int c) { return !on_edge(c) && c != p; });
    *pl = dest >= 0 ? swapc(am, p, dest) : am;
    return true;
  }
  // the biggest tile (off-corner) moved to the nearest corner (swap); placebo: to a random non-corner cell
  bool toward_corner(board_t* out, board_t* pl) {
    int mx = bb::max_rank(am), p = -1;
    for (int c = 0; c < 16; c++)
      if (bb::cell(am, c) == mx) p = c;
    int cc = -1, bd = 99;
    for (int c : {0, 3, 12, 15})
      if (dist(c, p) < bd) bd = dist(c, p), cc = c;
    if (p < 0 || cc == p) return note = "already in a corner", false;
    *out = swapc(am, p, cc);
    *pl = random_move_of(p, [&](int c) { return !is_corner(c) && c != p; });
    touched = {p, cc};
    return true;
  }
  // open cells next to big tiles: each extra exposed cell gets the tile the best move has there (moved in from its
  // nearest copy); placebo: the same tiles moved to random empty cells that are not exposed
  bool exposed(board_t* out, board_t* pl) {
    auto exposed_cells = [](board_t x) {
      vector<pair<int, int>> e;  // (biggest neighbour, cell)
      int big = max(6, bb::max_rank(x) - 3);
      for (int c = 0; c < 16; c++) {
        if (bb::cell(x, c)) continue;
        int r = c / 4, k = c % 4, nb = 0;
        if (k > 0) nb = max(nb, bb::cell(x, c - 1));
        if (k < 3) nb = max(nb, bb::cell(x, c + 1));
        if (r > 0) nb = max(nb, bb::cell(x, c - 4));
        if (r < 3) nb = max(nb, bb::cell(x, c + 4));
        if (nb >= big) e.push_back({nb, c});
      }
      sort(e.rbegin(), e.rend());
      return e;
    };
    auto em = exposed_cells(am), eb = exposed_cells(ab);
    int extra = (int)em.size() - (int)eb.size();
    if (extra <= 0) return note = "no extra exposed cell", false;
    board_t x = am, y = am;
    touched.clear();
    int moved = 0;
    for (auto& pe : em) {
      if (moved >= extra) break;
      int e = pe.second, t = bb::cell(ab, e);
      bool also_b = false;
      for (auto& q : eb) also_b |= q.second == e;
      if (also_b || !t) continue;
      int q = -1, bd = 99;
      for (int c = 0; c < 16; c++)
        if (c != e && bb::cell(x, c) == t && dist(c, e) < bd) bd = dist(c, e), q = c;
      if (q < 0) continue;
      x = swapc(x, q, e), moved++;
      touched.push_back(e), touched.push_back(q);
      int qy = -1;
      for (int c = 0; c < 16; c++)
        if (bb::cell(y, c) == t) qy = c;
      int dest = random_cell([&](int c) {
        if (bb::cell(y, c) || c == e) return false;
        for (auto& p2 : em)
          if (p2.second == c) return false;
        return true;
      });
      if (qy >= 0 && dest >= 0) y = swapc(y, qy, dest);
    }
    if (!moved) return note = "no exposed cell the best move fills", false;
    *out = x, *pl = y;
    return true;
  }
  // fewer free cells: the k smallest tiles removed (k = the difference in free cells); placebo: two random tiles swapped
  bool space(board_t* out, board_t* pl) {
    int k = bb::count_empty(ab) - bb::count_empty(am);
    if (k <= 0) return note = "no fewer free cells", false;
    board_t x = am;
    for (int i = 0; i < k; i++) {
      int sc = -1, sr = 99;
      for (int c = 0; c < 16; c++)
        if (bb::cell(x, c) && bb::cell(x, c) < sr) sr = bb::cell(x, c), sc = c;
      if (sc >= 0) x = bb::set_cell(x, sc, 0), touched.push_back(sc);
    }
    *out = x;
    *pl = random_swap(am);
    return true;
  }

  template <class F>
  int random_cell(F ok) {
    int cs[16], n = 0;
    for (int c = 0; c < 16; c++)
      if (ok(c)) cs[n++] = c;
    return n ? cs[rng.next() % n] : -1;
  }
  template <class F>
  board_t random_move_of(int p, F ok) {
    int dest = random_cell(ok);
    return dest >= 0 ? swapc(am, p, dest) : am;
  }
  board_t random_swap(board_t x) {
    for (int t = 0; t < 50; t++) {
      int i = rng.next() % 16, j = rng.next() % 16;
      if (i != j && bb::cell(x, i) != bb::cell(x, j) && bb::cell(x, i) && bb::cell(x, j)) return swapc(x, i, j);
    }
    return x;
  }
};

// The 2x2 area where the network's per-cell attribution of d's afterstate falls furthest below bv's (as analyze's
// "area" reason); -1 when there is none.
static inline int worst_area(const Engine& E, board_t ab, board_t am) {
  float hm[16], hb[16];
  E.ev.attribute(E.view(am), hm);
  E.ev.attribute(E.view(ab), hb);
  float total = 0, worst = 0;
  int w = -1;
  for (int c = 0; c < 16; c++) total += hm[c] - hb[c];
  for (int r = 0; r < 3; r++)
    for (int c = 0; c < 3; c++) {
      float x = 0;
      for (int dr = 0; dr < 2; dr++)
        for (int dc = 0; dc < 2; dc++) x += hm[(r + dr) * 4 + c + dc] - hb[(r + dr) * 4 + c + dc];
      if (x < worst) worst = x, w = r * 3 + c;
    }
  return total < 0 && w >= 0 && worst < 0.5f * total ? w : -1;
}
static inline board_t copy_area(board_t to, board_t from, int a) {
  int r = a / 3, c = a % 3;
  for (int dr = 0; dr < 2; dr++)
    for (int dc = 0; dc < 2; dc++) {
      int k = (r + dr) * 4 + c + dc;
      to = bb::set_cell(to, k, bb::cell(from, k));
    }
  return to;
}


// The edit for reason `code` (false when it cannot be built: the defect is not there in this form).
static inline bool fix(const string& code, board_t b, board_t ab, board_t am, bb::Rng& rng, board_t* out,
                       board_t* placebo = nullptr, string* note = nullptr) {
  Edit ed{b, ab, am, rng, "", {}};
  board_t o = am, p = am;
  bool ok = code == "corner" ? ed.corner(&o, &p) : code == "chain" ? ed.chain(&o, &p) : code == "chain_len" ? ed.chain_len(&o, &p)
            : code == "missed_merge" ? ed.missed_merge(&o, &p) : code == "danger" ? ed.danger(&o, &p)
            : code == "edge" ? ed.edge(&o, &p) : code == "trapped" ? ed.trapped(&o, &p) : code == "center" ? ed.center(&o, &p)
            : code == "toward_corner" ? ed.toward_corner(&o, &p) : code == "exposed" ? ed.exposed(&o, &p)
            : code == "space" ? ed.space(&o, &p) : (ed.note = "no edit for " + code, false);
  if (note) *note = ed.note;
  if (!ok) return false;
  *out = o;
  if (placebo) *placebo = p;
  return true;
}

}  // namespace xp
