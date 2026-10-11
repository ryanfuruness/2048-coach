// Packed n-tuple networks for cheap serving (workstream serve, 2026-10-07).
//
// The analysis engine's networks (5 stages x 8 six-cell patterns x 16^6 entries) take 1.34 GB as int16. Three
// observations make them much smaller without changing what the engine looks up:
//   - a stage that was never trained (best_v6c's stage 4: every entry still at its initial value) is one constant;
//   - a stage whose looked-up entries only use tile ranks below R is re-indexed in base R instead of 16 (an index with
//     a nibble >= R is answered by the stage's initial value without a table), e.g. 15^6 = 68% of 16^6. For best_v6c:
//     R = 14 for stage 0 (its leaves never hold a 16384: the leaf view, view_top 14 below sum 20480, lowers them),
//     15 for stages 1-2 (nothing trained uses a 32768 there), 16 for stage 3. A lower cap than the engine's lookups
//     need changes answers (stage 3 at 15 does); beyond_cap counts such lookups;
//   - values: "int16" keeps exactly the int16 values of nt::load_quantized (per-stage scale), so the packed engine
//     answers bit-identically; "int8" stores (w - init) / step per table in 8 bits (step: a per-table quantile of the
//     trained |w - init| / 127) with the rare larger values as exact escapes (code -128), found through a bucket index.
// File (.wp, little-endian): "WPK1", the pattern string, the stage count, per stage {kind, R, init, int16 scale,
// int16 init}, then per pattern {step, R^6 values, for int8: escape count + indices + values}. build/wpack_tool makes
// and checks them; the engine loads one with --packed FILE (engine.h), which replaces --weights' networks.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include "board.h"
#include "ntuple.h"

namespace wpack {

enum Kind : uint32_t { kConst = 0, kInt16 = 1, kInt8 = 2 };

struct Stage {
  uint32_t kind = kConst, R = 16;
  float init = 0;       // the untrained value (float)
  float scale = 1;      // int16: value = q * scale (as nt::load_quantized)
  int16_t q_init = 0;   // int16: the quantized initial value (for indices beyond the rank cap)
  uint32_t r6 = 0;      // R^6
  std::vector<float> step;                     // int8: per pattern
  std::vector<std::vector<int16_t>> t16;       // int16: per pattern, R^6
  std::vector<std::vector<int8_t>> t8;         // int8: per pattern, R^6 (-128 = escape)
  std::vector<std::vector<uint32_t>> esc_idx;  // int8 escapes per pattern (sorted base-R index)
  std::vector<std::vector<float>> esc_val;     // their exact deltas (w - init)
  std::vector<std::vector<uint32_t>> esc_bkt;  // per pattern: first escape of each bucket (index >> esc_shift)
  int esc_shift = 0;
  // base-R index of the low / high three nibbles of a 24-bit pattern index (kInvalid if a nibble is >= R)
  std::vector<uint32_t> lo, hi;
  void make_maps() {
    static const uint32_t kInvalid = 1u << 30;
    lo.assign(4096, 0), hi.assign(4096, 0);
    r6 = R * R * R * R * R * R;
    uint32_t r3 = R * R * R;
    for (uint32_t h = 0; h < 4096; h++) {
      uint32_t a = h & 15, b = (h >> 4) & 15, c = h >> 8;
      bool ok = a < R && b < R && c < R;
      uint32_t v = a + R * (b + R * c);
      lo[h] = ok ? v : kInvalid;
      hi[h] = ok ? v * r3 : kInvalid;
    }
    esc_shift = 0;
    while ((r6 >> esc_shift) > (1u << 16)) esc_shift++;
  }
  // the base-R index of a 24-bit pattern index, or >= r6 when a nibble is beyond the cap
  inline uint32_t index(uint64_t x) const { return lo[x & 0xFFF] + hi[(x >> 12) & 0xFFF]; }
  void make_buckets(size_t p) {
    uint32_t nb = (r6 >> esc_shift) + 2;
    std::vector<uint32_t>& B = esc_bkt[p];
    B.assign(nb, 0);
    const auto& ix = esc_idx[p];
    size_t j = 0;
    for (uint32_t b = 0; b < nb; b++) {
      while (j < ix.size() && (ix[j] >> esc_shift) < b) j++;
      B[b] = (uint32_t)j;
    }
  }
  inline float escape(size_t p, uint32_t i) const {
    uint32_t b = i >> esc_shift;
    const auto& ix = esc_idx[p];
    for (uint32_t j = esc_bkt[p][b], e = esc_bkt[p][b + 1]; j < e; j++)
      if (ix[j] == i) return esc_val[p][j];
    return 0.0f;
  }
};

class PackedNet {
 public:
  std::vector<nt::Pattern> pats;
  int nstages = 0;
  std::vector<Stage> st;
  mutable unsigned long long beyond_cap = 0;  // lookups answered by the initial value (diagnostics; not thread-exact)

  inline float eval(board_t b, int stage = 0) const {
    const Stage& S = st[stage];
    if (S.kind == kConst) return S.init * (float)(8 * pats.size());
    board_t s[8];
    bb::symmetries(b, s);
    if (S.kind == kInt16) {
      int32_t v = 0;
      for (size_t p = 0; p < pats.size(); p++) {
        const int16_t* t = S.t16[p].data();
        uint64_t m = pats[p].mask;
        for (int k = 0; k < 8; k++) {
          uint32_t i = S.index(bb::pext_nib(s[k], m));
          if (i < S.r6) v += t[i];
          else v += S.q_init, beyond_cap++;
        }
      }
      return (float)v * S.scale;
    }
    float v = S.init * (float)(8 * pats.size());
    for (size_t p = 0; p < pats.size(); p++) {
      const int8_t* t = S.t8[p].data();
      uint64_t m = pats[p].mask;
      int32_t q = 0;
      float e = 0;
      for (int k = 0; k < 8; k++) {
        uint32_t i = S.index(bb::pext_nib(s[k], m));
        if (i >= S.r6) { beyond_cap++; continue; }
        int8_t x = t[i];
        if (x != -128) q += x;
        else e += S.escape(p, i);
      }
      v += (float)q * S.step[p] + e;
    }
    return v;
  }
  // The weight of entry `x` (24-bit pattern index) of pattern p in stage `stage` (for the per-cell attribution).
  float weight(int stage, size_t p, uint64_t x) const {
    const Stage& S = st[stage];
    if (S.kind == kConst) return S.init;
    uint32_t i = S.index(x);
    if (S.kind == kInt16) return (float)(i < S.r6 ? S.t16[p][i] : S.q_init) * S.scale;
    if (i >= S.r6) return S.init;
    int8_t q = S.t8[p][i];
    return S.init + (q != -128 ? (float)q * S.step[p] : S.escape(p, i));
  }
  size_t bytes() const {  // memory of the tables
    size_t n = 0;
    for (auto& S : st) {
      for (auto& t : S.t16) n += t.size() * 2;
      for (auto& t : S.t8) n += t.size();
      for (auto& t : S.esc_idx) n += t.size() * 8;
      for (auto& t : S.esc_bkt) n += t.size() * 4;
      n += (S.lo.size() + S.hi.size()) * 4;
    }
    return n;
  }

  void load(const std::string& path) {
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) throw std::runtime_error("cannot read " + path);
    auto rd = [&](void* p, size_t n) {
      if (fread(p, 1, n, f) != n) throw std::runtime_error("short packed weight file " + path);
    };
    uint32_t magic, plen, ns;
    rd(&magic, 4);
    if (magic != 0x314B5057u) throw std::runtime_error("not a packed weight file: " + path);
    rd(&plen, 4);
    std::string ps(plen, ' ');
    rd(&ps[0], plen);
    pats = nt::parse_patterns(ps);
    rd(&ns, 4);
    nstages = (int)ns;
    st.assign(ns, Stage());
    for (auto& S : st) {
      rd(&S.kind, 4), rd(&S.R, 4), rd(&S.init, 4), rd(&S.scale, 4), rd(&S.q_init, 2);
      if (S.kind > kInt8) throw std::runtime_error("unknown table kind in " + path);
      S.make_maps();
      if (S.kind == kConst) continue;
      size_t np = pats.size();
      S.step.assign(np, 0);
      if (S.kind == kInt16) S.t16.assign(np, {});
      else S.t8.assign(np, {}), S.esc_idx.assign(np, {}), S.esc_val.assign(np, {}), S.esc_bkt.assign(np, {});
      for (size_t p = 0; p < np; p++) {
        rd(&S.step[p], 4);
        if (S.kind == kInt16) {
          S.t16[p].resize(S.r6);
          rd(S.t16[p].data(), S.r6 * 2);
        } else {
          S.t8[p].resize(S.r6);
          rd(S.t8[p].data(), S.r6);
          uint32_t ne;
          rd(&ne, 4);
          S.esc_idx[p].resize(ne), S.esc_val[p].resize(ne);
          if (ne) rd(S.esc_idx[p].data(), ne * 4), rd(S.esc_val[p].data(), ne * 4);
          S.make_buckets(p);
        }
      }
    }
    fclose(f);
  }
};

}  // namespace wpack
