#!/usr/bin/env python3
"""Workstream hm3: do humans play more carefully in danger? The human move model of hm (full_tied_death_recent,
scripts/hm_fit.py) with STATE-DEPENDENT care: the value skill and the structure weight are multiplied by
exp(c . z(position)), and the lapse rate by exp(ce . z), where z are features of the position before the move:
  tight  : empty cells <= 2              mid : 3-5 empty cells
  danger : the death share of the safest move (spawns after the best-for-survival move that leave no legal move)
  few    : at most 2 legal moves
Same evaluation as hm_fit.py (5 folds by player; test players' skill fitted on the first half of their decisions,
NLL on the second half). Also prints the coefficients of a fit on all players.
usage: hm3_fit.py [variants...]   variants: base, care_tight, care_all, care_all_eps, care_s (structure only) ..."""
import json, sys, time
import numpy as np
import torch
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import hm_fit as H

BASE = 'full_tied_death_recent'

def zfeats(D):
    F = D['F']
    fn = list(D['feats'])
    e0 = np.nan_to_num(F[:, 0, fn.index('empty')], nan=0.0)
    legal = D['legal']
    death = np.nan_to_num(D['death'], nan=1.0)
    death_min = np.where(legal, death, 9.0).min(1)
    death_min = np.where(death_min > 1.0, 0.0, death_min)
    nleg = legal.sum(1)
    z = np.stack([(e0 <= 2) * 1.0, ((e0 >= 3) & (e0 <= 5)) * 1.0, death_min, (nleg <= 2) * 1.0], -1)
    return z, ['tight', 'mid', 'danger', 'few']

class CareModel(H.Model):
    def __init__(self, kv, ks, kh, nplayers, two_skill, kz, mode):
        super().__init__(kv, ks, kh, nplayers, two_skill)
        self.mode = mode
        self.cv_ = torch.nn.Parameter(torch.zeros(kz)) if 'v' in mode else None   # value skill
        self.cs_ = torch.nn.Parameter(torch.zeros(kz)) if 's' in mode else None   # structure weight
        self.ce_ = torch.nn.Parameter(torch.zeros(kz)) if 'e' in mode else None   # lapse

    def logp(self, B, idx):
        V = B['Vt'][idx]
        Z = B['Zt'][idx]
        th = self.theta[B['pt'][idx]]
        lv = th + (Z @ self.cv_ if self.cv_ is not None else 0.0)
        z = torch.exp(lv)[:, None] * (V @ self.wv)
        if self.ws is not None:
            zs = B['St'][idx] @ self.ws
            g = self.gab[0] + self.gab[1] * th
            if self.cs_ is not None: g = g + Z @ self.cs_
            z = z + zs * torch.exp(g)[:, None]
        if self.wh is not None: z = z + B['Ht'][idx] @ self.wh
        lg = B['lt'][idx]
        z = torch.where(lg, z, torch.tensor(-1e30))
        ls = torch.log_softmax(z, -1)
        le = self.leps + (Z @ self.ce_ if self.ce_ is not None else 0.0)
        eps = torch.sigmoid(le)[:, None] if self.ce_ is not None else torch.sigmoid(self.leps)
        nl = lg.sum(-1, keepdim=True)
        p = (1 - eps) * torch.exp(ls) + eps / nl
        p = torch.where(lg, p, torch.tensor(1e-300))
        return torch.log(p)

def run(D, variant, folds=5):
    B = H.build(D, BASE)
    T = H.tensors(B)
    z, zn = zfeats(D)
    cols = {'care_tight': [0], 'care_all': [0, 1, 2, 3]}.get(variant.split('+')[0], [0, 1, 2, 3])
    T['Zt'] = torch.tensor(z[:, cols])
    mode = {'base': '', 'care_tight': 'vs', 'care_all': 'vs', 'care_v': 'v', 'care_s': 's'}.get(variant.split('+')[0], 'vs')
    if '+eps' in variant: mode += 'e'
    n = len(B['played'])
    nplayers = int(B['player'].max()) + 1
    rng = np.random.RandomState(0)
    perm = rng.permutation(nplayers)
    fold_of = np.zeros(nplayers, dtype=int)
    for k, p in enumerate(perm): fold_of[p] = k % folds
    half = np.zeros(n, dtype=bool)
    for p in range(nplayers):
        ix = np.where(B['player'] == p)[0]
        half[ix[len(ix) // 2:]] = True
    kv = B['V'].shape[2]; ks = B['S'].shape[2]; kh = B['H'].shape[2]
    out = np.full(n, np.nan)
    for k in range(folds):
        test_p = np.where(fold_of == k)[0]; train_p = np.where(fold_of != k)[0]
        tr = np.where(np.isin(B['player'], train_p))[0]
        m = CareModel(kv, ks, kh, nplayers, 'tied', len(cols), mode)
        m._train_players = torch.tensor(train_p)
        H.fit_global(m, T, torch.tensor(tr), train_p)
        cal = np.where(np.isin(B['player'], test_p) & ~half)[0]
        te = np.where(np.isin(B['player'], test_p) & half)[0]
        H.fit_players(m, T, torch.tensor(cal), torch.tensor(test_p))
        with torch.no_grad():
            out[te] = H.nll(m, T, torch.tensor(te)).numpy()
    ok = ~np.isnan(out)
    res = dict(variant=variant, nll=float(out[ok].mean()))
    for t in range(4):
        s = ok & (B['tier'] == t); res[f'tier{t}'] = float(out[s].mean())
    s = ok & (z[:, 0] > 0); res['tight'] = float(out[s].mean())
    # the final fit on all players: coefficients
    m = CareModel(kv, ks, kh, nplayers, 'tied', len(cols), mode)
    m._train_players = torch.arange(nplayers)
    H.fit_global(m, T, torch.arange(n), np.arange(nplayers))
    for nm in ('cv_', 'cs_', 'ce_'):
        p = getattr(m, nm)
        if p is not None: res[nm] = {zn[c]: round(float(v), 3) for c, v in zip(cols, p.detach().numpy())}
    res['gab'] = [round(float(x), 3) for x in m.gab.detach().numpy()]
    res['eps'] = float(torch.sigmoid(m.leps))
    return res, m

if __name__ == '__main__':
    D = dict(np.load('results/hm/data.npz'))
    try:
        R = np.load('results/hm/recent.npz'); D['_recent'] = (R['cnt'], R['hl'])
    except OSError:
        pass
    for v in sys.argv[1:] or ['base', 'care_all', 'care_all+eps']:
        t0 = time.time()
        res, m = run(D, v)
        res['secs'] = round(time.time() - t0)
        print(json.dumps(res), flush=True)
        with open('results/hm3/care_cv.jsonl', 'a') as f: f.write(json.dumps(res) + '\n')
