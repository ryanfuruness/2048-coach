// Exact endgame sub-games.
//
// Late in a game the biggest tiles form a chain that should stay where it is, and play
// consists of building, in the remaining cells, a tile equal to the chain's smallest tile
// right next to it (after which the chain collapses by merging). That sub-game is small
// enough to solve exactly: dynamic programming over the free cells gives the probability of
// producing the goal tile under optimal play, using only moves that leave the locked cells
// untouched. (This is the idea behind macroxue/2048-ai's lookup tables; the implementation
// here is independent.)
//
// A Table is one sub-game shape: which cells are locked, where the goal tile counts, its
// rank, and a cap on every free cell's rank (a free tile above its cap ends the sub-game as
// a failure: the table stays finite and a tile that big belongs in the chain, not in the
// free region). Entries are computed on demand by a memoised expectimax and kept in a
// chunked array, so only the configurations actually reached cost memory.
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "board.h"

namespace eg {

struct Spec {
  uint16_t locked = 0;  // bit i: cell i is locked
  uint16_t goal = 0;    // bit i: a goal-rank tile in cell i wins (cells next to the chain's end)
  int goal_rank = 0;
  int cap[16] = {};     // free cells: largest rank allowed
  // Digit order of the table index, least significant first (default: by cell number). Putting
  // the cells whose small tiles vary most first keeps the reachable entries close together.
  int order[16] = {-1};
};

class Table {
 public:
  // Locked cells hold `chain` (only their positions matter to the sub-game, but a real chain
  // value keeps the board legal; any distinct ranks above the free caps work).
  Table(const Spec& s, board_t chain) : spec_(s), chain_(chain) {
    n_ = 0;
    size_ = 1;
    for (int i = 0; i < 16; i++) {
      int c = s.order[0] < 0 ? i : s.order[i];
      if (!(s.locked >> c & 1)) {
        cells_[n_] = c;
        radix_[n_] = size_;
        size_ *= (uint64_t)(s.cap[c] + 1);
        n_++;
      }
    }
    locked_mask_ = 0;
    for (int c = 0; c < 16; c++)
      if (s.locked >> c & 1) locked_mask_ |= 0xFULL << (4 * c);
    chunks_.resize((size_ + kChunk - 1) / kChunk);
  }

  uint64_t size() const { return size_; }
  int free_cells() const { return n_; }
  const Spec& spec() const { return spec_; }
  int cell_at(int k) const { return cells_[k]; }      // k-th index digit's cell
  uint64_t radix_at(int k) const { return radix_[k]; }
  static constexpr uint64_t chunk_size() { return kChunk; }

  // Flat copy for the GPU: slot[c] = position of chunk c in data (in chunks), or -1.
  void export_flat(std::vector<int32_t>& slot, std::vector<uint16_t>& data) const {
    slot.assign(chunks_.size(), -1);
    data.clear();
    int32_t n = 0;
    for (size_t c = 0; c < chunks_.size(); c++)
      if (chunks_[c]) {
        slot[c] = n++;
        data.insert(data.end(), chunks_[c].get(), chunks_[c].get() + kChunk);
      }
  }

  // Writes to path.tmp and renames, so a reader never sees a partial file.
  bool save(const char* path) const {
    std::string tmp = std::string(path) + ".tmp";
    FILE* f = fopen(tmp.c_str(), "wb");
    if (!f) return false;
    uint64_t hdr[4] = {0x31544745ULL /* "EGT1" */, kChunk, (uint64_t)chunks_.size(), (uint64_t)allocated_};
    fwrite(hdr, sizeof hdr, 1, f);
    fwrite(&spec_, sizeof spec_, 1, f);
    fwrite(&chain_, sizeof chain_, 1, f);
    for (size_t c = 0; c < chunks_.size(); c++)
      if (chunks_[c]) {
        uint64_t idx = c;
        fwrite(&idx, sizeof idx, 1, f);
        fwrite(chunks_[c].get(), sizeof(uint16_t), kChunk, f);
      }
    if (fclose(f) != 0) return false;
    return rename(tmp.c_str(), path) == 0;
  }
  // Loads entries saved from a table of the same shape; false if the file does not match.
  bool load(const char* path) {
    FILE* f = fopen(path, "rb");
    if (!f) return false;
    uint64_t hdr[4];
    Spec sp;
    board_t ch;
    bool ok = fread(hdr, sizeof hdr, 1, f) == 1 && hdr[0] == 0x31544745ULL && hdr[1] == kChunk &&
              hdr[2] == chunks_.size() && fread(&sp, sizeof sp, 1, f) == 1 && fread(&ch, sizeof ch, 1, f) == 1 &&
              memcmp(&sp, &spec_, sizeof sp) == 0;
    for (uint64_t i = 0; ok && i < hdr[3]; i++) {
      uint64_t idx;
      if (fread(&idx, sizeof idx, 1, f) != 1 || idx >= chunks_.size()) { ok = false; break; }
      if (!chunks_[idx]) allocated_++;
      chunks_[idx].reset(new uint16_t[kChunk]);
      ok = fread(chunks_[idx].get(), sizeof(uint16_t), kChunk, f) == kChunk;
      for (uint64_t k = 0; ok && k < kChunk; k++) computed_ += chunks_[idx][k] != kUnknown;
    }
    fclose(f);
    return ok;
  }
  long entries() const { return computed_; }
  long chunk_bytes() const { return allocated_ * kChunk * (long)sizeof(uint16_t); }

  // Index of board b's free cells, or -1 if a free cell is above its cap.
  int64_t index(board_t b) const {
    uint64_t i = 0;
    for (int k = 0; k < n_; k++) {
      int r = bb::cell(b, cells_[k]);
      if (r > spec_.cap[cells_[k]]) return -1;
      i += (uint64_t)r * radix_[k];
    }
    return (int64_t)i;
  }
  board_t board_of(uint64_t idx) const {
    board_t b = chain_ & locked_mask_;
    for (int k = 0; k < n_; k++) {
      b |= (board_t)(idx / radix_[k] % (spec_.cap[cells_[k]] + 1)) << (4 * cells_[k]);
    }
    return b;
  }
  bool won(board_t after) const {
    for (int c = 0; c < 16; c++)
      if ((spec_.goal >> c & 1) && bb::cell(after, c) == spec_.goal_rank) return true;
    return false;
  }

  // Success probability of the position b (a state before a move; free cells as on the real
  // board, locked cells ignored) with optimal play; *move gets the best move (-1: none).
  // Like solve(), but only reads entries already computed (no computation, no lock): -1 if the
  // entry is unknown. Safe while no other thread computes entries of this table.
  float peek(board_t b, int* move) const {
    board_t s = (b & ~locked_mask_) | (chain_ & locked_mask_);
    int64_t i = index(s);
    if (i < 0) return -1.0f;
    const auto& c = chunks_[(uint64_t)i / kChunk];
    if (!c) return -1.0f;
    uint16_t e = c[(uint64_t)i % kChunk];
    if (e == kUnknown) return -1.0f;
    *move = e >> 14;
    return (e & 0x3FFF) / kScale;
  }

  float solve(board_t b, int* move) {
    board_t s = (b & ~locked_mask_) | (chain_ & locked_mask_);
    int64_t i = index(s);
    if (i < 0) {
      if (move) *move = -1;
      return 0.0f;
    }
    float p = value(s, (uint64_t)i);
    if (move) *move = get((uint64_t)i) >> 14;
    if (p == 0.0f && move) *move = -1;
    return p;
  }

 private:
  static constexpr uint64_t kChunk = 1 << 12;
  static constexpr uint16_t kUnknown = 0xFFFF;
  static constexpr float kScale = 16000.0f;  // probability resolution (14 bits)
  Spec spec_;
  board_t chain_, locked_mask_;
  int n_;
  int cells_[16];
  uint64_t radix_[16];
  uint64_t size_;
  std::vector<std::unique_ptr<uint16_t[]>> chunks_;
  long computed_ = 0, allocated_ = 0;

  uint16_t get(uint64_t i) {
    auto& c = chunks_[i / kChunk];
    if (!c) return kUnknown;
    return c[i % kChunk];
  }
  void put(uint64_t i, uint16_t v) {
    auto& c = chunks_[i / kChunk];
    if (!c) {
      c.reset(new uint16_t[kChunk]);
      for (uint64_t k = 0; k < kChunk; k++) c[k] = kUnknown;
      allocated_++;
    }
    c[i % kChunk] = v;
  }

  // Value of state s (before a move) with index i.
  float value(board_t s, uint64_t i) {
    uint16_t e = get(i);
    if (e != kUnknown) return (e & 0x3FFF) / kScale;
    float best = 0.0f;
    int best_move = 0;
    for (int d = 0; d < 4; d++) {
      board_t a = bb::move(s, d);
      if (a == s || (a & locked_mask_) != (s & locked_mask_)) continue;  // illegal or moves the chain
      float p = won(a) ? 1.0f : chance(a);
      if (p > best) best = p, best_move = d;
      if (best >= 1.0f) break;
    }
    uint16_t q = (uint16_t)(best * kScale + 0.5f);
    put(i, (uint16_t)(q | (best_move << 14)));
    computed_++;
    return q / kScale;
  }
  float chance(board_t a) {
    if (index(a) < 0) return 0.0f;  // a free tile grew above its cap
    uint64_t em = bb::empty_mask(a);
    int n = __builtin_popcountll(em);
    if (n == 0) return 0.0f;
    float sum = 0.0f;
    for (uint64_t m = em; m; m &= m - 1) {
      uint64_t bit = m & -m;
      board_t s2 = a | bit, s4 = a | (bit << 1);
      sum += 0.9f * value(s2, (uint64_t)index(s2));
      int64_t i4 = index(s4);
      sum += 0.1f * (i4 < 0 ? 0.0f : value(s4, (uint64_t)i4));
    }
    return sum / n;
  }
};

}  // namespace eg

namespace eg {

// Applies symmetry j (the order of bb::symmetries) to b.
static inline board_t sym(board_t b, int j) {
  if (j >= 4) b = bb::transpose(b);
  switch (j & 3) {
    case 1: return bb::flip_h(b);
    case 2: return bb::flip_v(b);
    case 3: return bb::flip_h(bb::flip_v(b));
  }
  return b;
}

// Snake endings: in some orientation, the cells along the snake path (row 0 left to right,
// row 1 right to left, ...) start with a strictly decreasing chain of k >= kmin tiles from the
// corner, and every other cell holds at most the chain's last rank. The sub-game: make a tile
// equal to the chain's end next to it without moving the chain. The k locked cells used are
// the shortest prefix the tables allow (more free cells, more ways to win). Thread-safe.
class Snake {
 public:
  static constexpr int kPath[16] = {0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12};
  // Tables for k locked cells are built only for goal ranks up to max_rank[k].
  // full = 1: only chains whose ranks fall by exactly one per cell, so that winning the sub-game
  // collapses the whole chain into one tile twice the corner's; full = 2: also chains with one
  // missing rank (a drop of two), where winning collapses the tail into exactly the missing tile
  // (e.g. [16384 8192 2048 1024 512 256] + 256 -> [16384 8192 4096]); full = n: up to n-1 such gaps
  // (winning fills the lowest one).
  Snake(int kmin, const int max_rank[17], int full = 0) : kmin_(kmin), full_(full) {
    for (int k = 0; k <= 16; k++) max_rank_[k] = max_rank[k];
  }

  // Best table move for the real-frame board b and its success probability, or -1.
  int suggest(board_t b, float* prob) {
    float best = -1.0f;
    int best_dir = -1;
    for (int j = 0; j < 8; j++) {
      board_t s = sym(b, j);
      int k, r;
      if (!match(s, &k, &r)) continue;
      Table* t = table(k, r);
      int m;
      float p;
      {
        std::lock_guard<std::mutex> lk(mu_);
        p = t->solve(s, &m);
      }
      if (m < 0 || p <= best) continue;
      // the table's move in this frame -> the real move with the same afterstate
      board_t a = bb::move(s, m);
      for (int d = 0; d < 4; d++) {
        board_t ad = bb::move(b, d);
        if (ad != b && sym(ad, j) == a) {
          best = p, best_dir = d;
          break;
        }
      }
    }
    if (prob) *prob = best;
    return best_dir;
  }

  // Like suggest(), but only from tables loaded or built before (lookup only, no computation, no
  // lock), for many threads at once (training). -1 when no known entry applies.
  int peek(board_t b, float* prob) const {
    float best = -1.0f;
    int best_dir = -1;
    for (int j = 0; j < 8; j++) {
      board_t s = sym(b, j);
      int k, r;
      if (!match(s, &k, &r)) continue;
      const Table* t = tables_[k * 16 + r].get();
      if (!t) continue;
      int m = 0;
      float p = t->peek(s, &m);
      if (p <= best) continue;
      board_t a = bb::move(s, m);
      if (a == s) continue;
      for (int d = 0; d < 4; d++) {
        board_t ad = bb::move(b, d);
        if (ad != b && sym(ad, j) == a) {
          best = p, best_dir = d;
          break;
        }
      }
    }
    if (prob) *prob = best;
    return best_dir;
  }

  // Success probability of state s (before a move) under the best matching orientation, or -1.
  float value(board_t s) {
    float best = -1.0f;
    for (int j = 0; j < 8; j++) {
      board_t t = sym(s, j);
      int k, r;
      if (!match(t, &k, &r)) continue;
      Table* tb = table(k, r);
      std::lock_guard<std::mutex> lk(mu_);
      float p = tb->solve(t, nullptr);
      if (p > best) best = p;
    }
    return best;
  }
  // Expected success probability of afterstate a over its random tiles, or -1 if a is not an
  // ending (spawning a 2 or 4 in a free cell never changes whether it is one).
  float after_value(board_t a) {
    if (!matches_any(a)) return -1.0f;
    uint64_t em = bb::empty_mask(a);
    int n = __builtin_popcountll(em);
    if (n == 0) return 0.0f;
    float sum = 0.0f;
    for (uint64_t m = em; m; m &= m - 1) {
      uint64_t bit = m & -m;
      float p2 = value(a | bit), p4 = value(a | (bit << 1));
      sum += 0.9f * (p2 > 0 ? p2 : 0.0f) + 0.1f * (p4 > 0 ? p4 : 0.0f);
    }
    return sum / n;
  }
  bool matches_any(board_t s) const {
    for (int j = 0; j < 8; j++) {
      int k, r;
      if (match(sym(s, j), &k, &r)) return true;
    }
    return false;
  }

  // Does board s (in this frame) hold a snake ending? Sets the locked length and goal rank.
  bool match(board_t s, int* k_out, int* r_out) const {
    int k = 1;
    int prev = bb::cell(s, kPath[0]);
    if (prev == 0 || prev != bb::max_rank(s)) return false;
    int gaps = 0;
    while (k < 16) {
      int v = bb::cell(s, kPath[k]);
      bool step_ok = v == prev - 1 || (gaps < full_ - 1 && v == prev - 2);
      if (v == 0 || v >= prev || (full_ && !step_ok)) break;
      gaps += v == prev - 2;
      prev = v;
      k++;
    }
    for (int kk = kmin_; kk <= k; kk++) {
      int r = bb::cell(s, kPath[kk - 1]);
      if (r > max_rank_[kk]) continue;
      bool ok = true;
      for (int i = kk; i < 16 && ok; i++) ok = bb::cell(s, kPath[i]) <= r;
      if (!ok) continue;
      *k_out = kk, *r_out = r;
      return true;
    }
    return false;
  }

  // Saves every table built so far as DIR/snake_k<k>_r<r>.egt; loads those present in DIR.
  void save(const std::string& dir) {
    std::lock_guard<std::mutex> lk(mu_);
    for (int k = 0; k <= 16; k++)
      for (int r = 0; r < 16; r++)
        if (tables_[k * 16 + r]) tables_[k * 16 + r]->save(file(dir, k, r).c_str());
  }
  int load(const std::string& dir) {
    int n = 0;
    for (int k = kmin_; k <= 16; k++)
      for (int r = 1; r <= max_rank_[k]; r++) {
        std::string f = file(dir, k, r);
        FILE* fp = fopen(f.c_str(), "rb");
        if (!fp) continue;
        fclose(fp);
        Table* t = table(k, r);
        std::lock_guard<std::mutex> lk(mu_);
        if (t->load(f.c_str())) n++;
        else fprintf(stderr, "endgame: cannot load %s\n", f.c_str());
      }
    return n;
  }
  // The table for k locked cells and goal rank r (built empty if new).
  Table* get(int k, int r) { return table(k, r); }
  int kmin() const { return kmin_; }
  int full() const { return full_; }
  int max_rank(int k) const { return max_rank_[k]; }

  long memory() {
    std::lock_guard<std::mutex> lk(mu_);
    long m = 0;
    for (auto& t : tables_)
      if (t) m += t->chunk_bytes();
    return m;
  }

 private:
  int kmin_;
  int full_;
  int max_rank_[17];
  std::mutex mu_;
  std::unique_ptr<Table> tables_[17 * 16];

  static std::string file(const std::string& dir, int k, int r) {
    return dir + "/snake_k" + std::to_string(k) + "_r" + std::to_string(r) + ".egt";
  }
  Table* table(int k, int r) {
    std::lock_guard<std::mutex> lk(mu_);
    auto& t = tables_[k * 16 + r];
    if (!t) {
      Spec s;
      board_t chain = 0;
      for (int j = 0; j < k; j++) {
        s.locked |= 1 << kPath[j];
        chain = bb::set_cell(chain, kPath[j], r + (k - 1 - j) > 15 ? 15 : r + (k - 1 - j));
      }
      int end = kPath[k - 1];
      for (int c = 0; c < 16; c++) {
        if (s.locked >> c & 1) continue;
        s.cap[c] = r;
        int dr = c / 4 - end / 4, dc = c % 4 - end % 4;
        if (dr * dr + dc * dc == 1) s.goal |= 1 << c;
      }
      s.goal_rank = r;
      for (int i = 0; i < 16; i++) s.order[i] = kPath[i];
      t.reset(new Table(s, chain));
    }
    return t.get();
  }
};

}  // namespace eg
