// Packs float n-tuple weights into the serving format of wpack.h and checks it (workstream serve, 2026-10-07).
//
//   wpack_tool pack IN.w OUT.wp --kind int16|int8 --caps R0,R1,...  [--esc-q Q]
//       R per stage: the rank cap (base of the re-indexed tables, 2-16) or "c" (a constant stage: the stage's
//       initial value everywhere; automatic for an untrained stage). Reports trained entries lost by a cap.
//       int8: per table, the step is the Q-quantile (default 0.995) of |w - init| over the trained entries / 127;
//       larger values are stored exactly as escapes.
//   wpack_tool unpack IN.wp OUT.w          float weights with the packed values (for build/play strength tests)
//   wpack_tool check IN.w IN.wp [N]        N random late-game-like boards per stage: packed vs nt::load_quantized
//                                          (int16, the engine's own) evaluations, and evaluation speed
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#include "board.h"
#include "ntuple.h"
#include "wpack.h"

using namespace std;

static void die(const string& m) {
  fprintf(stderr, "%s\n", m.c_str());
  exit(1);
}

struct FloatFile {
  string pats;
  uint32_t nstages = 0;
  long data = 0;
  size_t per = 0, npat = 0;
  FILE* f = nullptr;
  void open(const string& path) {
    f = fopen(path.c_str(), "rb");
    if (!f) die("cannot read " + path);
    uint32_t hdr[3];
    if (fread(hdr, sizeof hdr, 1, f) != 1 || hdr[0] != 0x32303438u) die("bad weight file " + path);
    pats.resize(hdr[1]);
    if (fread(&pats[0], 1, pats.size(), f) != pats.size()) die("bad weight file");
    nstages = hdr[2];
    data = ftell(f);
    auto ps = nt::parse_patterns(pats);
    npat = ps.size();
    per = ps[0].size;
  }
  void stage(uint32_t s, vector<float>& buf) {
    buf.resize(npat * per);
    fseek(f, data + (long)(s * npat * per * 4), SEEK_SET);
    if (fread(buf.data(), 4, buf.size(), f) != buf.size()) die("short weight file");
  }
};

// the most common value of a table (sampled), the "initial" value of untrained entries
static float mode_of(const float* t, size_t n) {
  map<float, size_t> c;
  for (size_t i = 0; i < n; i += 97) c[t[i]]++;
  float best = 0;
  size_t bc = 0;
  for (auto& kv : c)
    if (kv.second > bc) bc = kv.second, best = kv.first;
  return best;
}

static uint32_t base_r(uint32_t x16, uint32_t R, bool* ok) {  // base-16 24-bit index -> base-R index
  uint32_t v = 0, m = 1;
  *ok = true;
  for (int k = 0; k < 6; k++) {
    uint32_t d = (x16 >> (4 * k)) & 15;
    if (d >= R) *ok = false;
    v += d * m, m *= R;
  }
  return v;
}

static int pack(int argc, char** argv) {
  if (argc < 4) die("usage: wpack_tool pack IN.w OUT.wp --kind int16|int8 --caps R0,R1,... [--esc-q Q]");
  string in = argv[2], out = argv[3], kind = "int16", caps;
  double esc_q = 0.995;
  for (int i = 4; i < argc; i++) {
    string a = argv[i];
    if (a == "--kind" && i + 1 < argc) kind = argv[++i];
    else if (a == "--caps" && i + 1 < argc) caps = argv[++i];
    else if (a == "--esc-q" && i + 1 < argc) esc_q = atof(argv[++i]);
    else die("unknown option " + a);
  }
  FloatFile F;
  F.open(in);
  vector<string> cap;
  for (size_t p = 0; p <= caps.size();) {
    size_t q = caps.find(',', p);
    if (q == string::npos) q = caps.size();
    if (q > p) cap.push_back(caps.substr(p, q - p));
    p = q + 1;
  }
  FILE* o = fopen((out + ".tmp").c_str(), "wb");
  if (!o) die("cannot write " + out);
  auto wr = [&](const void* p, size_t n) { fwrite(p, 1, n, o); };
  uint32_t magic = 0x314B5057u, plen = (uint32_t)F.pats.size();
  wr(&magic, 4), wr(&plen, 4), wr(F.pats.data(), plen), wr(&F.nstages, 4);
  vector<float> buf;
  size_t total_bytes = 0;
  for (uint32_t s = 0; s < F.nstages; s++) {
    F.stage(s, buf);
    // the stage's initial value: the mode of its first table; trained = differs from it
    float init = mode_of(buf.data(), F.per);
    size_t trained = 0;
    float m = 0;
    for (float x : buf) trained += x != init, m = max(m, fabsf(x));
    string c = s < cap.size() ? cap[s] : "16";
    uint32_t k = trained == 0 || c == "c" ? wpack::kConst : kind == "int8" ? wpack::kInt8 : wpack::kInt16;
    uint32_t R = k == wpack::kConst ? 16 : (uint32_t)atoi(c.c_str());
    if (k != wpack::kConst && (R < 2 || R > 16)) die("bad cap " + c);
    // int16: exactly nt::load_quantized's values (per-stage scale over all entries)
    float scale = m > 0 ? m / 32767.0f : 1.0f, inv = 1.0f / scale;
    int16_t q_init = (int16_t)lrintf(init * inv);
    wr(&k, 4), wr(&R, 4), wr(&init, 4), wr(&scale, 4), wr(&q_init, 2);
    if (k == wpack::kConst) {
      fprintf(stderr, "stage %u: constant %.3f (%zu trained entries dropped)\n", s, init, trained);
      continue;
    }
    uint32_t r6 = R * R * R * R * R * R;
    size_t lost = 0, escapes = 0;
    for (size_t p = 0; p < F.npat; p++) {
      const float* t = buf.data() + p * F.per;
      // trained entries beyond the cap are lost (answered by the initial value)
      vector<uint32_t> map16(r6);
      for (uint32_t x = 0; x < F.per; x++) {
        bool ok;
        uint32_t i = base_r(x, R, &ok);
        if (ok) map16[i] = x;
        else lost += t[x] != init;
      }
      if (k == wpack::kInt16) {
        float step = 0;
        wr(&step, 4);
        vector<int16_t> q(r6);
        for (uint32_t i = 0; i < r6; i++) q[i] = (int16_t)lrintf(t[map16[i]] * inv);
        wr(q.data(), r6 * 2);
        total_bytes += r6 * 2;
      } else {
        vector<float> d;
        for (uint32_t i = 0; i < r6; i++)
          if (t[map16[i]] != init) d.push_back(fabsf(t[map16[i]] - init));
        float step = 1;
        if (!d.empty()) {
          size_t qi = min(d.size() - 1, (size_t)(esc_q * (double)(d.size() - 1)));
          nth_element(d.begin(), d.begin() + qi, d.end());
          step = max(1e-3f, d[qi] / 127.0f);
        }
        wr(&step, 4);
        vector<int8_t> q(r6);
        vector<uint32_t> ei;
        vector<float> ev;
        for (uint32_t i = 0; i < r6; i++) {
          float dv = t[map16[i]] - init;
          long r = lrintf(dv / step);
          if (r >= -127 && r <= 127) q[i] = (int8_t)r;
          else q[i] = -128, ei.push_back(i), ev.push_back(dv);
        }
        uint32_t ne = (uint32_t)ei.size();
        escapes += ne;
        wr(q.data(), r6), wr(&ne, 4);
        if (ne) wr(ei.data(), ne * 4), wr(ev.data(), ne * 4);
        total_bytes += r6 + ne * 8;
      }
    }
    fprintf(stderr, "stage %u: %s, cap %u (%u^6 = %u entries per table), init %.3f, trained %zu, lost by the cap %zu"
            "%s\n", s, k == wpack::kInt16 ? "int16" : "int8", R, R, r6, init, trained, lost,
            k == wpack::kInt8 ? (", escapes " + to_string(escapes)).c_str() : "");
  }
  fclose(o);
  rename((out + ".tmp").c_str(), out.c_str());
  fprintf(stderr, "-> %s (%.1f MB of tables)\n", out.c_str(), total_bytes / 1e6);
  return 0;
}

static int unpack(int argc, char** argv) {
  if (argc < 4) die("usage: wpack_tool unpack IN.wp OUT.w");
  wpack::PackedNet P;
  P.load(argv[2]);
  string out = argv[3];
  FILE* o = fopen((out + ".tmp").c_str(), "wb");
  if (!o) die("cannot write " + out);
  string ps = nt::pattern_string(P.pats);
  uint32_t hdr[3] = {0x32303438u, (uint32_t)ps.size(), (uint32_t)P.nstages};
  fwrite(hdr, sizeof hdr, 1, o);
  fwrite(ps.data(), 1, ps.size(), o);
  size_t per = P.pats[0].size;
  vector<float> buf(per);
  for (int s = 0; s < P.nstages; s++)
    for (size_t p = 0; p < P.pats.size(); p++) {
      for (size_t x = 0; x < per; x++) buf[x] = P.weight(s, p, x);
      fwrite(buf.data(), 4, per, o);
    }
  fclose(o);
  rename((out + ".tmp").c_str(), out.c_str());
  fprintf(stderr, "-> %s\n", out.c_str());
  return 0;
}

// random boards resembling a stage: a snake of descending big tiles plus small junk, tile sums spread over the stage
static board_t random_board(bb::Rng& rng, int top) {
  board_t b = 0;
  static const int path[16] = {0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11, 15, 14, 13, 12};
  int r = top, i = 0;
  for (; i < 16 && r >= 1; i++) {
    b = bb::set_cell(b, path[i], r);
    r -= 1 + (int)rng.below(2);
    if (rng.below(3) == 0) break;
  }
  for (int c = 0; c < 16; c++)
    if (!bb::cell(b, c) && rng.below(3)) b = bb::set_cell(b, c, 1 + rng.below(std::max(1, top - 3)));
  return b;
}

static int check(int argc, char** argv) {
  if (argc < 4) die("usage: wpack_tool check IN.w IN.wp [N]");
  int N = argc > 4 ? atoi(argv[4]) : 200000;
  nt::Net<int16_t> Q;
  nt::load_quantized(argv[2], Q);
  wpack::PackedNet P;
  P.load(argv[3]);
  fprintf(stderr, "packed tables: %.1f MB (int16 reference: %.1f MB)\n", P.bytes() / 1e6, Q.total * 2 / 1e6);
  bb::Rng rng(12345);
  for (int s = 0; s < P.nstages; s++) {
    double mx = 0, sum = 0, ref = 0;
    unsigned long long beyond0 = P.beyond_cap;
    vector<board_t> bs;
    for (int k = 0; k < N; k++) bs.push_back(random_board(rng, 9 + (s + k) % 6));
    auto t0 = chrono::steady_clock::now();
    double acc = 0;
    for (auto b : bs) acc += Q.eval(b, s);
    auto t1 = chrono::steady_clock::now();
    for (auto b : bs) acc -= P.eval(b, s);
    auto t2 = chrono::steady_clock::now();
    for (auto b : bs) {
      double a = Q.eval(b, s), c = P.eval(b, s);
      mx = max(mx, fabs(a - c)), sum += fabs(a - c), ref += fabs(a);
    }
    double tq = chrono::duration<double, nano>(t1 - t0).count() / N, tp = chrono::duration<double, nano>(t2 - t1).count() / N;
    fprintf(stderr, "stage %d: |packed - int16| max %.3f, mean %.4f (mean |value| %.1f); beyond-cap lookups %llu; eval "
            "%.0f ns (int16 %.0f ns) [%g]\n", s, mx, sum / N, ref / N, P.beyond_cap - beyond0, tp, tq, acc * 0);
  }
  return 0;
}

int main(int argc, char** argv) {
  if (argc < 2) die("usage: wpack_tool pack|unpack|check ...");
  string c = argv[1];
  if (c == "pack") return pack(argc, argv);
  if (c == "unpack") return unpack(argc, argv);
  if (c == "check") return check(argc, argv);
  die("unknown command " + c);
}
