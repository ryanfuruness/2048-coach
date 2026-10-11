// N-tuple network value function for 2048 afterstates.
//
// A pattern is a set of cells. Its feature index on a board is the concatenation
// of the 4-bit ranks of those cells (extracted with PEXT). Every pattern is
// applied to all 8 symmetries of the board with shared weights, so
//   V(b) = sum_p sum_k w_p[pext(sym_k(b), mask_p)].
// Weights can be split into "stages" (separate weight sets for game phases).
#pragma once
#include <sys/mman.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>
#include "board.h"

namespace nt {

struct Pattern {
  std::vector<int> cells;  // sorted
  uint64_t mask = 0;
  size_t size = 0;  // 16^n
};

// Pattern strings are hex cell lists separated by spaces, e.g. "012345 456789".
static inline std::vector<Pattern> parse_patterns(const std::string& spec) {
  std::string s = spec;
  if (s == "4x6") s = "012345 456789 012456 45689a";
  else if (s == "8x6") s = "012345 456789 012456 45689a 01237b 012458 0156ab 01259d";
  std::vector<Pattern> out;
  size_t i = 0;
  while (i < s.size()) {
    while (i < s.size() && s[i] == ' ') i++;
    if (i >= s.size()) break;
    Pattern p;
    while (i < s.size() && s[i] != ' ') {
      char c = s[i++];
      int v = (c >= '0' && c <= '9') ? c - '0' : (c >= 'a' && c <= 'f') ? c - 'a' + 10 : -1;
      if (v < 0) throw std::runtime_error("bad pattern spec: " + spec);
      p.cells.push_back(v);
    }
    std::sort(p.cells.begin(), p.cells.end());
    for (int c : p.cells) p.mask |= 0xFULL << (4 * c);
    p.size = 1ULL << (4 * p.cells.size());
    out.push_back(p);
  }
  return out;
}

static inline std::string pattern_string(const std::vector<Pattern>& ps) {
  std::string s;
  for (auto& p : ps) {
    if (!s.empty()) s += ' ';
    for (int c : p.cells) s += "0123456789abcdef"[c];
  }
  return s;
}

// Large zero-initialised allocation backed by transparent huge pages when possible.
template <typename T>
static T* big_alloc(size_t n) {
  size_t bytes = n * sizeof(T);
  size_t align = 2 << 20;
  bytes = (bytes + align - 1) / align * align;
  void* p = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (p == MAP_FAILED) throw std::runtime_error("mmap failed");
  madvise(p, bytes, MADV_HUGEPAGE);
  return (T*)p;
}
template <typename T>
static void big_free(T* p, size_t n) {
  size_t bytes = n * sizeof(T);
  size_t align = 2 << 20;
  bytes = (bytes + align - 1) / align * align;
  munmap((void*)p, bytes);
}

// Weight entry used during training: value plus temporal-coherence accumulators.
struct TCEntry {
  float w, e, a;
};

template <typename Entry>
struct Net {
  std::vector<Pattern> pats;
  std::vector<size_t> offset;  // offset of pattern p within a stage
  size_t stage_size = 0;
  int nstages = 1;
  Entry* w = nullptr;
  size_t total = 0;
  std::vector<float> scale;  // per-stage value scale (1 except for quantized nets)

  Net() {}
  Net(const std::vector<Pattern>& ps, int stages) { init(ps, stages); }
  Net(const Net&) = delete;
  Net& operator=(const Net&) = delete;
  ~Net() {
    if (w) big_free(w, total);
  }
  void init(const std::vector<Pattern>& ps, int stages) {
    if (w) big_free(w, total);
    pats = ps;
    nstages = stages;
    offset.clear();
    stage_size = 0;
    for (auto& p : pats) {
      offset.push_back(stage_size);
      stage_size += p.size;
    }
    total = stage_size * nstages;
    w = big_alloc<Entry>(total);
    scale.assign(nstages, 1.0f);
  }
  int features() const { return 8 * (int)pats.size(); }

  inline float eval(board_t b, int stage = 0) const {
    board_t s[8];
    bb::symmetries(b, s);
    const Entry* base = w + stage * stage_size;
    float v = 0;
    for (size_t p = 0; p < pats.size(); p++) {
      const Entry* t = base + offset[p];
      uint64_t m = pats[p].mask;
      float a = get(t[bb::pext_nib(s[0], m)]) + get(t[bb::pext_nib(s[1], m)]);
      float b2 = get(t[bb::pext_nib(s[2], m)]) + get(t[bb::pext_nib(s[3], m)]);
      float c = get(t[bb::pext_nib(s[4], m)]) + get(t[bb::pext_nib(s[5], m)]);
      float d = get(t[bb::pext_nib(s[6], m)]) + get(t[bb::pext_nib(s[7], m)]);
      v += (a + b2) + (c + d);
    }
    return v * scale[stage];
  }
  static inline float get(const float& e) { return e; }
  static inline float get(const int16_t& e) { return (float)e; }
  static inline float get(const TCEntry& e) { return e.w; }

  // Moves V(b) toward `target`. Plain TD: each active weight moves by lr*err/F.
  // TC (temporal coherence): the step is further scaled by the per-weight
  // coherence |E|/A, where E and A accumulate signed and absolute errors.
  // Returns the updated value V(b).
  inline float learn(board_t b, float target, float lr, bool tc, int stage = 0) {
    board_t s[8];
    bb::symmetries(b, s);
    Entry* base = w + stage * stage_size;
    Entry* ptr[128];
    int F = 0;
    float v = 0;
    for (size_t p = 0; p < pats.size(); p++) {
      Entry* t = base + offset[p];
      uint64_t m = pats[p].mask;
      for (int k = 0; k < 8; k++) {
        ptr[F] = &t[bb::pext_nib(s[k], m)];
        v += get(*ptr[F]);
        F++;
      }
    }
    float err = target - v;
    float d = lr * err / F;
    if (tc) {
      float aerr = fabsf(err);
      for (int i = 0; i < F; i++) tc_step(*ptr[i], d, err, aerr);
    } else {
      for (int i = 0; i < F; i++) add(*ptr[i], d);
    }
    float nv = 0;
    for (int i = 0; i < F; i++) nv += get(*ptr[i]);
    return nv;
  }
  static inline void tc_step(float& e, float d, float, float) { e += d; }
  static inline void tc_step(TCEntry& e, float d, float err, float aerr) {
    float rate = e.a > 0 ? fabsf(e.e) / e.a : 1.0f;
    e.w += d * rate;
    e.e += err;
    e.a += aerr;
  }

  // Plain TD update: every active weight moves by `delta` (caller divides by features()).
  // Returns the new value of the board.
  inline float update_td(board_t b, float delta, int stage = 0) {
    board_t s[8];
    bb::symmetries(b, s);
    Entry* base = w + stage * stage_size;
    float v = 0;
    for (size_t p = 0; p < pats.size(); p++) {
      Entry* t = base + offset[p];
      uint64_t m = pats[p].mask;
      for (int k = 0; k < 8; k++) {
        Entry& e = t[bb::pext_nib(s[k], m)];
        v += add(e, delta);
      }
    }
    return v;
  }
  static inline float add(float& e, float d) { return e += d; }
  static inline float add(TCEntry& e, float d) { return e.w += d; }

  // Temporal-coherence update (Beal & Smith; Jaskowski): per-weight rate |E|/A.
  // `err` is the full TD error, `beta` the meta learning rate (already divided by features()).
  inline float update_tc(board_t b, float err, float beta, int stage = 0) {
    board_t s[8];
    bb::symmetries(b, s);
    Entry* base = w + stage * stage_size;
    float v = 0, aerr = fabsf(err);
    for (size_t p = 0; p < pats.size(); p++) {
      Entry* t = base + offset[p];
      uint64_t m = pats[p].mask;
      for (int k = 0; k < 8; k++) {
        TCEntry& e = t[bb::pext_nib(s[k], m)];
        float rate = e.a > 0 ? fabsf(e.e) / e.a : 1.0f;
        e.w += beta * rate * err;
        e.e += err;
        e.a += aerr;
        v += e.w;
      }
    }
    return v;
  }

  void fill(float value) {
    for (size_t i = 0; i < total; i++) set(w[i], value);
  }
  static inline void set(float& e, float v) { e = v; }
  static inline void set(TCEntry& e, float v) { e.w = v; e.e = 0; e.a = 0; }

  void reset_tc() {
    for (size_t i = 0; i < total; i++) reset_tc_entry(w[i]);
  }
  static inline void reset_tc_entry(float&) {}
  static inline void reset_tc_entry(TCEntry& e) { e.e = 0; e.a = 0; }

  // ---- persistence (only the values are stored) ----
  // `sub_stage`/`sub` let the caller substitute the values of one stage (the
  // trainer keeps the stage being trained in a separate net).
  void save(const std::string& path, int sub_stage = -1, const std::function<float(size_t)>& sub = nullptr) const {
    std::string tmp = path + ".tmp";
    FILE* f = fopen(tmp.c_str(), "wb");
    if (!f) throw std::runtime_error("cannot write " + path);
    std::string ps = pattern_string(pats);
    uint32_t hdr[3] = {0x32303438u, (uint32_t)ps.size(), (uint32_t)nstages};
    fwrite(hdr, sizeof(hdr), 1, f);
    fwrite(ps.data(), 1, ps.size(), f);
    const size_t chunk = 1 << 20;
    std::vector<float> buf(chunk);
    for (int st = 0; st < nstages; st++) {
      for (size_t i = 0; i < stage_size; i += chunk) {
        size_t n = std::min(chunk, stage_size - i);
        for (size_t j = 0; j < n; j++) buf[j] = st == sub_stage ? sub(i + j) : get(w[st * stage_size + i + j]);
        fwrite(buf.data(), sizeof(float), n, f);
      }
    }
    fclose(f);
    rename(tmp.c_str(), path.c_str());
  }
  // Loads weights. stages == 0 keeps the file's stage count; extra stages are
  // initialised as copies of the file's last stage, surplus file stages are ignored.
  // Values of stage `sub_stage` are handed to `sub` instead of being stored.
  void load(const std::string& path, int stages = 0, int sub_stage = -1,
            const std::function<void(size_t, float)>& sub = nullptr) {
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) throw std::runtime_error("cannot read " + path);
    uint32_t hdr[3];
    if (fread(hdr, sizeof(hdr), 1, f) != 1 || hdr[0] != 0x32303438u) throw std::runtime_error("bad weight file");
    std::string ps(hdr[1], ' ');
    if (fread(&ps[0], 1, ps.size(), f) != ps.size()) throw std::runtime_error("bad weight file");
    int file_stages = hdr[2];
    init(parse_patterns(ps), stages ? stages : file_stages);
    const size_t chunk = 1 << 20;
    std::vector<float> buf(chunk);
    long last_pos = -1;
    for (int st = 0; st < nstages; st++) {
      if (st >= file_stages) fseek(f, last_pos, SEEK_SET);  // re-read the last stage
      else last_pos = ftell(f);
      for (size_t i = 0; i < stage_size; i += chunk) {
        size_t n = std::min(chunk, stage_size - i);
        if (fread(buf.data(), sizeof(float), n, f) != n) throw std::runtime_error("short weight file");
        if (st == sub_stage)
          for (size_t j = 0; j < n; j++) sub(i + j, buf[j]);
        else
          for (size_t j = 0; j < n; j++) set(w[st * stage_size + i + j], buf[j]);
      }
    }
    fclose(f);
  }
};

// Loads a float weight file into 16-bit fixed point (per-stage scale = max|w| / 32767),
// streaming the file twice so the float weights are never held in memory.
static inline void load_quantized(const std::string& path, Net<int16_t>& q) {
  FILE* f = fopen(path.c_str(), "rb");
  if (!f) throw std::runtime_error("cannot read " + path);
  uint32_t hdr[3];
  if (fread(hdr, sizeof(hdr), 1, f) != 1 || hdr[0] != 0x32303438u) throw std::runtime_error("bad weight file");
  std::string ps(hdr[1], ' ');
  if (fread(&ps[0], 1, ps.size(), f) != ps.size()) throw std::runtime_error("bad weight file");
  q.init(parse_patterns(ps), (int)hdr[2]);
  long data = ftell(f);
  const size_t chunk = 1 << 20;
  std::vector<float> buf(chunk);
  for (int pass = 0; pass < 2; pass++) {
    fseek(f, data, SEEK_SET);
    for (int st = 0; st < q.nstages; st++) {
      float m = 0;
      for (size_t i = 0; i < q.stage_size; i += chunk) {
        size_t n = std::min(chunk, q.stage_size - i);
        if (fread(buf.data(), sizeof(float), n, f) != n) throw std::runtime_error("short weight file");
        if (pass == 0) {
          for (size_t j = 0; j < n; j++) m = std::max(m, fabsf(buf[j]));
        } else {
          float inv = 1.0f / q.scale[st];
          int16_t* dst = q.w + st * q.stage_size + i;
          for (size_t j = 0; j < n; j++) dst[j] = (int16_t)lrintf(buf[j] * inv);
        }
      }
      if (pass == 0) q.scale[st] = m > 0 ? m / 32767.0f : 1.0f;
    }
  }
  fclose(f);
}

}  // namespace nt
