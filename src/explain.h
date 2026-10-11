// Plain-word reasons for moves: board concepts a human player uses (biggest tile in a corner, a chain of decreasing
// tiles along the snake path, small tiles trapped among big ones, free cells, merges), their changes between moves,
// and what the random tile can do after a move (spawn risk).
#pragma once
#include <algorithm>
#include <cmath>
#include <string>
#include <vector>
#include "board.h"
#include "endgame.h"

namespace ex {

// Cell of path position p under orientation j (same convention as search.h's chain_cells: canonical (row, col) is
// mapped by column flip (bit 0), row flip (bit 1) and transpose (j >= 4)).
static inline int path_cell(int j, int p) {
  static const int path[16] = {0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12};
  int c = path[p], rr = c / 4, cc = c % 4;
  if (j & 1) cc = 3 - cc;
  if (j & 2) rr = 3 - rr;
  if (j >= 4) std::swap(rr, cc);
  return rr * 4 + cc;
}

static inline std::string cell_name(int c) {
  static const char* rows[4] = {"top", "second", "third", "bottom"};
  static const char* cols[4] = {"left", "second", "third", "right"};
  int r = c / 4, k = c % 4;
  if ((r == 0 || r == 3) && (k == 0 || k == 3)) return std::string(rows[r]) + "-" + cols[k] + " corner";
  return std::string(rows[r]) + " row, " + (k == 0 ? "left" : k == 3 ? "right" : std::string(cols[k])) +
         (k == 0 || k == 3 ? " edge" : " column");
}
// tile value text; analyze sets display_rank to show real values for boards whose big tiles the search board lowers
inline int display_rank[16] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
static inline std::string tile(int r) {
  if (r <= 0) return std::string("empty");
  int rr = r < 16 ? display_rank[r] : display_rank[15] + (r - 15);  // merge results above the search board's ranks
  return std::to_string(1L << rr);
}
// "a 1024", "an 8", "an 8192"
static inline std::string a_tile(int r) { return (tile(r)[0] == '8' ? "an " : "a ") + tile(r); }

struct Chain {
  int orient = -1;  // orientation of the snake path (path_cell)
  int len = 0;      // tiles in the chain: strictly decreasing from the biggest tile along the path
  int cells[16] = {};
  int ranks[16] = {};
  int collapse = 0;  // leading chain tiles whose ranks fall by exactly one (they all merge once the next tile arrives)
};

// The longest chain over the orientations whose path starts at a corner holding the biggest tile (len 0 if the
// biggest tile is in no corner). Ties: the orientation whose next cell after the chain holds the bigger tile.
static inline Chain chain_of(board_t b) {
  Chain best;
  int mx = bb::max_rank(b);
  if (!mx) return best;
  int best_next = -1;
  for (int j = 0; j < 8; j++) {
    if (bb::cell(b, path_cell(j, 0)) != mx) continue;
    Chain c;
    c.orient = j;
    int prev = 99;
    for (int p = 0; p < 16; p++) {
      int v = bb::cell(b, path_cell(j, p));
      if (v == 0 || v >= prev) break;
      c.cells[c.len] = path_cell(j, p), c.ranks[c.len] = v, c.len++;
      prev = v;
    }
    c.collapse = 1;
    while (c.collapse < c.len && c.ranks[c.collapse] == c.ranks[c.collapse - 1] - 1) c.collapse++;
    int next = c.len < 16 ? bb::cell(b, path_cell(j, c.len)) : 0;
    if (c.len > best.len || (c.len == best.len && next > best_next)) best = c, best_next = next;
  }
  return best;
}

struct Features {
  int max_rank = 0;
  bool corner = false;  // the biggest tile sits in a corner
  int chain_len = 0;
  int chain_ranks = 0;  // sum of 2^rank over the chain (how much of the board's value is lined up)
  int empty = 0;
  int merges = 0;       // adjacent equal pairs
  int trapped = 0;      // tiles of rank <= 3 (<= 8) with a neighbour of rank >= 7 (>= 128) on two sides or more
  int big_off_edge = 0; // tiles >= 1/4 of the biggest tile (and >= 64) not on an edge
  int corner_dist = 0;  // steps from the biggest tile (nearest copy) to the nearest corner
  int exposed = 0;      // empty cells next to a big tile (>= 1/8 of the biggest and >= 64): a new tile there gets stuck
};

static inline Features features(board_t b) {
  Features f;
  f.max_rank = bb::max_rank(b);
  int corners[4] = {0, 3, 12, 15};
  for (int c : corners) f.corner |= f.max_rank && bb::cell(b, c) == f.max_rank;
  Chain ch = chain_of(b);
  f.chain_len = ch.len;
  for (int i = 0; i < ch.len; i++) f.chain_ranks += 1 << ch.ranks[i];
  f.empty = bb::count_empty(b);
  for (int c = 0; c < 16; c++) {
    int v = bb::cell(b, c), r = c / 4, k = c % 4;
    if (!v) continue;
    if (k < 3 && bb::cell(b, c + 1) == v) f.merges++;
    if (r < 3 && bb::cell(b, c + 4) == v) f.merges++;
    if (v <= 3) {
      int big = 0;
      if (k > 0 && bb::cell(b, c - 1) >= 7) big++;
      if (k < 3 && bb::cell(b, c + 1) >= 7) big++;
      if (r > 0 && bb::cell(b, c - 4) >= 7) big++;
      if (r < 3 && bb::cell(b, c + 4) >= 7) big++;
      f.trapped += big >= 2;
    }
    bool edge = r == 0 || r == 3 || k == 0 || k == 3;
    if (!edge && v >= 6 && v >= f.max_rank - 2) f.big_off_edge++;
  }
  f.corner_dist = 9;
  for (int c = 0; c < 16; c++)
    if (bb::cell(b, c) == f.max_rank) {
      int r = c / 4, k = c % 4;
      f.corner_dist = std::min(f.corner_dist, std::min(r, 3 - r) + std::min(k, 3 - k));
    }
  int big = std::max(6, f.max_rank - 3);
  for (int c = 0; c < 16; c++) {
    if (bb::cell(b, c)) continue;
    int r = c / 4, k = c % 4;
    bool nb = (k > 0 && bb::cell(b, c - 1) >= big) || (k < 3 && bb::cell(b, c + 1) >= big) ||
              (r > 0 && bb::cell(b, c - 4) >= big) || (r < 3 && bb::cell(b, c + 4) >= big);
    f.exposed += nb;
  }
  return f;
}

// The plan in the position, as data: the chain of big tiles and what its end needs next. The chain stops before small
// stragglers (a tile below 8 or 16x smaller than the chain tile before it, in REAL tile values: boards with lowered big
// tiles compress the ranks): they are not part of the plan. Of the orientations whose path starts at a corner holding
// the biggest tile, the plan uses the one with the longest chain after that cut (chain_of ranks by the uncut length).
//   type ""          nothing to plan (largest tile below 32)
//        "no_corner" the biggest tile is in no corner (and not in the "pair" shape)
//        "single"    only the corner tile counts (the next path tiles are stragglers)
//        "merge"     the next path cell holds a tile equal to the chain's end: merge it into the chain
//        "build"     the next path cell is empty: build a tile equal to the chain's end there
//        "grow"      the next path cell holds a smaller tile: grow it into the chain's end
//        "blocked"   the next path cell holds a bigger tile than the chain's end: it blocks the chain
//        "full"      the chain fills the whole path
//        "pair"      the biggest tile sits next to a corner that holds a tile half its size (a strong players' shape
//                    after a big merge): the corner tile is the head of the chain (step = its plan as above) and, once
//                    doubled, merges into the biggest tile
static inline int real_rank(int r) { return r <= 0 ? 0 : r < 16 ? display_rank[r] : display_rank[15] + (r - 15); }
static inline std::string real_tile(int rr) { return rr <= 0 ? std::string("empty") : std::to_string(1L << rr); }
static inline std::string a_real_tile(int rr) { return (real_tile(rr)[0] == '8' ? "an " : "a ") + real_tile(rr); }
struct Plan {
  std::string type, step;  // step: the chain plan's type (= type, except for "pair")
  Chain chain;             // the chain the plan uses
  int len = 0;             // chain tiles the plan uses (stragglers cut)
  int end = 0;             // rank of the chain's end (the tile its next cell needs)
  int next_cell = -1;      // the path cell after the chain's end
  int there = 0;           // the rank in next_cell (0: empty)
  int collapse = 0;        // leading plan tiles whose real ranks fall by one (all merge once the next tile arrives)
  int made_real = 0;       // real rank the tail (or the whole chain) merges into once the end tile arrives
  int tail = 0;            // first plan tile of that merging tail
  int pair_cell = -1;      // "pair": the biggest tile's cell
  int corner_cell = -1;    // the corner the plan is anchored in (the biggest tile's, or the pair's corner)
  int start = 0;           // path position of the chain's first tile (1: "single" with a chain next to the corner)
};
// The chain along orientation j from path position p0 (0: its corner; strictly decreasing ranks).
static inline Chain chain_along(board_t b, int j, int p0 = 0) {
  Chain c;
  c.orient = j;
  int prev = 99;
  for (int p = p0; p < 16; p++) {
    int v = bb::cell(b, path_cell(j, p));
    if (v == 0 || v >= prev) break;
    c.cells[c.len] = path_cell(j, p), c.ranks[c.len] = v, c.len++;
    prev = v;
  }
  c.collapse = 1;
  while (c.collapse < c.len && c.ranks[c.collapse] == c.ranks[c.collapse - 1] - 1) c.collapse++;
  return c;
}
// Chain tiles before the first straggler (real ranks).
static inline int cut_len(const Chain& ch) {
  int len = 1;
  while (len < ch.len && real_rank(ch.ranks[len]) >= 3 &&
         real_rank(ch.ranks[len - 1]) - real_rank(ch.ranks[len]) < 4)
    len++;
  return ch.len ? len : 0;
}
// The chain plan of chain ch (len >= 1) starting at path position p0: fills step, len, end, next_cell, there,
// collapse, made_real, tail.
static inline void chain_plan(board_t b, const Chain& ch, Plan& P, int p0 = 0) {
  P.chain = ch;
  P.start = p0;
  int len = cut_len(ch);
  P.len = len;
  if (len <= 0) return;  // (callers pass chains that start at a tile)
  P.end = ch.ranks[len - 1];
  if (len == 1) {
    P.step = "single";
    return;
  }
  P.next_cell = p0 + len < 16 ? path_cell(ch.orient, p0 + len) : -1;
  if (P.next_cell < 0) {
    P.step = "full";
    return;
  }
  P.there = bb::cell(b, P.next_cell);
  P.step = P.there == P.end ? "merge" : P.there == 0 ? "build" : P.there < P.end ? "grow" : "blocked";
  // the chain's end has other neighbours off the path: a tile equal to the end there is a merge the path misses, and
  // when the path cell holds a small tile, a bigger head start there is where players and the engine usually build
  // (the plan study, 2026-10-07: on such positions they build first in the off-path cell 2-3x as often; an EMPTY path
  // cell is as good as an off-path head start, and the snake continuation is kept)
  if (P.step != "merge" && P.step != "blocked") {
    int e = ch.cells[len - 1], er = e / 4, ec = e % 4;
    int nbs[4] = {er > 0 ? e - 4 : -1, er < 3 ? e + 4 : -1, ec > 0 ? e - 1 : -1, ec < 3 ? e + 1 : -1};
    int best = -1, best_v = P.there;
    for (int x : nbs) {
      if (x < 0 || x == P.next_cell) continue;
      bool in_chain = false;
      for (int i = 0; i < len; i++) in_chain |= ch.cells[i] == x;
      if (in_chain) continue;
      int v = bb::cell(b, x);
      if (v == P.end) {
        best = x, best_v = v;
        break;
      }
      if (P.step == "grow" && v < P.end && v > best_v) best = x, best_v = v;
    }
    if (best >= 0) {
      P.next_cell = best, P.there = best_v;
      P.step = best_v == P.end ? "merge" : "grow";
    }
  }
  int rr[16];
  for (int i = 0; i < len; i++) rr[i] = real_rank(ch.ranks[i]);
  int collapse = 1;
  while (collapse < len && rr[collapse] == rr[collapse - 1] - 1) collapse++;
  P.collapse = collapse;
  int t = len - 1;
  while (t > 0 && rr[t - 1] == rr[t] + 1) t--;
  P.tail = collapse == len ? 0 : t;
  P.made_real = collapse == len ? rr[0] + 1 : rr[t] + 1;
}
static inline Plan plan_info(board_t b) {
  Plan P;
  int mx = bb::max_rank(b);
  if (mx < 5) return P;  // nothing to plan on a near-empty board
  // the best chain from a corner holding the biggest tile: longest after the straggler cut, then longest, then the
  // bigger tile after it (chain_of's rule)
  // (when no orientation keeps more than the corner tile: the one with the bigger tile next to the corner)
  Chain best;
  int best_cut = -1, best_next = -1, best_n1 = -1;
  for (int j = 0; j < 8; j++) {
    if (bb::cell(b, path_cell(j, 0)) != mx) continue;
    Chain c = chain_along(b, j);
    int cl = cut_len(c), next = c.len < 16 ? bb::cell(b, path_cell(j, c.len)) : 0;
    int n1 = bb::cell(b, path_cell(j, 1));
    n1 = n1 < mx ? n1 : -1;
    bool better = cl > best_cut;
    if (cl == best_cut) {
      if (cl == 1 && n1 != best_n1) better = n1 > best_n1;
      else better = c.len > best.len || (c.len == best.len && next > best_next);
    }
    if (better) best = c, best_cut = cl, best_next = next, best_n1 = n1;
  }
  if (best_cut > 0) {
    chain_plan(b, best, P);
    P.type = P.step;
    P.corner_cell = best.cells[0];
    if (P.type == "single") {
      // the corner tile stands alone (the next tile is a straggler): plan the chain next to it, if there is one
      Chain sub = chain_along(b, best.orient, 1);
      if (sub.len >= 2 && cut_len(sub) >= 2 && real_rank(sub.ranks[0]) >= 3) {
        chain_plan(b, sub, P, 1);
        P.type = "single";
      } else {
        P.step = "single";
      }
    }
    return P;
  }
  // the pair shape: the biggest tile on an edge next to a corner whose tile is half of it; the chain runs from that
  // corner along the other edge (away from the biggest tile)
  static const int corners[4] = {0, 3, 12, 15};
  for (int c : corners) {
    if (real_rank(bb::cell(b, c)) != real_rank(mx) - 1) continue;
    int r = c / 4, k = c % 4;
    int nbs[2] = {r * 4 + (k == 0 ? 1 : 2), (r == 0 ? 4 : 8) + k};
    for (int m : nbs) {
      if (bb::cell(b, m) != mx) continue;
      for (int j = 0; j < 8; j++) {
        if (path_cell(j, 0) != c || path_cell(j, 1) == m) continue;
        chain_plan(b, chain_along(b, j), P);
        P.type = "pair";
        P.pair_cell = m;
        P.corner_cell = c;
        return P;
      }
    }
  }
  P.type = "no_corner";
  return P;
}
// The plan in plain words (plan_info as a sentence). With best_dir (the engine's best move, 0-3 = up, right, down,
// left; -1: unknown), a merge the plan names but the best move does not make is not phrased as an instruction.
static inline std::string plan_core(board_t b, int best_dir, const char* best_name) {
  Plan P = plan_info(b);
  const Chain& ch = P.chain;
  if (P.type.empty()) return "";
  if (P.type == "no_corner") {
    int mx = bb::max_rank(b);
    return "Get your biggest tile (" + tile(mx) + ") into a corner and build around it.";
  }
  bool pair = P.type == "pair";
  int corner_rank = bb::cell(b, P.corner_cell);
  std::string s;
  if (pair)
    s = "Your " + tile(bb::cell(b, P.pair_cell)) + " sits next to the " + cell_name(P.corner_cell) + ", where your " +
        tile(corner_rank) + " is: once the " + tile(corner_rank) + " doubles, the two merge. ";
  if (P.step == "single") {  // only the corner tile: what the tile next to it must become
    int c1 = path_cell(ch.orient, 1), v1 = bb::cell(b, c1);
    if (pair) {
      if (v1 == 0) return s + "Build " + a_tile(corner_rank) + " in the empty " + cell_name(c1) + " next to it.";
      if (v1 < corner_rank && real_rank(v1) >= 3)
        return s + "Build up the " + tile(v1) + " in the " + cell_name(c1) + " next to it into " + a_tile(corner_rank) + ".";
      return s + "Build " + a_tile(corner_rank) + " next to it.";
    }
    if (v1 > 0 && v1 < corner_rank && real_rank(v1) >= 3)
      return "Keep the " + tile(corner_rank) + " in the " + cell_name(P.corner_cell) + " and build up the " + tile(v1) +
             " next to it (" + cell_name(c1) + ") toward " + a_real_tile(real_rank(corner_rank) - 1) + ".";
    return "Keep the " + tile(corner_rank) + " in the " + cell_name(P.corner_cell) +
           " and line up the next biggest tiles next to it.";
  }
  int len = P.len, end = P.end;
  if (P.type == "single")  // the corner tile alone, a chain of smaller tiles next to it
    s = "Keep the " + tile(corner_rank) + " in the " + cell_name(P.corner_cell) + "; your chain ";
  else
    s += "Your chain ";
  for (int i = 0; i < len; i++) s += (i ? "-" : "") + tile(ch.ranks[i]);
  s += P.type == "single" ? " runs next to it. " : " runs from the " + cell_name(ch.cells[0]) + ". ";
  if (P.step == "full") return s;
  std::string where = cell_name(P.next_cell);
  int there = P.there;
  if (P.step == "merge") {
    // does the engine's best move make this merge (the merged tile lands on the chain's end)?
    bool now = best_dir < 0 || bb::cell(bb::move(b, best_dir), ch.cells[len - 1]) == end + 1;
    if (now) s += "Merge the " + tile(end) + " in the " + where + " into it";
    else
      s += "The " + tile(end) + " in the " + where + " can merge into it (the engine prefers " +
           (best_name ? best_name : "another move") + " first)";
  } else if (P.step == "build") s += "Build " + a_tile(end) + " in the empty " + where + " next to the " + tile(end);
  else if (P.step == "grow") s += "Grow the " + tile(there) + " in the " + where + " into " + a_tile(end);
  else return s + "The " + tile(there) + " in the " + where + " blocks it: merge it away or rebuild the chain around it.";
  std::string then_pair = pair ? ", which merges with your " + tile(bb::cell(b, P.pair_cell)) : "";
  if (P.collapse == len) {
    s += ": then the whole chain merges into " + a_real_tile(real_rank(ch.ranks[0]) + 1) + then_pair + ".";
    return s;
  }
  int t = P.tail;
  int made = P.made_real;
  s += ": the tail merges into " + a_real_tile(made);
  if (t > 0 && made == real_rank(ch.ranks[t - 1]) - 1) s += ", which completes your chain below the " + tile(ch.ranks[t - 1]) + ".";
  else if (t > 0 && made == real_rank(ch.ranks[t - 1])) s += " and keeps merging up the chain.";
  else s += ".";
  return s;
}

// The plan sentence (plan_core), plus a note when the engine's best move takes the plan's corner tile out of its corner
// early in a game (largest tile up to 512): the engine commits to a corner only from ~1024 on (the plan study: its
// best move leaves the corner in 31% of such positions, players' moves in 2%), and the plan is the human strategy.
static inline std::string plan(board_t b, int best_dir = -1, const char* best_name = nullptr) {
  std::string s = plan_core(b, best_dir, best_name);
  if (best_dir < 0 || s.empty() || real_rank(bb::max_rank(b)) > 9) return s;
  Plan P = plan_info(b);
  if (P.corner_cell < 0 || P.type == "pair") return s;
  board_t a = bb::move(b, best_dir);
  if (bb::cell(a, P.corner_cell) < bb::cell(b, P.corner_cell))
    s += " This early the engine does not mind leaving the corner (its best move, " + std::string(best_name ? best_name : "") +
         ", does).";
  return s;
}

struct Reason {
  std::string code, text;
  double share = -1;  // analyze: the share of the move's loss that removing this defect recovers (-1: not measured)
};

// Merges made by the move before -> after (no spawn in between): m[k] = merges of two rank-k tiles into rank k+1,
// solved from the rank counts (count_after[k] = count_before[k] - 2 m[k] + m[k-1]). Returns the largest new rank (0: none).
static inline int largest_merge(board_t before, board_t after, int* count_out = nullptr) {
  int cb[17] = {0}, ca[17] = {0};
  for (int i = 0; i < 16; i++) cb[bb::cell(before, i)]++, ca[bb::cell(after, i)]++;
  int m[17] = {0};
  for (int k = 15; k >= 2; k--) m[k - 1] = ca[k] - cb[k] + 2 * m[k];
  int total = 0, top = 0;
  for (int k = 1; k < 16; k++)
    if (m[k] > 0) total += m[k], top = k + 1;
  if (count_out) *count_out = total;
  return top;
}

// The row or column along the edge where the biggest tile sits in a corner (the "home" edge of corner players):
// its 4 cells, or false if the biggest tile is in no corner. Between the two edges through that corner, the one
// holding more of the big tiles.
static inline bool home_edge(board_t b, int cells[4]) {
  int mx = bb::max_rank(b);
  int corners[4] = {0, 3, 12, 15};
  for (int c : corners) {
    if (bb::cell(b, c) != mx) continue;
    int r = c / 4, k = c % 4, row[4], col[4], sr = 0, sc = 0;
    for (int i = 0; i < 4; i++) {
      row[i] = r * 4 + i, col[i] = i * 4 + k;
      sr += 1 << bb::cell(b, row[i]), sc += 1 << bb::cell(b, col[i]);
    }
    for (int i = 0; i < 4; i++) cells[i] = sr >= sc ? row[i] : col[i];
    return true;
  }
  return false;
}
static inline int filled(board_t b, const int cells[4]) {
  int n = 0;
  for (int i = 0; i < 4; i++) n += bb::cell(b, cells[i]) != 0;
  return n;
}
static inline std::string edge_name(const int cells[4]) {
  bool row = cells[1] == cells[0] + 1;
  if (row) return cells[0] / 4 == 0 ? "top row" : "bottom row";
  return cells[0] % 4 == 0 ? "left column" : "right column";
}

// Why move `m` is worse than the best move: concept changes between the two afterstates (best first).
static inline std::vector<Reason> compare(board_t before, board_t best_after, board_t move_after) {
  std::vector<Reason> out;
  Features f0 = features(before), fb = features(best_after), fm = features(move_after);
  int nb = 0, nm = 0, mb = largest_merge(before, best_after, &nb), mm = largest_merge(before, move_after, &nm);
  if (mb >= 5 && mb > mm) {
    // the best move merges bigger tiles; are they still mergeable after this move? (adjacent equal tiles of that rank)
    bool still = false;
    for (int c = 0; c < 16 && !still; c++) {
      if (bb::cell(move_after, c) != mb - 1) continue;
      if (c % 4 < 3 && bb::cell(move_after, c + 1) == mb - 1) still = true;
      if (c / 4 < 3 && bb::cell(move_after, c + 4) == mb - 1) still = true;
    }
    out.push_back({"missed_merge", "misses merging the two " + tile(mb - 1) + "s" +
                                       (still ? "" : std::string(" (they are no longer next to each other)"))});
  }
  if (fm.empty <= 1 && fm.merges == 0 && !(fb.empty <= 1 && fb.merges == 0))
    out.push_back({"danger", "puts the game in danger: almost no free cells and nothing to merge"});
  if (fb.corner && !fm.corner)
    out.push_back({"corner", "moves your biggest tile (" + tile(fm.max_rank) + ") out of its corner"});
  Chain c0 = chain_of(before);
  if (c0.len >= 2) {
    // chain tiles that leave their cell (and are not merged up into a bigger tile there)
    int lost = -1;
    for (int i = 0; i < c0.len; i++)
      if (bb::cell(move_after, c0.cells[i]) < c0.ranks[i] && bb::cell(best_after, c0.cells[i]) >= c0.ranks[i]) {
        lost = i;
        break;
      }
    if (lost >= 0)
      out.push_back({"chain", "pulls the " + tile(c0.ranks[lost]) + " out of your chain (" + cell_name(c0.cells[lost]) + ")"});
  }
  int edge[4];
  if (home_edge(before, edge) && filled(before, edge) == 4 && filled(best_after, edge) == 4 && filled(move_after, edge) < 4)
    out.push_back({"edge", "leaves a gap in your " + edge_name(edge) + " where a new small tile can land"});
  if (fb.chain_len >= 3 && fm.chain_len + 2 <= fb.chain_len && fm.corner)
    out.push_back({"chain_len", "lines up fewer of your big tiles in order (a chain of " + std::to_string(fm.chain_len) +
                                    " vs " + std::to_string(fb.chain_len) + ")"});
  // (no "trapped" reason: removing the trapped small tiles recovers no more of a move's loss than removing as many
  // other small tiles - 0.24 of the loss either way on 194 real cases, workstream expl 2026-10-07 - the effect is the
  // free cells, not the trapping)
  if (fm.big_off_edge > fb.big_off_edge)
    out.push_back({"center", "brings a big tile into the middle of the board"});
  if (!fm.corner && !fb.corner && fm.corner_dist > fb.corner_dist)
    out.push_back({"toward_corner", "keeps your biggest tile (" + tile(fm.max_rank) + ") further from a corner"});
  if (fm.exposed > fb.exposed)
    out.push_back({"exposed", "opens space next to your big tiles where a new small tile can get stuck"});
  // free cells and merges barely predict value losses on human positions (corr -0.05 / +0.01 over 14k position-move
  // pairs, NOTES 2026-10-06): only a large difference in free cells is worth saying, merge counts never
  if (fm.empty + 3 <= fb.empty)
    out.push_back({"space", "leaves fewer free cells (" + std::to_string(fm.empty) + " vs " + std::to_string(fb.empty) + ")"});
  (void)f0;
  // strongest predictors of real losses first (correlations with the value loss on human positions)
  static const char* order[] = {"danger", "corner", "chain", "chain_len", "missed_merge", "exposed", "center",
                                "toward_corner", "trapped", "edge", "space"};
  auto rank = [](const std::string& c) {
    for (int i = 0; i < 11; i++)
      if (c == order[i]) return i;
    return 11;
  };
  std::stable_sort(out.begin(), out.end(), [&](const Reason& a, const Reason& b) { return rank(a.code) < rank(b.code); });
  return out;
}

// What makes the best move good, in words (relative to the alternatives' afterstates).
static inline std::vector<Reason> strengths(board_t before, board_t best_after, const std::vector<board_t>& others) {
  std::vector<Reason> out;
  Features fb = features(best_after);
  bool keeps_corner = fb.corner, others_break = false, more_space = true;
  int max_other_empty = -1;
  for (board_t o : others) {
    Features fo = features(o);
    others_break |= keeps_corner && !fo.corner;
    max_other_empty = std::max(max_other_empty, fo.empty);
  }
  more_space = !others.empty() && fb.empty > max_other_empty;
  int nm = 0, top = largest_merge(before, best_after, &nm);
  if (top >= 4) out.push_back({"merge", "merges the two " + tile(top - 1) + "s into " + a_tile(top)});
  if (others_break) out.push_back({"corner", "keeps your biggest tile in its corner"});
  int edge[4];
  if (home_edge(before, edge) && filled(before, edge) == 4 && filled(best_after, edge) == 4) {
    bool other_opens = false;
    for (board_t o : others) other_opens |= filled(o, edge) < 4;
    if (other_opens) out.push_back({"edge", "keeps your " + edge_name(edge) + " full so it cannot slide"});
  }
  Chain cb = chain_of(best_after), c0 = chain_of(before);
  if (cb.len > c0.len && c0.len >= 1)
    out.push_back({"chain", "extends your chain to " + std::to_string(cb.len) + " tiles"});
  if (more_space) out.push_back({"space", "keeps the most free cells (" + std::to_string(fb.empty) + ")"});
  Features f0 = features(before);
  if (!f0.corner && fb.corner_dist < f0.corner_dist)
    out.push_back({"toward_corner", "moves your biggest tile toward a corner"});

  return out;
}

}  // namespace ex
