#!/usr/bin/env python3
"""Late-game refit of the human move model on best_v6b values (workstream hm2): a separate value hinge for positions
with a tile sum >= 20480 (where best_v6b's late networks give the 1-ply values), every other weight fixed at
results/hm/human_model_v2.txt (so play below 20480 - the personal model's territory - is unchanged). Fitted by
maximum likelihood with the players' skills (N(0, 1) prior around their mean, as hm_fit.py); 5-fold CV by player
(test players' skill on the first half of their decisions, scored on the second half) against the unchanged model.
usage: hm_late_refit.py [--data results/hm2/v6b/data.npz] [--out results/hm2/human_model_late.txt] [--late-search]"""
import sys
import numpy as np
import torch
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import hm_fit
from hm_skill_real import load_model

torch.set_default_dtype(torch.float64)
KN = [0.0, 0.003, 0.01, 0.03, 0.1, 0.3]

def main():
    args = sys.argv[1:]
    data = args[args.index('--data') + 1] if '--data' in args else 'results/hm2/v6b/data.npz'
    out = args[args.index('--out') + 1] if '--out' in args else 'results/hm2/human_model_late.txt'
    D = dict(np.load(data))
    R = np.load(data.replace('data.npz', 'recent.npz')); D['_recent'] = (R['cnt'], R['hl'])
    B = hm_fit.build(D, 'full_tied_death_recent')
    if '--late-search' in args:  # late rows: the hinge of the SEARCH loss (analyze's scale) instead of the 1-ply loss
        BS = hm_fit.build(D, 'full_tied_death_recent_search')
        lt = D['tsum'] >= 20480
        B['V'][lt] = BS['V'][lt]
    M = load_model('results/hm/human_model_v2.txt')
    names_v, names_s, names_h = B['names']
    V = torch.tensor(B['V']); Sw = torch.tensor(B['S'] @ np.array([M['ws'][k] for k in names_s]))
    Hw = torch.tensor(B['H'] @ np.array([M['wh'][k] for k in names_h]))
    lg = torch.tensor(B['legal']); pl = torch.tensor(B['player']); played = torch.tensor(B['played'])
    late = torch.tensor(D['tsum'] >= 20480)
    wv0 = torch.tensor(M['wv'])
    eps, ga, gb = M['eps'], M['ga'], M['gb']
    big = torch.tensor(np.nan_to_num(D['losss'], nan=0.0) >= 0.15)
    stage = np.where(D['mx'] <= 512, 0, np.where(D['mx'] <= 2048, 1, np.where(D['mx'] <= 8192, 2, 3)))
    nplayers = int(B['player'].max()) + 1
    n = len(B['played'])

    def logp(idx, theta_all, wl):
        w = torch.where(late[idx][:, None], wl[None, :], wv0[None, :])          # (m, 6)
        v = (V[idx] * w[:, None, :]).sum(-1)                                     # (m, 4)
        th = theta_all[pl[idx]][:, None]
        z = torch.exp(th) * v + torch.exp(ga + gb * th) * Sw[idx] + Hw[idx]
        z = torch.where(lg[idx], z, torch.tensor(-1e30))
        p = (1 - eps) * torch.softmax(z, -1) + eps / lg[idx].sum(-1, keepdim=True)
        return torch.log(torch.where(lg[idx], p, torch.tensor(1e-300)))

    def fit(train_players, wl_init, refit_w=True, iters=150):
        theta = torch.zeros(nplayers, requires_grad=True)
        wl = wl_init.clone().requires_grad_(refit_w)
        idx = torch.where(torch.isin(pl, torch.tensor(train_players)))[0]
        params = [theta] + ([wl] if refit_w else [])
        opt = torch.optim.LBFGS(params, lr=1, max_iter=iters, line_search_fn='strong_wolfe')
        tp = torch.tensor(sorted(train_players))
        def closure():
            opt.zero_grad()
            L = logp(idx, theta, wl)
            loss = -L[torch.arange(len(idx)), played[idx]].sum() + ((theta[tp] - theta[tp].mean()) ** 2).sum() / 2
            loss.backward()
            return loss
        opt.step(closure)
        return wl.detach()

    def player_theta(idx, wl):
        """the grid ML skill of the decisions idx (as the review fits it)"""
        best, bth = -1e300, 0.0
        for th in np.arange(-3.0, 3.0001, 0.025):
            t = torch.full((nplayers,), float(th))
            L = logp(idx, t, wl)
            s = float(L[torch.arange(len(idx)), played[idx]].sum())
            if s > best: best, bth = s, th
        return bth

    rng = np.random.RandomState(0)
    perm = rng.permutation(nplayers)
    fold_of = np.zeros(nplayers, dtype=int)
    for k, p in enumerate(perm): fold_of[p] = k % 5
    res = {name: (np.full(n, np.nan), np.full(n, np.nan)) for name in ('v2', 'late')}
    for k in range(5):
        train = [p for p in range(nplayers) if fold_of[p] != k]
        wl = fit(train, wv0.clone())
        print(f"fold {k}: late value hinge " + ' '.join(f"{x:+.3f}" for x in wl.tolist()), flush=True)
        for p in [p for p in range(nplayers) if fold_of[p] == k]:
            ix = np.where(B['player'] == p)[0]
            a, b = torch.tensor(ix[:len(ix) // 2]), torch.tensor(ix[len(ix) // 2:])
            if len(a) < 20: continue
            for name, w in (('v2', wv0), ('late', wl)):
                th = player_theta(a, w)
                L = logp(b, torch.full((nplayers,), float(th)), w)
                res[name][0][b.numpy()] = (-L[torch.arange(len(b)), played[b]]).detach().numpy()
                res[name][1][b.numpy()] = (torch.exp(L) * (big[b] & lg[b])).sum(-1).detach().numpy()
    tsum_late = D['tsum'] >= 20480
    obs = np.nan_to_num(D['losss'], nan=0.0)[np.arange(n), B['played']] >= 0.15
    for name in ('v2', 'late'):
        nl, pb = res[name]
        ok = ~np.isnan(nl)
        print(f"{name:5s}: held-out nll {nl[ok].mean():.4f}  by stage " + ' '.join(f"{nl[ok & (stage == g)].mean():.4f}" for g in range(4)) +
              f"  sum>=20480 {nl[ok & tsum_late].mean():.4f}  sum<20480 {nl[ok & ~tsum_late].mean():.4f}")
        for t, tn in enumerate(('novice', 'intermediate', 'strong', 'expert')):
            for g in (2, 3):
                s = ok & (D['tier'] == t) & (stage == g)
                if s.sum() < 300: continue
                print(f"      {tn:12s} stage {g}: >= 15% moves per 100 predicted {100 * pb[s].mean():.2f} observed {100 * obs[s].mean():.2f} (n={int(s.sum())})")
    wl = fit(list(range(nplayers)), wv0.clone())
    with open(out, 'w') as f:
        f.write("# human move model: value hinge for tile sums >= 20480 refit on best_v6b values (scripts/hm_late_refit.py)\n")
        f.write("wv_late " + ' '.join(f"{k:g} {w:.6f}" for k, w in zip(KN, wl.tolist())) + "\n")
    print("final late hinge -> " + out + ": " + ' '.join(f"{x:+.3f}" for x in wl.tolist()))

if __name__ == '__main__':
    main()
