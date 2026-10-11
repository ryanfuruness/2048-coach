// Your chance (workstream yc, 2026-10-10): the human player's own chance of reaching the next milestone (2048, then
// each doubling of the largest tile) from an afterstate, for the simulated human players of the personal odds
// (src/hplayer.h) at a few model keys. Learned by TD evaluation of the player's policy (build/hv_tool train): the
// engine's own odds and values say what the ENGINE would make of a position (it repairs almost anything early on);
// this says what a player who moves like you would.
//
// Per key and stage (the afterstate's largest tile: <= 64, 128, 256, 512, 1024, 2048, 4096, 8192) a logistic n-tuple
// network: V(a) = sigmoid(z), z = sum over patterns and the 8 symmetries of w[pattern index] + global tables over a
// few whole-board features (the largest tile's distance to a corner x empty cells, chain length, exposed cells,
// trapped tiles, big tiles off the edge, merges). Between keys the chance is interpolated in logit space, linear in
// log key (as the personal odds).
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "board.h"
#include "explain.h"
#include "ntuple.h"

namespace hv {

constexpr int kStages = 8;
// Stage of an afterstate by its largest tile's rank; -1 beyond the modelled milestones (a 16384 or more).
static inline int stage_of_rank(int r) { return r <= 6 ? 0 : r <= 13 ? r - 6 : -1; }
static inline int stage_of(board_t a) { return stage_of_rank(bb::max_rank(a)); }
// The milestone (rank) a position plays for: 2048 first, then each doubling of the largest tile.
static inline int milestone_rank(board_t b) { return std::max(11, bb::max_rank(b) + 1); }

// Global feature tables (sizes per stage)
enum Glob { kGCornerEmpty, kGChain, kGExposed, kGTrapped, kGOffEdge, kGMerges, kNumGlob };
constexpr int kGlobSize[kNumGlob] = {3 * 17, 16, 16, 16, 16, 24};
static inline void glob_index(board_t a, int idx[kNumGlob]) {
  ex::Features f = ex::features(a);
  int cd = std::min(f.corner_dist, 2);
  idx[kGCornerEmpty] = cd * 17 + std::min(f.empty, 16);
  idx[kGChain] = std::min(f.chain_len, 15);
  idx[kGExposed] = std::min(f.exposed, 15);
  idx[kGTrapped] = std::min(f.trapped, 15);
  idx[kGOffEdge] = std::min(f.big_off_edge, 15);
  idx[kGMerges] = std::min(f.merges, 23);
}

static inline double sigmoid(double z) { return 1.0 / (1.0 + std::exp(-std::max(-30.0, std::min(30.0, z)))); }
static inline double logit(double p) {
  p = std::min(1 - 1e-6, std::max(1e-6, p));
  return std::log(p / (1 - p));
}

// One key's networks (all stages).
struct Net {
  std::vector<nt::Pattern> pats;
  std::vector<size_t> poff;  // offset of pattern p within a stage
  size_t gbase = 0;          // offset of the global tables within a stage
  size_t goff[kNumGlob] = {};
  size_t stage_size = 0;
  std::vector<float> w;      // kStages * stage_size
  double key = 0;
  // Recalibration per stage (build/hv_tool recal): the chance is sigmoid(cal_a + cal_b * z) - TD with a small network
  // leaves the chances a few points low; the map is fitted on the outcomes of the player's games from real positions.
  float cal_a[kStages], cal_b[kStages];

  void init(const std::string& patterns, double k) {
    pats = nt::parse_patterns(patterns);
    key = k;
    poff.clear();
    stage_size = 0;
    for (auto& p : pats) poff.push_back(stage_size), stage_size += p.size;
    gbase = stage_size;
    for (int g = 0; g < kNumGlob; g++) goff[g] = stage_size, stage_size += kGlobSize[g];
    w.assign(kStages * stage_size, 0.0f);
    for (int st = 0; st < kStages; st++) cal_a[st] = 0.0f, cal_b[st] = 1.0f;
  }
  double zc(board_t a, int st) const { return cal_a[st] + cal_b[st] * z(a, st); }  // the calibrated logit
  int features() const { return 8 * (int)pats.size() + kNumGlob; }

  // The logit of afterstate a (stage st = stage_of(a) >= 0).
  double z(board_t a, int st) const {
    board_t s[8];
    bb::symmetries(a, s);
    const float* base = w.data() + st * stage_size;
    double v = 0;
    for (size_t p = 0; p < pats.size(); p++) {
      const float* t = base + poff[p];
      uint64_t m = pats[p].mask;
      float x = (t[bb::pext_nib(s[0], m)] + t[bb::pext_nib(s[1], m)]) + (t[bb::pext_nib(s[2], m)] + t[bb::pext_nib(s[3], m)]);
      float y = (t[bb::pext_nib(s[4], m)] + t[bb::pext_nib(s[5], m)]) + (t[bb::pext_nib(s[6], m)] + t[bb::pext_nib(s[7], m)]);
      v += x + y;
    }
    int gi[kNumGlob];
    glob_index(a, gi);
    for (int g = 0; g < kNumGlob; g++) v += base[goff[g] + gi[g]];
    return v;
  }
  // P(milestone) from afterstate a: 1 if a already holds its milestone's tile... (callers check), else sigmoid(z).
  double v(board_t a) const {
    int st = stage_of(a);
    return st < 0 ? 1.0 : sigmoid(z(a, st));
  }
  // TD step: every active weight moves by step / features() (step = learning rate x (target - V) on the logit's
  // cross-entropy gradient).
  void update(board_t a, double step) {
    int st = stage_of(a);
    if (st < 0) return;
    board_t s[8];
    bb::symmetries(a, s);
    float* base = w.data() + st * stage_size;
    float d = (float)(step / features());
    for (size_t p = 0; p < pats.size(); p++) {
      float* t = base + poff[p];
      uint64_t m = pats[p].mask;
      for (int k = 0; k < 8; k++) t[bb::pext_nib(s[k], m)] += d;
    }
    int gi[kNumGlob];
    glob_index(a, gi);
    for (int g = 0; g < kNumGlob; g++) base[goff[g] + gi[g]] += d;
  }
};

// A family of networks (one per key), as the analysis loads it.
struct Family {
  std::vector<std::unique_ptr<Net>> nets;  // sorted by key, descending (weakest first)

  bool ok() const { return !nets.empty(); }

  static void save_net(FILE* f, const Net& n) {
    std::string ps = nt::pattern_string(n.pats);
    uint32_t len = (uint32_t)ps.size();
    fwrite(&n.key, sizeof(double), 1, f);
    fwrite(&len, 4, 1, f);
    fwrite(ps.data(), 1, len, f);
    uint64_t sz = n.w.size();
    fwrite(&sz, 8, 1, f);
    fwrite(n.w.data(), sizeof(float), n.w.size(), f);
    fwrite(n.cal_a, sizeof(float), kStages, f);
    fwrite(n.cal_b, sizeof(float), kStages, f);
  }
  void save(const std::string& path) const {
    std::string tmp = path + ".tmp";
    FILE* f = fopen(tmp.c_str(), "wb");
    if (!f) throw std::runtime_error("cannot write " + path);
    uint32_t hdr[3] = {0x32305648u, (uint32_t)nets.size(), (uint32_t)kStages};  // "HV02" (HV01: no calibration)
    fwrite(hdr, sizeof hdr, 1, f);
    for (auto& n : nets) save_net(f, *n);
    fclose(f);
    rename(tmp.c_str(), path.c_str());
  }
  // Appends the networks of a file (several files may be loaded: one per key while training).
  bool load(const std::string& path) {
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return false;
    uint32_t hdr[3];
    bool good = fread(hdr, sizeof hdr, 1, f) == 1 && (hdr[0] == 0x31305648u || hdr[0] == 0x32305648u) &&
                hdr[2] == (uint32_t)kStages;
    bool has_cal = good && hdr[0] == 0x32305648u;
    for (uint32_t i = 0; good && i < hdr[1]; i++) {
      double key;
      uint32_t len;
      if (fread(&key, sizeof key, 1, f) != 1 || fread(&len, 4, 1, f) != 1 || len > 4096) {
        good = false;
        break;
      }
      std::string ps(len, ' ');
      uint64_t sz;
      if (fread(&ps[0], 1, len, f) != len || fread(&sz, 8, 1, f) != 1) {
        good = false;
        break;
      }
      std::unique_ptr<Net> n(new Net);
      n->init(ps, key);
      if (n->w.size() != sz || fread(n->w.data(), sizeof(float), sz, f) != sz) {
        good = false;
        break;
      }
      if (has_cal && (fread(n->cal_a, sizeof(float), kStages, f) != (size_t)kStages ||
                      fread(n->cal_b, sizeof(float), kStages, f) != (size_t)kStages)) {
        good = false;
        break;
      }
      nets.push_back(std::move(n));
    }
    fclose(f);
    std::sort(nets.begin(), nets.end(), [](const std::unique_ptr<Net>& a, const std::unique_ptr<Net>& b) {
      return a->key > b->key;
    });
    return good && !nets.empty();
  }
  // P(milestone of `milestone` rank) after afterstate a for a player of model key k: 1 if a holds the milestone,
  // else the networks of the two nearest keys, interpolated in logit space linear in log key (clamped to the ends).
  double v(board_t a, int milestone, double k) const {
    if (bb::max_rank(a) >= milestone) return 1.0;
    int st = stage_of(a);
    if (st < 0 || nets.empty()) return 1.0;
    if (k >= nets.front()->key) return sigmoid(nets.front()->zc(a, st));
    if (k <= nets.back()->key) return sigmoid(nets.back()->zc(a, st));
    for (size_t i = 0; i + 1 < nets.size(); i++) {
      double k0 = nets[i]->key, k1 = nets[i + 1]->key;  // k0 > k >= k1
      if (k <= k0 && k >= k1) {
        double t = (std::log(k0) - std::log(k)) / (std::log(k0) - std::log(k1));
        return sigmoid((1 - t) * nets[i]->zc(a, st) + t * nets[i + 1]->zc(a, st));
      }
    }
    return sigmoid(nets.back()->zc(a, st));
  }
};

}  // namespace hv
