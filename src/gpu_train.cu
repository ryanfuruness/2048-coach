// GPU self-play TD learning for n-tuple networks (same file format as train.cpp).
//
// One CUDA thread plays one game. Many games (e.g. 2^17) run concurrently, each
// step choosing argmax_a r + V(afterstate) and applying an online TD(0) update to
// the previous afterstate: V(as_{t-1}) <- r_t + V(as_t)  (0 at game end). Weight
// updates use atomics. Temporal coherence (TC) keeps per-weight accumulators.
// Multi-stage: one stage is trained; the others are frozen float tables.
#include <cuda_runtime.h>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include "board.h"
#include "ntuple.h"
#include "search.h"
#include "endgame.h"

using namespace std;
using Clock = chrono::steady_clock;

#define CK(x)                                                                                    \
  do {                                                                                           \
    cudaError_t e_ = (x);                                                                        \
    if (e_ != cudaSuccess) {                                                                     \
      fprintf(stderr, "CUDA error %s at %s:%d\n", cudaGetErrorString(e_), __FILE__, __LINE__); \
      exit(1);                                                                                   \
    }                                                                                            \
  } while (0)

constexpr int MAXP = 16;     // max patterns
constexpr int MAXC = 8;      // max cells per pattern
constexpr int MAXB = 12;     // max stage conditions

struct DevCfg {
  int np;                      // number of patterns
  int ncell[MAXP];
  int cells[MAXP][MAXC];
  unsigned long long offset[MAXP];  // offset of pattern within a stage
  unsigned long long stage_size;
  int nconds;                  // stage conditions (see StageFn in search.h)
  unsigned int cond_exact[MAXB];
  int cond_min[MAXB];
  int nsums;                   // sum-mode stage thresholds
  unsigned int sums[MAXB];
  int sum_or_rank[MAXB];       // "S/R": also passed once a tile of rank >= R exists (0 = none)
  int train_stage;
  int tc;
  float lr;                    // alpha (TD) or beta (TC), already divided by #features
  int downgrade;
  int min_gap;
  int pool_n;
  float pool_prob;
  float lambda;                // TD(lambda), truncated after `horizon` steps
  int horizon;
  int collect;                 // collect positions when this condition first holds
  unsigned int collect_exact;
  int collect_min;
  unsigned int collect_sum;    // or: when the tile sum first reaches this (0 = unused)
  int collect_every;           // >0: instead record every collect_every-th state of each episode
  int learn;
  int stop_at_boundary;        // end episodes when they move past the trained stage
  int policy_depth;            // 1: greedy on r + V(afterstate); 2: expectimax one move deeper
  int policy_beam;             // depth 2: only the policy_beam best moves by 1-ply value get the deeper look
  int policy_no4;              // depth 2: ignore 4-spawns in the lookahead (the 2 gets probability 1)
  int policy_max_empty;        // depth 2 only in states with at most this many empty cells
  int train_all_root;          // depth >= 2: also train every looked-ahead move's afterstate toward its
                               // expectimax backup (not only the chosen one toward its lambda-return)
  const float* stage_w[MAXB + 1];  // frozen stage tables (the trained stage's entry is unused)
  const float* teacher_w;      // optional: the policy uses this table for the trained stage (teacher-student)
  float explore;               // probability of playing a random other legal move (trains off-policy states)
  float policy_mix;            // depth >= 2: probability that a step uses the deeper policy (else 1-ply)
  float tc_forget;             // TC accumulators decay by this factor per update (1 = plain TC); keeps the
                               // per-weight rates tracking recent coherence instead of annealing to zero
  int upd_mode;                // batched update of a weight touched c times in a round: 0 mean error,
                               // 1 sum (as c sequential updates would be), 2 min(c, upd_cap) x mean, 3 sqrt(c) x mean
  float upd_cap;
  float branch_p;              // side branches (CPU train --branch): probability per step of training a branch that
  int branch_len;              // starts at a random non-chosen candidate and follows branch_len greedy moves
  int tc_mean;                 // TC accumulators take the round's mean error (consistent with the mean step)
                               // instead of the sum over the c transitions that touched the weight
  int corner_lock;             // >0: when a tile of the board's max rank (>= this) sits in a corner, moves
                               // that leave no such tile in a corner are not played (unless all moves do)
};
__constant__ DevCfg C;

// Endgame tables (src/endgame.h, snake endings) for the policy: in an ending whose table entry
// is known and wins with probability >= eg_min, the table's move is played instead of the
// network's, so the network learns the values of the combined player.
#define EG_MAXT 24
struct EgTable {
  int n;                       // free cells (index digits, least significant first)
  int cell[16];
  unsigned long long radix[16];
  int cap;                     // every free cell's cap (= goal rank)
  const int* slot;             // chunk -> position in data (in chunks), -1 = absent
  const unsigned short* data;
  unsigned long long nchunks;
};
struct EgCfg {
  int on, kmin, full;
  float min_p;
  int max_rank[17];
  unsigned long long chunk;      // entries per chunk
  signed char table_of[17][16];  // (k, r) -> table, -1 = none
  EgTable t[EG_MAXT];
};
__constant__ EgCfg EG;
__constant__ int EG_PATH[16] = {0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12};

struct TCE {  // checkpoint format: weight and TC accumulators
  float w, e, a;
};
// Device entry of the trained stage: the weight, its TC accumulators and the
// per-round error accumulators of the batched update, kept together so that an
// update touches one entry instead of several separate arrays.
struct WE {
  float w, e, a;
  float gsum, gabs;
  unsigned int gcnt;
};

struct GameState {
  unsigned long long board;
  unsigned long long score;
  unsigned int moves;
  int nring;  // afterstates waiting for their (truncated) lambda-return
  int head;   // ring index of the oldest one
  int collected;
  int made65536;  // two 32768s merged in this episode
  unsigned long long rng;
};

// Per-game ring of recent afterstates, stored [slot][game] for coalescing.
struct Ring {
  unsigned long long* as;
  float* r;   // reward and value that the previous afterstate's target uses: those of the
  float* v;   // greedy move (also when an exploratory move was played)
  unsigned char* cut;  // an exploratory move was played: the lambda-return stops here (Watkins)
  int n;  // number of games
};

struct EpisodeRec {
  unsigned long long score;
  unsigned int moves;
  int max_rank;
  unsigned int sum;  // final tile sum
  int exited;        // ended by leaving the trained stage (not by game over)
  int made65536;
};

// ---------------- device helpers ----------------
__device__ __forceinline__ unsigned long long splitmix(unsigned long long& x) {
  unsigned long long z = (x += 0x9E3779B97F4A7C15ULL);
  z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
  return z ^ (z >> 31);
}
__device__ __forceinline__ unsigned int below(unsigned long long& r, unsigned int n) {
  return (unsigned int)(((splitmix(r) >> 32) * (unsigned long long)n) >> 32);
}
__device__ __forceinline__ unsigned long long transpose(unsigned long long x) {
  unsigned long long a1 = x & 0xF0F00F0FF0F00F0FULL, a2 = x & 0x0000F0F00000F0F0ULL, a3 = x & 0x0F0F00000F0F0000ULL;
  unsigned long long a = a1 | (a2 << 12) | (a3 >> 12);
  unsigned long long b1 = a & 0xFF00FF0000FF00FFULL, b2 = a & 0x00FF00FF00000000ULL, b3 = a & 0x00000000FF00FF00ULL;
  return b1 | (b2 >> 24) | (b3 << 24);
}
__device__ __forceinline__ unsigned long long flip_h(unsigned long long b) {
  b = ((b & 0x00FF00FF00FF00FFULL) << 8) | ((b >> 8) & 0x00FF00FF00FF00FFULL);
  return ((b & 0x0F0F0F0F0F0F0F0FULL) << 4) | ((b >> 4) & 0x0F0F0F0F0F0F0F0FULL);
}
__device__ __forceinline__ unsigned long long flip_v(unsigned long long b) {
  return (b << 48) | ((b & 0xFFFF0000ULL) << 16) | ((b >> 16) & 0xFFFF0000ULL) | (b >> 48);
}
__device__ __forceinline__ unsigned long long dsym(unsigned long long b, int j) {
  if (j >= 4) b = transpose(b);
  switch (j & 3) {
    case 1: return flip_h(b);
    case 2: return flip_v(b);
    case 3: return flip_h(flip_v(b));
  }
  return b;
}
__device__ __forceinline__ unsigned long long empty_mask(unsigned long long x) {
  x |= (x >> 2) & 0x3333333333333333ULL;
  x |= (x >> 1);
  return ~x & 0x1111111111111111ULL;
}

struct Tables {
  const unsigned short* row_left;
  const unsigned short* row_right;
  const unsigned long long* col_up;
  const unsigned long long* col_down;
  const unsigned int* score;
};

__device__ __forceinline__ unsigned long long dmove(const Tables& T, unsigned long long b, int dir, unsigned int& sc) {
  sc = 0;
  unsigned long long r;
  if (dir == 1 || dir == 3) {
    const unsigned short* tbl = dir == 3 ? T.row_left : T.row_right;
    r = 0;
    for (int i = 0; i < 4; i++) {
      unsigned row = (b >> (16 * i)) & 0xFFFF;
      r |= (unsigned long long)__ldg(tbl + row) << (16 * i);
      sc += __ldg(T.score + row);
    }
  } else {
    const unsigned long long* tbl = dir == 0 ? T.col_up : T.col_down;
    unsigned long long t = transpose(b);
    r = b;
    for (int i = 0; i < 4; i++) {
      unsigned col = (t >> (16 * i)) & 0xFFFF;
      r ^= __ldg(tbl + col) << (4 * i);
      sc += __ldg(T.score + col);
    }
  }
  return r;
}

__device__ __forceinline__ unsigned int ranks_present(unsigned long long b) {
  unsigned int m = 0;
  for (int i = 0; i < 16; i++, b >>= 4) m |= 1u << (b & 0xF);
  return m;
}
__device__ __forceinline__ bool holds(unsigned int m, unsigned int exact, int min_rank) {
  return (m & exact) == exact && (min_rank == 0 || (m >> min_rank) != 0);
}
__device__ __forceinline__ unsigned int dtile_sum(unsigned long long b) {
  unsigned int s = 0;
  for (int i = 0; i < 16; i++, b >>= 4) {
    unsigned int r = b & 0xF;
    s += r ? 1u << r : 0;
  }
  return s;
}
__device__ __forceinline__ int max_rank_of(unsigned long long b) {
  int m = 0;
  for (int i = 0; i < 16; i++, b >>= 4) m = max(m, (int)(b & 0xF));
  return m;
}
__device__ __forceinline__ int stage_of(unsigned long long b) {
  if (C.nsums > 0) {
    unsigned int s = dtile_sum(b);
    int st = 0;
    while (st < C.nsums && (s >= C.sums[st] || (C.sum_or_rank[st] && max_rank_of(b) >= C.sum_or_rank[st]))) st++;
    return st;
  }
  if (C.nconds == 0) return 0;
  unsigned int m = ranks_present(b);
  int st = 0;
  for (int k = 0; k < C.nconds; k++)
    if (holds(m, C.cond_exact[k], C.cond_min[k])) st = k + 1;
  return st;
}
__device__ __forceinline__ bool collect_cond(unsigned long long b) {
  if (C.collect_sum) return dtile_sum(b) >= C.collect_sum;
  return holds(ranks_present(b), C.collect_exact, C.collect_min);
}
// tile downgrading (same as eval_view in search.h)
__device__ __forceinline__ unsigned long long view_of(unsigned long long b) {
  if (!C.downgrade) return b;
  unsigned long long x = b & (b >> 1) & (b >> 2) & (b >> 3) & 0x1111111111111111ULL;
  if (!x) return b;
  unsigned int m = ranks_present(b);
  int gap = -1;
  for (int k = 14; k >= C.min_gap; k--)
    if (!(m >> k & 1)) { gap = k; break; }
  if (gap < 0) return b;
  unsigned long long r = 0;
  for (int i = 0; i < 16; i++) {
    int v = (b >> (4 * i)) & 0xF;
    if (v > gap) v--;
    r |= (unsigned long long)v << (4 * i);
  }
  return r;
}

__device__ __forceinline__ void syms(unsigned long long b, unsigned long long s[8]) {
  unsigned long long t = transpose(b);
  s[0] = b; s[1] = flip_h(b); s[2] = flip_v(b); s[3] = flip_h(s[2]);
  s[4] = t; s[5] = flip_h(t); s[6] = flip_v(t); s[7] = flip_h(s[6]);
}
__device__ __forceinline__ unsigned int index_of(unsigned long long b, int p) {
  unsigned int idx = 0;
  for (int j = 0; j < C.ncell[p]; j++) idx |= (unsigned int)((b >> (4 * C.cells[p][j])) & 0xF) << (4 * j);
  return idx;
}

// value of an afterstate
__device__ float value(unsigned long long as, const WE* wt, const float* __restrict__ wf) {
  unsigned long long v = view_of(as);
  int st = stage_of(v);
  unsigned long long s[8];
  syms(v, s);
  float sum = 0;
  if (st == C.train_stage) {
    for (int p = 0; p < C.np; p++) {
      const WE* t = wt + C.offset[p];
#pragma unroll
      for (int k = 0; k < 8; k++) sum += __ldcg(&t[index_of(s[k], p)].w);
    }
  } else {
    const float* base = C.stage_w[st];
    for (int p = 0; p < C.np; p++) {
      const float* t = base + C.offset[p];
#pragma unroll
      for (int k = 0; k < 8; k++) sum += __ldg(&t[index_of(s[k], p)]);
    }
  }
  return sum;
}

// Value used by the policy: the student's value, or with a teacher, the teacher's table for
// the trained stage (other stages are shared).
__device__ float policy_value(unsigned long long as, const WE* wt, const float* __restrict__ wf) {
  if (!C.teacher_w) return value(as, wt, wf);
  unsigned long long v = view_of(as);
  int st = stage_of(v);
  const float* base = st == C.train_stage ? C.teacher_w : C.stage_w[st];
  unsigned long long s[8];
  syms(v, s);
  float sum = 0;
  for (int p = 0; p < C.np; p++) {
    const float* t = base + C.offset[p];
#pragma unroll
    for (int k = 0; k < 8; k++) sum += __ldg(&t[index_of(s[k], p)]);
  }
  return sum;
}

// Batched update, phase 1: scatter this transition's TD error into per-weight
// accumulators (sum, |sum|, count); the first toucher of a weight records it.
struct Grad {
  unsigned int* touched;
  unsigned int* ntouched;
  unsigned int cap;  // capacity of touched (excess first-touches are dropped instead of overflowing)
};
__device__ void learn(unsigned long long as, float target, WE* wt, const Grad& G) {
  unsigned long long v = view_of(as);
  if (stage_of(v) != C.train_stage) return;
  unsigned long long s[8];
  syms(v, s);
  unsigned int idx[MAXP * 8];
  float cur = 0;
  int F = 0;
  for (int p = 0; p < C.np; p++) {
    for (int k = 0; k < 8; k++) {
      unsigned int i = (unsigned int)C.offset[p] + index_of(s[k], p);
      idx[F++] = i;
      cur += __ldcg(&wt[i].w);
    }
  }
  float err = target - cur, aerr = fabsf(err);
  for (int f = 0; f < F; f++) {
    unsigned int i = idx[f];
    if (atomicAdd(&wt[i].gcnt, 1u) == 0) {
      unsigned int slot = atomicAdd(G.ntouched, 1u);
      if (slot < G.cap) G.touched[slot] = i;
    }
    atomicAdd(&wt[i].gsum, err);
    if (C.tc) atomicAdd(&wt[i].gabs, aerr);
  }
}

// Batched update, phase 2: each touched weight moves by the mean error of the
// transitions that touched it (TC: scaled by its coherence |E|/A).
__global__ void k_apply(WE* wt, Grad G) {
  unsigned int n = min(*G.ntouched, G.cap);
  for (unsigned int t = blockIdx.x * blockDim.x + threadIdx.x; t < n; t += gridDim.x * blockDim.x) {
    unsigned int i = G.touched[t];
    WE e = wt[i];
    float sum = e.gsum, ab = e.gabs;
    unsigned int c = e.gcnt;
    float mean = sum / c;
    float fc = (float)c;
    mean *= C.upd_mode == 1 ? fc : C.upd_mode == 2 ? fminf(fc, C.upd_cap) : C.upd_mode == 3 ? sqrtf(fc) : 1.0f;
    if (C.tc) {
      float rate = e.a > 0 ? fabsf(e.e) / e.a : 1.0f;
      e.w += C.lr * rate * mean;
      e.e = e.e * C.tc_forget + (C.tc_mean ? sum / fc : sum);
      e.a = e.a * C.tc_forget + (C.tc_mean ? ab / fc : ab);
    } else {
      e.w += C.lr * mean;
    }
    e.gsum = 0;
    e.gabs = 0;
    e.gcnt = 0;
    wt[i] = e;
  }
}

__device__ __forceinline__ int max_rank(unsigned long long b) {
  int m = 0;
  for (int i = 0; i < 16; i++, b >>= 4) m = max(m, (int)(b & 0xF));
  return m;
}
__device__ __forceinline__ int corner_max(unsigned long long b) {
  return max(max((int)(b & 0xF), (int)((b >> 12) & 0xF)), max((int)((b >> 48) & 0xF), (int)(b >> 60)));
}
// Corner lock (C.corner_lock): the rank that must stay in a corner after a move from `s`, or 0.
__device__ __forceinline__ int lock_rank(unsigned long long s) {
  if (!C.corner_lock) return 0;
  int m = max_rank(s);
  return (m >= C.corner_lock && corner_max(s) == m) ? m : 0;
}

__device__ unsigned long long g_eg_moves;  // table moves played (for the log)

// The endgame table's move for state s (real frame) and its success probability, or -1 when s
// is not a snake ending with a known table entry (see eg::Snake::match).
__device__ int eg_move(const Tables& T, unsigned long long s, float* pout) {
  float best = -1.0f;
  int best_d = -1;
  for (int j = 0; j < 8; j++) {
    unsigned long long t = dsym(s, j);
    int prev = (int)((t >> (4 * EG_PATH[0])) & 0xF);
    if (prev == 0 || prev != max_rank(t)) continue;
    int k = 1, gaps = 0;
    while (k < 16) {
      int v = (int)((t >> (4 * EG_PATH[k])) & 0xF);
      bool step_ok = v == prev - 1 || (gaps < EG.full - 1 && v == prev - 2);
      if (v == 0 || v >= prev || (EG.full && !step_ok)) break;
      gaps += v == prev - 2;
      prev = v;
      k++;
    }
    int kk = -1, r = 0;
    for (int q = EG.kmin; q <= k && kk < 0; q++) {
      int rr = (int)((t >> (4 * EG_PATH[q - 1])) & 0xF);
      if (rr > EG.max_rank[q]) continue;
      bool ok = true;
      for (int i = q; i < 16 && ok; i++) ok = (int)((t >> (4 * EG_PATH[i])) & 0xF) <= rr;
      if (ok) kk = q, r = rr;
    }
    if (kk < 0) continue;
    int ti = EG.table_of[kk][r];
    if (ti < 0) continue;
    const EgTable& tb = EG.t[ti];
    unsigned long long idx = 0;
    for (int c = 0; c < tb.n; c++) idx += ((t >> (4 * tb.cell[c])) & 0xF) * tb.radix[c];
    unsigned long long ch = idx / EG.chunk;
    if (ch >= tb.nchunks) continue;
    int sl = tb.slot[ch];
    if (sl < 0) continue;
    unsigned short e = tb.data[(unsigned long long)sl * EG.chunk + idx % EG.chunk];
    if (e == 0xFFFF) continue;
    float p = (e & 0x3FFF) * (1.0f / 16000.0f);
    if (p <= best) continue;
    unsigned int sc;
    unsigned long long a = dmove(T, t, e >> 14, sc);
    if (a == t) continue;
    for (int d = 0; d < 4; d++) {
      unsigned long long ad = dmove(T, s, d, sc);
      if (ad != s && dsym(ad, j) == a) {
        best = p, best_d = d;
        break;
      }
    }
  }
  *pout = best;
  return best_d;
}

// Expectimax value of afterstate `as` searched `depth` more moves deep: the expectation over
// its spawns of the best next move r + (depth > 1 ? lookahead(next, depth - 1) : V(next)).
// The policy's lookahead (see policy_depth). One level is a plain loop (the common case,
// used in training); deeper levels recurse. No transposition table.
template <bool DEEP>
__device__ float lookahead_t(const Tables& T, unsigned long long as, int depth, const WE* wt,
                             const float* __restrict__ wf);
__device__ float lookahead_deep(const Tables& T, unsigned long long as, int depth, const WE* wt,
                                const float* __restrict__ wf) {
  return lookahead_t<true>(T, as, depth, wt, wf);
}
template <bool DEEP>
__device__ float lookahead_t(const Tables& T, unsigned long long as, int depth, const WE* wt,
                             const float* __restrict__ wf) {
  unsigned long long em = empty_mask(as);
  int n = __popcll(em);
  if (n == 0) return 0;
  float sum = 0;
  const int tmax = C.policy_no4 ? 1 : 2;
  for (unsigned long long m = em; m; m &= m - 1) {
    unsigned long long bit = m & (~m + 1);
    for (int t = 1; t <= tmax; t++) {
      unsigned long long s2 = as | (bit * t);
      float b = 0, bl = 0;  // best over all moves / over moves the corner lock allows
      bool anym = false, anyl = false;
      int lr = lock_rank(s2);
      for (int d = 0; d < 4; d++) {
        unsigned int r;
        unsigned long long a2 = dmove(T, s2, d, r);
        if (a2 == s2) continue;
        float v = (float)r + ((DEEP && depth > 1) ? lookahead_deep(T, a2, depth - 1, wt, wf) : policy_value(a2, wt, wf));
        if (!anym || v > b) b = v, anym = true;
        if (corner_max(a2) >= lr && (!anyl || v > bl)) bl = v, anyl = true;
      }
      if (anyl) b = bl;
      sum += (t == 2 ? 0.1f : (C.policy_no4 ? 1.0f : 0.9f)) * b;
    }
  }
  return sum / n;
}
__device__ __forceinline__ float lookahead(const Tables& T, unsigned long long as, int depth, const WE* wt,
                                           const float* __restrict__ wf) {
  return depth > 1 ? lookahead_deep(T, as, depth, wt, wf) : lookahead_t<false>(T, as, 1, wt, wf);
}

__device__ __forceinline__ unsigned long long spawn(unsigned long long b, unsigned long long& rng) {
  unsigned long long em = empty_mask(b);
  int n = __popcll(em);
  if (!n) return b;
  unsigned int k = below(rng, n);
  // k-th set bit
  for (unsigned int i = 0; i < k; i++) em &= em - 1;
  unsigned long long bit = em & (~em + 1);
  unsigned long long tile = below(rng, 10) == 0 ? 2 : 1;
  return b | (bit * tile);
}

__device__ __forceinline__ unsigned long long new_start(unsigned long long& rng, const unsigned long long* pool) {
  if (C.pool_n > 0 && (splitmix(rng) >> 40) * (1.0f / 16777216.0f) < C.pool_prob) return pool[below(rng, C.pool_n)];
  return spawn(spawn(0, rng), rng);
}


__global__ void k_init(GameState* g, int n, unsigned long long seed, const unsigned long long* pool) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n) return;
  GameState s;
  s.rng = seed ^ (0x9E3779B97F4A7C15ULL * (i + 1));
  splitmix(s.rng);
  s.board = new_start(s.rng, pool);
  s.nring = 0;
  s.head = 0;
  s.score = 0;
  s.moves = 0;
  s.collected = 0;
  s.made65536 = 0;
  g[i] = s;
}

#define MAXBRANCH 16
// The 1-ply policy's move from state s (corner lock; a known winning table move replaces it), for side branches;
// false at game over.
__device__ bool greedy_choice(const Tables& T, unsigned long long s, const WE* wt, const float* __restrict__ wf,
                              unsigned long long& best_as, unsigned int& best_r, float& best) {
  unsigned long long cas[4];
  unsigned int cr[4];
  float cv[4];
  int nc = 0, nlocked = 0;
  const int lr = lock_rank(s);
  for (int d = 0; d < 4; d++) {
    unsigned int r;
    unsigned long long as = dmove(T, s, d, r);
    if (as == s) continue;
    cas[nc] = as, cr[nc] = r, nc++;
    nlocked += corner_max(as) < lr;
  }
  if (nlocked && nlocked < nc) {
    int k = 0;
    for (int a = 0; a < nc; a++)
      if (corner_max(cas[a]) >= lr) cas[k] = cas[a], cr[k] = cr[a], k++;
    nc = k;
  }
  if (!nc) return false;
  best = -1e30f;
  for (int a = 0; a < nc; a++) {
    float v = (float)cr[a] + policy_value(cas[a], wt, wf);
    cv[a] = v;
    if (v > best) best = v, best_as = cas[a], best_r = cr[a];
  }
  if (EG.on) {
    float tp;
    int td = eg_move(T, s, &tp);
    if (td >= 0 && tp >= EG.min_p) {
      unsigned int tr;
      unsigned long long tas = dmove(T, s, td, tr);
      for (int a = 0; a < nc; a++)
        if (cas[a] == tas) { best_as = tas, best_r = tr, best = cv[a]; break; }
    }
  }
  return true;
}

__global__ void k_step(GameState* games, int n, int steps, Tables T, WE* wt, Grad G, Ring R,
                       const float* __restrict__ wf,
                       const unsigned long long* __restrict__ pool, EpisodeRec* recs, unsigned int* nrec,
                       unsigned int rec_cap, unsigned long long* coll, unsigned int* ncoll, unsigned int coll_cap,
                       unsigned long long* total_moves, int* stop_new) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n) return;
  GameState g = games[i];
  unsigned long long moves_done = 0;
  for (int step = 0; step < steps; step++) {
    if (g.board == 0) break;  // retired game
    unsigned long long s = g.board;
    if (C.collect_every > 0 ? (g.moves % C.collect_every == C.collect_every - 1)
                            : (C.collect && !g.collected && collect_cond(s))) {
      g.collected = 1;
      unsigned int k = atomicAdd(ncoll, 1u);
      if (k < coll_cap) coll[k] = s;
    }
    float best = -1e30f;
    unsigned long long best_as = 0;
    unsigned int best_r = 0;
    bool any = false;
    unsigned long long cas[4];
    unsigned int cr[4];
    float cv[4];
    int nc = 0, nlocked = 0;
    const int lr = lock_rank(s);
    for (int d = 0; d < 4; d++) {
      unsigned int r;
      unsigned long long as = dmove(T, s, d, r);
      if (as == s) continue;
      cas[nc] = as, cr[nc] = r, nc++;
      nlocked += corner_max(as) < lr;
    }
    if (nlocked && nlocked < nc) {  // corner lock: drop the moves that take the max tile out of its corner
      int k = 0;
      for (int a = 0; a < nc; a++)
        if (corner_max(cas[a]) >= lr) cas[k] = cas[a], cr[k] = cr[a], k++;
      nc = k;
    }
    for (int a = 0; a < nc; a++) {
      float v = (float)cr[a] + policy_value(cas[a], wt, wf);
      cv[a] = v;
      if (!any || v > best) best = v, best_as = cas[a], best_r = cr[a], any = true;
    }
    // endgame table: in a snake ending it knows how to win, its move is played
    bool table_played = false;
    if (EG.on && nc >= 1) {
      float tp;
      int td = eg_move(T, s, &tp);
      if (td >= 0 && tp >= EG.min_p) {
        unsigned int tr;
        unsigned long long tas = dmove(T, s, td, tr);
        for (int a = 0; a < nc; a++)
          if (cas[a] == tas) {
            best_as = tas, best_r = tr, best = cv[a], table_played = true;
            atomicAdd(&g_eg_moves, 1ULL);
            break;
          }
      }
    }
    // deeper policy: re-rank the best moves by a one-move lookahead; `best` stays the
    // 1-ply value r + V of the chosen afterstate (the TD machinery needs V(afterstate))
    if (!table_played && C.policy_depth >= 2 && nc >= 2 && __popcll(empty_mask(s)) <= C.policy_max_empty &&
        (C.policy_mix >= 1.0f || (splitmix(g.rng) >> 40) * (1.0f / 16777216.0f) < C.policy_mix)) {
      for (int a = 0; a < nc; a++)  // sort candidates by 1-ply value, descending
        for (int b = a + 1; b < nc; b++)
          if (cv[b] > cv[a]) {
            float tv = cv[a]; cv[a] = cv[b]; cv[b] = tv;
            unsigned long long ta = cas[a]; cas[a] = cas[b]; cas[b] = ta;
            unsigned int tr = cr[a]; cr[a] = cr[b]; cr[b] = tr;
          }
      int keep = nc < C.policy_beam ? nc : C.policy_beam;
      float b2 = -1e30f;
      for (int a = 0; a < keep; a++) {
        float la = lookahead(T, cas[a], C.policy_depth - 1, wt, wf);
        float v2 = (float)cr[a] + la;
        if (v2 > b2) b2 = v2, best_as = cas[a], best_r = cr[a], best = cv[a];
        if (C.learn && C.train_all_root) learn(cas[a], la, wt, G);  // V(afterstate) <- its expectimax backup
      }
    }
    // teacher-student: the teacher chose the move; the TD machinery needs the student's value
    if (C.teacher_w && any) best = (float)best_r + value(best_as, wt, wf);
    const int H1 = C.horizon + 1;
    // leaving the trained stage: bootstrap pending afterstates from the next stage's value
    // (the stage can also drop, when two 32768s merge into a 65536 stored as rank 15)
    bool boundary = any && C.stop_at_boundary && stage_of(view_of(best_as)) != C.train_stage;
    if (!any || boundary) {
      // every pending afterstate gets its lambda-return: exact at a terminal state,
      // bootstrapped from V(boundary afterstate) when stopping at the stage boundary
      if (C.learn) {
        float Gt = 0;
        if (boundary) Gt = best_r + (best - (float)best_r);  // target of the last pending: r_t + V(as_t)
        for (int k = g.nring - 1; k >= 0; k--) {
          int slot = (g.head + k) % H1;
          size_t o = (size_t)slot * R.n + i;
          learn(R.as[o], Gt, wt, G);
          Gt = R.cut[o] ? R.r[o] + R.v[o] : R.r[o] + (1 - C.lambda) * R.v[o] + C.lambda * Gt;
        }
      }
      unsigned int k = atomicAdd(nrec, 1u);
      if (boundary) g.score += best_r;
      if (k < rec_cap) {
        unsigned long long fin = boundary ? best_as : s;
        recs[k] = EpisodeRec{g.score, g.moves, max_rank(fin), dtile_sum(fin), boundary ? 1 : 0,
                             g.made65536 || best_r >= 65536u};
      }
      if (*stop_new) { g.board = 0; break; }
      g.board = new_start(g.rng, pool);
      g.nring = 0;
      g.head = 0;
      g.score = 0;
      g.moves = 0;
      g.collected = 0;
      g.made65536 = 0;
      continue;
    }
    // exploration: sometimes play a random other legal move. Its afterstate is trained like any
    // other (toward the greedy continuation from there); the previous afterstate's target still
    // uses the greedy move's value, and the lambda-return is cut at this step.
    unsigned long long play_as = best_as;
    unsigned int play_r = best_r;
    bool explored = false;
    if (C.explore > 0 && !table_played && nc >= 2 && (splitmix(g.rng) >> 40) * (1.0f / 16777216.0f) < C.explore) {
      int j = (int)below(g.rng, (unsigned)(nc - 1));
      int seen = 0;
      for (int a = 0; a < nc; a++) {
        if (cas[a] == best_as) continue;
        if (seen++ == j) { play_as = cas[a], play_r = cr[a]; break; }
      }
      explored = play_as != best_as;
    }
    // side branch: train a random non-chosen candidate and its greedy continuation (the episode itself is unchanged)
    if (C.learn && C.branch_p > 0 && !table_played && nc >= 2 &&
        (splitmix(g.rng) >> 40) * (1.0f / 16777216.0f) < C.branch_p) {
      int j = (int)below(g.rng, (unsigned)(nc - 1)), alt = -1;
      for (int a = 0, seen = 0; a < nc; a++) {
        if (cas[a] == best_as) continue;
        if (seen++ == j) { alt = a; break; }
      }
      if (alt >= 0) {
        unsigned long long bp[MAXBRANCH + 1];
        float brw[MAXBRANCH + 1];
        int nb = 0;
        bp[nb] = cas[alt], brw[nb] = (float)cr[alt], nb++;
        unsigned long long bs = spawn(cas[alt], g.rng);
        float G0 = 0;
        for (int k = 0;; k++) {
          unsigned long long bas;
          unsigned int brr;
          float bv;
          if (!greedy_choice(T, bs, wt, wf, bas, brr, bv)) { G0 = 0; break; }
          if (C.stop_at_boundary && stage_of(view_of(bas)) != C.train_stage) { G0 = bv; break; }
          if (k >= C.branch_len) { G0 = bv; break; }
          bp[nb] = bas, brw[nb] = (float)brr, nb++;
          bs = spawn(bas, g.rng);
        }
        float Gt = G0;
        for (int k = nb - 1; k >= 0; k--) {  // backward lambda-return sweep (values before this round's update)
          learn(bp[k], Gt, wt, G);
          float v = value(bp[k], wt, wf);
          Gt = brw[k] + (1 - C.lambda) * v + C.lambda * Gt;
        }
      }
    }
    if (C.learn) {
      // push (as_t, r_t, V(as_t)); once H+1 are pending, the oldest gets its target
      int slot = (g.head + g.nring) % H1;
      size_t o = (size_t)slot * R.n + i;
      R.as[o] = play_as;
      R.r[o] = (float)best_r;
      R.v[o] = best - (float)best_r;
      R.cut[o] = explored;
      g.nring++;
      if (g.nring == H1) {
        float Gt = R.v[o];
        for (int k = g.nring - 1; k >= 1; k--) {
          size_t ok = (size_t)((g.head + k) % H1) * R.n + i;
          Gt = R.cut[ok] ? R.r[ok] + R.v[ok] : R.r[ok] + (1 - C.lambda) * R.v[ok] + C.lambda * Gt;
        }
        learn(R.as[(size_t)g.head * R.n + i], Gt, wt, G);
        g.head = (g.head + 1) % H1;
        g.nring--;
      }
    }
    g.score += play_r;
    if (play_r >= 65536u) g.made65536 = 1;
    g.moves++;
    moves_done++;
    g.board = spawn(play_as, g.rng);
  }
  games[i] = g;
  atomicAdd(total_moves, moves_done);
}

// ---------------- host ----------------
struct Config {
  string patterns = "4x6", load, save, checkpoint, resume, stages, pool, collect, collect_when = "14+";
  int collect_every = 0;  // >0: record every collect_every-th state instead of the first match of collect_when
  int train_stage = 0;
  double pool_prob = 1.0;
  long pool_last = 0;
  long episodes = 1000000;
  double alpha = 1.0;
  bool tc = true;
  bool learn = true;
  bool downgrade = true;
  int min_gap = 10;
  double init = 0;
  double opt_fill = 0;  // >0: weights that are exactly 0 (never visited) start at opt_fill/F
  string fresh;         // comma-separated stages that start at init/F instead of the loaded weights
  string teacher;       // weight file whose trained-stage table drives the policy (teacher-student)
  double explore = 0;   // probability of an exploratory (random other) move
  double policy_mix = 1.0;  // probability that a step uses the deeper policy
  double tc_forget = 1.0;   // decay of the TC accumulators per update
  bool tc_mean = false;     // TC accumulators per round: mean error instead of the sum (DevCfg::tc_mean)
  double branch_p = 0;      // --branch P L (DevCfg::branch_p)
  int branch_len = 8;
  double tc_decay = 1.0;
  double lambda = 0.5;
  int horizon = 3;
  bool stop_at_boundary = false;
  int policy_depth = 1, policy_beam = 4, policy_max_empty = 16;
  int corner_lock = 0;  // keep a max tile of at least this rank in its corner (0 = off)
  string eg_dir;        // endgame tables (play --endgame-dir) whose moves the policy plays
  float eg_min = 0.5f;  // ... when they win with at least this probability
  int eg_min_rank = 1;  // load only the tables whose goal rank is at least this (saves GPU memory)
  string update_scale = "mean";  // see DevCfg::upd_mode: mean | sum | capK | sqrt
  bool skip_lower = false;  // do not load the stages below the trained one onto the GPU (episodes that
                            // all start in or after the trained stage never reach them: the tile sum
                            // and the max tile never decrease); saving copies them from --load
  int eg_full = 2;      // which snake endings (see eg::Snake)
  bool train_all_root = false;
  bool policy_no4 = false;
  long log_every = 20000;
  long save_every = 0;
  int games = 1 << 17;
  int steps = 1;
  uint64_t seed = 1;
};

// Uploads the endgame tables saved in dir (eg::Table::save files of eg::Snake) to the GPU and
// fills the EG constant. Each file is read straight into device memory, chunk by chunk.
static void load_endgame(const string& dir, int full, float min_p, int min_rank) {
  EgCfg eg;
  memset(&eg, 0, sizeof eg);
  memset(eg.table_of, -1, sizeof eg.table_of);
  eg.kmin = 6, eg.full = full, eg.min_p = min_p, eg.chunk = eg::Table::chunk_size();
  for (int k = 6; k <= 16; k++) eg.max_rank[k] = std::min(16 - k, k == 6 ? 9 : 8);
  int nt = 0;
  size_t bytes = 0;
  for (int k = 6; k <= 16; k++)
    for (int r = min_rank; r <= eg.max_rank[k] && nt < EG_MAXT; r++) {
      string path = dir + "/snake_k" + to_string(k) + "_r" + to_string(r) + ".egt";
      FILE* f = fopen(path.c_str(), "rb");
      if (!f) continue;
      uint64_t hdr[4];
      eg::Spec sp;
      board_t chain;
      if (fread(hdr, sizeof hdr, 1, f) != 1 || hdr[0] != 0x31544745ULL || hdr[1] != eg.chunk ||
          fread(&sp, sizeof sp, 1, f) != 1 || fread(&chain, sizeof chain, 1, f) != 1) {
        fprintf(stderr, "endgame: bad table file %s\n", path.c_str());
        exit(1);
      }
      EgTable& t = eg.t[nt];
      t.n = 0;
      unsigned long long size = 1;
      for (int i = 0; i < 16; i++) {
        int c = sp.order[0] < 0 ? i : sp.order[i];
        if (sp.locked >> c & 1) continue;
        t.cell[t.n] = c, t.radix[t.n] = size, t.n++;
        size *= (unsigned long long)(sp.cap[c] + 1);
        t.cap = sp.cap[c];
      }
      t.nchunks = hdr[2];
      vector<int> slot(hdr[2], -1);
      unsigned short* dd;
      CK(cudaMalloc(&dd, hdr[3] * eg.chunk * sizeof(unsigned short)));
      vector<unsigned short> buf(eg.chunk);
      for (uint64_t i = 0; i < hdr[3]; i++) {
        uint64_t idx;
        if (fread(&idx, sizeof idx, 1, f) != 1 || idx >= hdr[2] ||
            fread(buf.data(), sizeof(unsigned short), eg.chunk, f) != eg.chunk) {
          fprintf(stderr, "endgame: truncated %s\n", path.c_str());
          exit(1);
        }
        slot[idx] = (int)i;
        CK(cudaMemcpy(dd + i * eg.chunk, buf.data(), eg.chunk * sizeof(unsigned short), cudaMemcpyHostToDevice));
      }
      fclose(f);
      int* ds;
      CK(cudaMalloc(&ds, slot.size() * sizeof(int)));
      CK(cudaMemcpy(ds, slot.data(), slot.size() * sizeof(int), cudaMemcpyHostToDevice));
      t.slot = ds, t.data = dd;
      eg.table_of[k][r] = (signed char)nt++;
      bytes += hdr[3] * eg.chunk * sizeof(unsigned short) + slot.size() * sizeof(int);
      printf("endgame table k=%d r=%d: %llu chunks\n", k, r, (unsigned long long)hdr[3]);
    }
  eg.on = nt > 0;
  CK(cudaMemcpyToSymbol(EG, &eg, sizeof eg));
  printf("endgame: %d tables from %s on the GPU (%.0f MB), played when p >= %.2f\n", nt, dir.c_str(), bytes / 1e6,
         min_p);
}

int main(int argc, char** argv) {
  Config cfg;
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
    else if (a == "--collect-every") cfg.collect_every = stoi(next());
    else if (a == "--episodes") cfg.episodes = stol(next());
    else if (a == "--alpha") cfg.alpha = stod(next());
    else if (a == "--td") cfg.tc = false;
    else if (a == "--tc") cfg.tc = true;
    else if (a == "--no-learn") cfg.learn = false;
    else if (a == "--no-downgrade") cfg.downgrade = false;
    else if (a == "--min-gap") cfg.min_gap = stoi(next());
    else if (a == "--init") cfg.init = stod(next());
    else if (a == "--opt-fill") cfg.opt_fill = stod(next());
    else if (a == "--fresh") cfg.fresh = next();
    else if (a == "--teacher") cfg.teacher = next();
    else if (a == "--explore") cfg.explore = stod(next());
    else if (a == "--policy-mix") cfg.policy_mix = stod(next());
    else if (a == "--tc-forget") cfg.tc_forget = stod(next());
    else if (a == "--tc-mean") cfg.tc_mean = true;
    else if (a == "--branch") { cfg.branch_p = stod(next()); cfg.branch_len = stoi(next()); }
    else if (a == "--corner-lock") cfg.corner_lock = stoi(next());
    else if (a == "--endgame-dir") cfg.eg_dir = next();
    else if (a == "--endgame-min") cfg.eg_min = stof(next());
    else if (a == "--endgame-full") cfg.eg_full = stoi(next());
    else if (a == "--endgame-min-rank") cfg.eg_min_rank = stoi(next());
    else if (a == "--skip-lower") cfg.skip_lower = true;
    else if (a == "--update-scale") cfg.update_scale = next();
    else if (a == "--tc-decay") cfg.tc_decay = stod(next());
    else if (a == "--lambda") cfg.lambda = stod(next());
    else if (a == "--horizon") cfg.horizon = stoi(next());
    else if (a == "--stop-at-boundary") cfg.stop_at_boundary = true;
    else if (a == "--policy-depth") cfg.policy_depth = stoi(next());
    else if (a == "--policy-beam") cfg.policy_beam = stoi(next());
    else if (a == "--policy-no4") cfg.policy_no4 = true;
    else if (a == "--policy-max-empty") cfg.policy_max_empty = stoi(next());
    else if (a == "--train-all-root") cfg.train_all_root = true;
    else if (a == "--log") cfg.log_every = stol(next());
    else if (a == "--save-every") cfg.save_every = stol(next());
    else if (a == "--games") cfg.games = stoi(next());
    else if (a == "--steps") cfg.steps = stoi(next());
    else if (a == "--seed") cfg.seed = stoull(next());
    else { fprintf(stderr, "unknown option %s\n", a.c_str()); return 1; }
  }
  StageFn sf;
  if (!cfg.stages.empty()) sf = StageFn::parse(cfg.stages);
  if (!sf.sums.empty()) cfg.downgrade = false;  // downgrading would change the tile sum
  int S = sf.count();

  // ---- weight metadata (weights are streamed straight to the GPU) ----
  vector<nt::Pattern> pats;
  int file_stages = 0;
  long data_pos = 0;
  if (!cfg.load.empty()) {
    FILE* f = fopen(cfg.load.c_str(), "rb");
    uint32_t hdr[3];
    if (!f || fread(hdr, sizeof hdr, 1, f) != 1 || hdr[0] != 0x32303438u) { fprintf(stderr, "bad weight file\n"); return 1; }
    string ps(hdr[1], ' ');
    if (fread(&ps[0], 1, ps.size(), f) != ps.size()) { fprintf(stderr, "bad weight file\n"); return 1; }
    pats = nt::parse_patterns(ps);
    file_stages = hdr[2];
    data_pos = ftell(f);
    fclose(f);
  } else {
    pats = nt::parse_patterns(cfg.patterns);
  }
  vector<unsigned long long> offset;
  unsigned long long stage_size = 0;
  for (auto& p : pats) offset.push_back(stage_size), stage_size += p.size;
  int F = 8 * (int)pats.size();
  if (pats.size() > (size_t)MAXP) { fprintf(stderr, "too many patterns\n"); return 1; }

  // ---- device config ----
  DevCfg dc{};
  dc.np = (int)pats.size();
  for (int p = 0; p < dc.np; p++) {
    dc.ncell[p] = (int)pats[p].cells.size();
    for (int j = 0; j < dc.ncell[p]; j++) dc.cells[p][j] = pats[p].cells[j];
    dc.offset[p] = offset[p];
  }
  dc.stage_size = stage_size;
  if ((int)sf.conds.size() > MAXB || (int)sf.sums.size() > MAXB) { fprintf(stderr, "too many stages\n"); return 1; }
  dc.nconds = (int)sf.conds.size();
  for (int k = 0; k < dc.nconds; k++) dc.cond_exact[k] = sf.conds[k].exact, dc.cond_min[k] = sf.conds[k].min_rank;
  dc.nsums = (int)sf.sums.size();
  for (int k = 0; k < dc.nsums; k++) dc.sums[k] = sf.sums[k], dc.sum_or_rank[k] = sf.sum_or_rank[k];
  dc.train_stage = cfg.train_stage;
  dc.tc = cfg.tc;
  dc.lr = (float)(cfg.alpha / F);
  dc.downgrade = cfg.downgrade;
  dc.min_gap = cfg.min_gap;
  dc.pool_prob = (float)cfg.pool_prob;
  dc.learn = cfg.learn;
  dc.lambda = (float)cfg.lambda;
  dc.stop_at_boundary = cfg.stop_at_boundary;
  dc.policy_depth = cfg.policy_depth;
  dc.policy_beam = cfg.policy_beam;
  dc.policy_no4 = cfg.policy_no4;
  dc.policy_max_empty = cfg.policy_max_empty;
  dc.train_all_root = cfg.train_all_root;
  dc.explore = (float)cfg.explore;
  dc.policy_mix = (float)cfg.policy_mix;
  dc.tc_forget = (float)cfg.tc_forget;
  dc.tc_mean = cfg.tc_mean ? 1 : 0;
  dc.branch_p = (float)cfg.branch_p;
  dc.branch_len = cfg.branch_len < MAXBRANCH ? cfg.branch_len : MAXBRANCH;
  dc.corner_lock = cfg.corner_lock;
  dc.upd_mode = 0, dc.upd_cap = 1;
  if (cfg.update_scale == "sum") dc.upd_mode = 1;
  else if (cfg.update_scale.rfind("cap", 0) == 0) dc.upd_mode = 2, dc.upd_cap = stof(cfg.update_scale.substr(3));
  else if (cfg.update_scale == "sqrt") dc.upd_mode = 3;
  else if (cfg.update_scale != "mean") { fprintf(stderr, "unknown --update-scale %s\n", cfg.update_scale.c_str()); return 1; }
  dc.horizon = cfg.horizon;
  dc.collect_every = cfg.collect.empty() ? 0 : cfg.collect_every;
  if (!cfg.collect.empty()) {
    StageFn cf = StageFn::parse(cfg.collect_when);
    dc.collect = 1;
    if (!cf.sums.empty()) {
      dc.collect_sum = cf.sums.back();
    } else {
      dc.collect_exact = cf.conds.back().exact;
      dc.collect_min = cf.conds.back().min_rank;
    }
  }

  vector<unsigned long long> pool;
  if (!cfg.pool.empty()) {
    FILE* f = fopen(cfg.pool.c_str(), "rb");
    if (!f) { fprintf(stderr, "cannot read pool %s\n", cfg.pool.c_str()); return 1; }
    unsigned long long b;
    while (fread(&b, sizeof b, 1, f) == 1) pool.push_back(b);
    fclose(f);
    if (cfg.pool_last > 0 && (long)pool.size() > cfg.pool_last) pool.erase(pool.begin(), pool.end() - cfg.pool_last);
    printf("pool: %zu start positions\n", pool.size());
  }
  dc.pool_n = (int)pool.size();
  CK(cudaMemcpyToSymbol(C, &dc, sizeof dc));
  if (!cfg.eg_dir.empty()) load_endgame(cfg.eg_dir, cfg.eg_full, cfg.eg_min, cfg.eg_min_rank);

  // ---- device memory ----
  Tables T;
  unsigned short *d_rl, *d_rr;
  unsigned long long *d_cu, *d_cd;
  unsigned int* d_sc;
  CK(cudaMalloc(&d_rl, 65536 * 2)); CK(cudaMalloc(&d_rr, 65536 * 2));
  CK(cudaMalloc(&d_cu, 65536 * 8)); CK(cudaMalloc(&d_cd, 65536 * 8));
  CK(cudaMalloc(&d_sc, 65536 * 4));
  CK(cudaMemcpy(d_rl, bb::T.row_left, 65536 * 2, cudaMemcpyHostToDevice));
  CK(cudaMemcpy(d_rr, bb::T.row_right, 65536 * 2, cudaMemcpyHostToDevice));
  CK(cudaMemcpy(d_cu, bb::T.col_up, 65536 * 8, cudaMemcpyHostToDevice));
  CK(cudaMemcpy(d_cd, bb::T.col_down, 65536 * 8, cudaMemcpyHostToDevice));
  CK(cudaMemcpy(d_sc, bb::T.score, 65536 * 4, cudaMemcpyHostToDevice));
  T.row_left = d_rl; T.row_right = d_rr; T.col_up = d_cu; T.col_down = d_cd; T.score = d_sc;

  // trained stage (WE) and frozen stages (float; the trained stage's slot is unused)
  WE* d_tw;
  CK(cudaMalloc(&d_tw, stage_size * sizeof(WE)));
  float* d_wf = nullptr;  // frozen stages only, packed; stage st lives at slot (st < train ? st : st - 1)
  const int lo = cfg.skip_lower ? cfg.train_stage : 0;  // first stage kept on the GPU
  if (cfg.skip_lower && (cfg.pool.empty() || cfg.pool_prob < 1.0)) {
    fprintf(stderr, "--skip-lower needs every episode to start from the pool\n");
    return 1;
  }
  auto slot = [&](int st) { return (size_t)(st < cfg.train_stage ? st - lo : st - 1 - lo) * stage_size; };
  if (S - lo > 1) CK(cudaMalloc(&d_wf, (size_t)(S - 1 - lo) * stage_size * sizeof(float)));
  for (int st = 0; st < S; st++) dc.stage_w[st] = (st == cfg.train_stage || st < lo) ? nullptr : d_wf + slot(st);
  CK(cudaMemcpyToSymbol(C, &dc, sizeof dc));
  {
    const size_t chunk = 1 << 22;
    vector<float> buf(chunk);
    vector<TCE> tbuf(chunk);
    vector<WE> wbuf(chunk);
    FILE* f = cfg.load.empty() ? nullptr : fopen(cfg.load.c_str(), "rb");
    float v0 = (float)(cfg.init / F);
    const float vfill = (float)(cfg.opt_fill / F);
    long filled = 0;
    vector<bool> fresh(S, false);
    for (size_t i = 0; i < cfg.fresh.size();) {
      size_t j = cfg.fresh.find(',', i);
      if (j == string::npos) j = cfg.fresh.size();
      int st = stoi(cfg.fresh.substr(i, j - i));
      if (st >= 0 && st < S) fresh[st] = true;
      i = j + 1;
    }
    for (int st = lo; st < S; st++) {
      if (f) fseek(f, data_pos + (long)min(st, file_stages - 1) * (long)(stage_size * sizeof(float)), SEEK_SET);
      for (size_t i = 0; i < stage_size; i += chunk) {
        size_t n = min(chunk, (size_t)stage_size - i);
        if (f && !fresh[st]) {
          if (fread(buf.data(), sizeof(float), n, f) != n) { fprintf(stderr, "short weight file\n"); return 1; }
          if (cfg.opt_fill > 0)
            for (size_t j = 0; j < n; j++)
              if (buf[j] == 0.0f) buf[j] = vfill, filled++;
        } else {
          fill(buf.begin(), buf.begin() + n, v0);
        }
        if (st == cfg.train_stage) {
          for (size_t j = 0; j < n; j++) wbuf[j] = WE{buf[j], 0, 0, 0, 0, 0};
          CK(cudaMemcpy(d_tw + i, wbuf.data(), n * sizeof(WE), cudaMemcpyHostToDevice));
        } else {
          CK(cudaMemcpy(d_wf + slot(st) + i, buf.data(), n * sizeof(float), cudaMemcpyHostToDevice));
        }
      }
    }
    if (f) fclose(f);
    if (!cfg.resume.empty()) {
      FILE* r = fopen(cfg.resume.c_str(), "rb");
      if (!r) { fprintf(stderr, "cannot resume from %s\n", cfg.resume.c_str()); return 1; }
      for (size_t i = 0; i < stage_size; i += chunk) {
        size_t n = min(chunk, (size_t)stage_size - i);
        if (fread(tbuf.data(), sizeof(TCE), n, r) != n) { fprintf(stderr, "short checkpoint\n"); return 1; }
        if (cfg.tc_decay != 1.0)
          for (size_t j = 0; j < n; j++) tbuf[j].e *= (float)cfg.tc_decay, tbuf[j].a *= (float)cfg.tc_decay;
        if (cfg.opt_fill > 0)
          for (size_t j = 0; j < n; j++)
            if (tbuf[j].w == 0.0f && tbuf[j].a == 0.0f) tbuf[j].w = vfill, filled++;
        for (size_t j = 0; j < n; j++) wbuf[j] = WE{tbuf[j].w, tbuf[j].e, tbuf[j].a, 0, 0, 0};
        CK(cudaMemcpy(d_tw + i, wbuf.data(), n * sizeof(WE), cudaMemcpyHostToDevice));
      }
      fclose(r);
    }
    if (cfg.opt_fill > 0) printf("optimistic fill: %ld never-visited weights set to %g\n", filled, vfill);
  }
  if (!cfg.teacher.empty()) {  // only the trained stage's table of the teacher is needed
    FILE* f = fopen(cfg.teacher.c_str(), "rb");
    uint32_t hdr[3];
    if (!f || fread(hdr, sizeof hdr, 1, f) != 1 || hdr[0] != 0x32303438u) { fprintf(stderr, "bad teacher file\n"); return 1; }
    string ps(hdr[1], ' ');
    if (fread(&ps[0], 1, ps.size(), f) != ps.size() || ps != nt::pattern_string(pats)) {
      fprintf(stderr, "teacher patterns differ\n");
      return 1;
    }
    int tst = min(cfg.train_stage, (int)hdr[2] - 1);
    fseek(f, (long)(ftell(f) + (long)tst * (long)(stage_size * sizeof(float))), SEEK_SET);
    float* d_teach;
    CK(cudaMalloc(&d_teach, stage_size * sizeof(float)));
    const size_t chunk = 1 << 22;
    vector<float> buf(chunk);
    for (size_t i = 0; i < stage_size; i += chunk) {
      size_t n = min(chunk, (size_t)stage_size - i);
      if (fread(buf.data(), sizeof(float), n, f) != n) { fprintf(stderr, "short teacher file\n"); return 1; }
      CK(cudaMemcpy(d_teach + i, buf.data(), n * sizeof(float), cudaMemcpyHostToDevice));
    }
    fclose(f);
    dc.teacher_w = d_teach;
    CK(cudaMemcpyToSymbol(C, &dc, sizeof dc));
    printf("teacher: %s (stage %d table drives the policy)\n", cfg.teacher.c_str(), tst);
  }
  unsigned long long* d_pool = nullptr;
  if (!pool.empty()) {
    CK(cudaMalloc(&d_pool, pool.size() * 8));
    CK(cudaMemcpy(d_pool, pool.data(), pool.size() * 8, cudaMemcpyHostToDevice));
  }
  Grad G;
  size_t touch_cap = min((size_t)stage_size, (size_t)cfg.games * cfg.steps * F *
                                                ((cfg.train_all_root ? 6 : 2) + (cfg.branch_p > 0 ? dc.branch_len + 1 : 0)));
  G.cap = (unsigned int)touch_cap;
  CK(cudaMalloc(&G.touched, touch_cap * sizeof(unsigned int)));
  CK(cudaMalloc(&G.ntouched, 4));
  CK(cudaMemset(G.ntouched, 0, 4));
  Ring R;
  R.n = cfg.games;
  size_t ring_n = (size_t)(cfg.horizon + 1) * cfg.games;
  CK(cudaMalloc(&R.as, ring_n * 8));
  CK(cudaMalloc(&R.r, ring_n * 4));
  CK(cudaMalloc(&R.v, ring_n * 4));
  CK(cudaMalloc(&R.cut, ring_n));
  CK(cudaMemset(R.cut, 0, ring_n));
  const unsigned int REC_CAP = 1 << 20, COLL_CAP = 1 << 20;
  GameState* d_games;
  EpisodeRec* d_recs;
  unsigned int *d_nrec, *d_ncoll;
  unsigned long long *d_coll, *d_moves;
  int* d_stop;
  CK(cudaMalloc(&d_games, cfg.games * sizeof(GameState)));
  CK(cudaMalloc(&d_recs, REC_CAP * sizeof(EpisodeRec)));
  CK(cudaMalloc(&d_nrec, 4)); CK(cudaMemset(d_nrec, 0, 4));
  CK(cudaMalloc(&d_coll, COLL_CAP * 8));
  CK(cudaMalloc(&d_ncoll, 4)); CK(cudaMemset(d_ncoll, 0, 4));
  CK(cudaMalloc(&d_moves, 8)); CK(cudaMemset(d_moves, 0, 8));
  CK(cudaMalloc(&d_stop, 4)); CK(cudaMemset(d_stop, 0, 4));

  if (cfg.policy_depth > 2) CK(cudaDeviceSetLimit(cudaLimitStackSize, 8192));
  int bs = 128, nb = (cfg.games + bs - 1) / bs;
  k_init<<<nb, bs>>>(d_games, cfg.games, cfg.seed * 0x2545F4914F6CDD1DULL + 7, d_pool);
  CK(cudaGetLastError());

  printf("patterns: %s  (%d features, stages %d, training stage %d)  games in flight %d\n",
         nt::pattern_string(pats).c_str(), F, S, cfg.train_stage, cfg.games);
  printf("mode: %s alpha=%g lambda=%g horizon=%d init=%g episodes=%ld%s  policy depth %d (beam %d%s, <= %d empty)\n",
         cfg.tc ? "TC" : "TD", cfg.alpha, cfg.lambda, cfg.horizon, cfg.init, cfg.episodes,
         cfg.learn ? "" : " (no learning)", cfg.policy_depth, cfg.policy_beam, cfg.policy_no4 ? ", no 4s" : "",
         cfg.policy_max_empty);
  if (cfg.corner_lock) printf("corner lock: a max tile of rank >= %d stays in its corner\n", cfg.corner_lock);
  if (cfg.update_scale != "mean") printf("batched update scale: %s\n", cfg.update_scale.c_str());
  if (cfg.branch_p > 0) printf("side branches: p=%g, %d greedy moves\n", cfg.branch_p, dc.branch_len);
  fflush(stdout);

  FILE* collect_file = cfg.collect.empty() ? nullptr : fopen(cfg.collect.c_str(), "wb");
  long collected = 0;

  // streams the weights from the GPU to disk (weight file + raw TC checkpoint)
  auto save_weights = [&]() {
    const size_t chunk = 1 << 22;
    vector<float> buf(chunk);
    vector<TCE> tbuf(chunk);
    vector<WE> wbuf(chunk);
    if (!cfg.save.empty()) {
      string tmp = cfg.save + ".tmp";
      FILE* f = fopen(tmp.c_str(), "wb");
      string ps = nt::pattern_string(pats);
      uint32_t hdr[3] = {0x32303438u, (uint32_t)ps.size(), (uint32_t)S};
      fwrite(hdr, sizeof hdr, 1, f);
      fwrite(ps.data(), 1, ps.size(), f);
      FILE* in = lo > 0 ? fopen(cfg.load.c_str(), "rb") : nullptr;  // stages left on the host
      for (int st = 0; st < S; st++) {
        if (st < lo) fseek(in, data_pos + (long)min(st, file_stages - 1) * (long)(stage_size * sizeof(float)), SEEK_SET);
        for (size_t i = 0; i < stage_size; i += chunk) {
          size_t n = min(chunk, (size_t)stage_size - i);
          if (st < lo) {
            if (fread(buf.data(), sizeof(float), n, in) != n) { fprintf(stderr, "short weight file\n"); exit(1); }
          } else if (st == cfg.train_stage) {
            CK(cudaMemcpy(wbuf.data(), d_tw + i, n * sizeof(WE), cudaMemcpyDeviceToHost));
            for (size_t j = 0; j < n; j++) buf[j] = wbuf[j].w;
          } else {
            CK(cudaMemcpy(buf.data(), d_wf + slot(st) + i, n * sizeof(float), cudaMemcpyDeviceToHost));
          }
          fwrite(buf.data(), sizeof(float), n, f);
        }
      }
      if (in) fclose(in);
      fclose(f);
      rename(tmp.c_str(), cfg.save.c_str());
    }
    if (!cfg.checkpoint.empty()) {
      string tmp = cfg.checkpoint + ".tmp";
      FILE* f = fopen(tmp.c_str(), "wb");
      for (size_t i = 0; i < stage_size; i += chunk) {
        size_t n = min(chunk, (size_t)stage_size - i);
        CK(cudaMemcpy(wbuf.data(), d_tw + i, n * sizeof(WE), cudaMemcpyDeviceToHost));
        for (size_t j = 0; j < n; j++) tbuf[j] = TCE{wbuf[j].w, wbuf[j].e, wbuf[j].a};
        fwrite(tbuf.data(), sizeof(TCE), n, f);
      }
      fclose(f);
      rename(tmp.c_str(), cfg.checkpoint.c_str());
    }
  };

  long finished = 0, next_log = cfg.log_every, next_save = cfg.save_every ? cfg.save_every : -1;
  double wscore = 0;
  long wgames = 0, wtiles[20] = {0}, wsum48 = 0, wsum56 = 0, wexit = 0, w65 = 0;
  unsigned long long last_moves = 0;
  auto t0 = Clock::now(), tw0 = t0;
  vector<EpisodeRec> recs;
  bool stopping = false;
  // several step/apply rounds are queued between host synchronisations
  const int rounds = max(1, (int)(REC_CAP / 2 / (unsigned)cfg.games));
  unsigned int last_touched = 0;  // distinct weights updated in the last round (for the log)
  for (;;) {
    for (int rd = 0; rd < rounds; rd++) {
      k_step<<<nb, bs>>>(d_games, cfg.games, cfg.steps, T, d_tw, G, R, d_wf, d_pool, d_recs, d_nrec, REC_CAP, d_coll,
                         d_ncoll, COLL_CAP, d_moves, d_stop);
      CK(cudaGetLastError());
      if (cfg.learn) {
        k_apply<<<1024, 256>>>(d_tw, G);
        if (rd == rounds - 1) CK(cudaMemcpy(&last_touched, G.ntouched, 4, cudaMemcpyDeviceToHost));
        CK(cudaMemsetAsync(G.ntouched, 0, 4));
      }
    }
    unsigned int nrec = 0, ncoll = 0;
    CK(cudaMemcpy(&nrec, d_nrec, 4, cudaMemcpyDeviceToHost));
    if (nrec) {
      if (nrec > REC_CAP) nrec = REC_CAP;
      recs.resize(nrec);
      CK(cudaMemcpy(recs.data(), d_recs, nrec * sizeof(EpisodeRec), cudaMemcpyDeviceToHost));
      CK(cudaMemset(d_nrec, 0, 4));
      for (auto& r : recs) {
        finished++;
        wgames++;
        wscore += r.score;
        wtiles[r.max_rank]++;
        wsum48 += r.sum >= 49152;
        wsum56 += r.sum >= 57344;
        wexit += r.exited;
        w65 += r.made65536;
        if (finished == next_log) {
          unsigned long long mv;
          static unsigned long long last_eg = 0;
          CK(cudaMemcpy(&mv, d_moves, 8, cudaMemcpyDeviceToHost));
          auto now = Clock::now();
          double dt = chrono::duration<double>(now - tw0).count();
          printf("%9ld games  avg %8.0f  mps %6.2fM  |", finished, wscore / wgames, (mv - last_moves) / dt / 1e6);
          for (int rr = 11; rr <= 15; rr++) {
            long c = 0;
            for (int q = rr; q < 20; q++) c += wtiles[q];
            printf(" %5d:%5.1f%%", 1 << rr, 100.0 * c / wgames);
          }
          printf("  32k+16k:%5.2f%% +8k:%5.2f%% 65536:%5.2f%%", 100.0 * wsum48 / wgames, 100.0 * wsum56 / wgames,
                 100.0 * w65 / wgames);
          if (cfg.stop_at_boundary) printf("  stage exit:%5.1f%%", 100.0 * wexit / wgames);
          if (!cfg.eg_dir.empty()) {
            unsigned long long em;
            CK(cudaMemcpyFromSymbol(&em, g_eg_moves, sizeof em));
            printf("  table moves:%5.2f%%", 100.0 * (em - last_eg) / max(1ULL, mv - last_moves));
            last_eg = em;
          }
          if (cfg.learn && last_touched)
            printf("  c:%.1f", (double)cfg.games * cfg.steps * F / last_touched);  // feature updates per distinct weight
          printf("  | %.0fs\n", chrono::duration<double>(now - t0).count());
          fflush(stdout);
          last_moves = mv;
          tw0 = now;
          wscore = 0;
          wgames = 0;
          for (auto& x : wtiles) x = 0;
          wsum48 = wsum56 = wexit = w65 = 0;
          next_log += cfg.log_every;
        }
        if (finished == next_save) {
          save_weights();
          next_save += cfg.save_every;
        }
      }
    }
    if (collect_file) {
      CK(cudaMemcpy(&ncoll, d_ncoll, 4, cudaMemcpyDeviceToHost));
      if (ncoll) {
        if (ncoll > COLL_CAP) ncoll = COLL_CAP;
        vector<unsigned long long> c(ncoll);
        CK(cudaMemcpy(c.data(), d_coll, ncoll * 8, cudaMemcpyDeviceToHost));
        CK(cudaMemset(d_ncoll, 0, 4));
        fwrite(c.data(), 8, ncoll, collect_file);
        fflush(collect_file);
        collected += ncoll;
      }
    }
    if (!stopping && finished >= cfg.episodes) {
      int one = 1;
      CK(cudaMemcpy(d_stop, &one, 4, cudaMemcpyHostToDevice));
      stopping = true;
    }
    if (stopping) break;  // in-flight games are abandoned
  }
  if (collect_file) {
    fclose(collect_file);
    printf("collected %ld positions\n", collected);
  }
  if (cfg.learn) save_weights();
  return 0;
}
