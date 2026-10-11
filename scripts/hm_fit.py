#!/usr/bin/env python3
"""Human move model (workstream hm), step 2: fit and compare models of human move choice on results/hm/data.npz.

Every model is a conditional logit over the legal moves, mixed with a lapse:
  P(d) = (1 - eps) * softmax_d( s_p * V(d) + S(d) * g_p + H(d) ) + eps / n_legal
  V(d): value part, from the move's relative 1-ply loss (soft_move's scale) [and/or the search loss]
  S(d): structure part (concept features of the afterstate, direction class relative to the biggest tile's wall)
  H(d): habits (repeat the previous move, alternate with the one before)
  s_p = exp(theta_p): the player's skill (inverse temperature of the value part), g_p = exp(gamma_p) optional
Models:
  soft    : V = -loss1 (the softmax player: s_p = 1/t), no S, no H (+ lapse)
  hinge   : V = hinge basis of loss1 (non-linear: near-ties vs real losses)
  full    : hinge + S + H
  full2   : full with a separate skill multiplier on S (g_p)
  ... + 'stage' variants: V's hinge weights per stage group (max tile <= 512, 1024-2048, 4096-8192, 16384+)
Evaluation (5 folds by player): global weights on the training players (their theta jointly, with a N(0, 1) prior
on theta - mean); for each test player theta (and gamma) is fitted on the first half of the player's decisions (in
data order) with the weights fixed, and the second half is scored: mean negative log-likelihood per decision.
usage: hm_fit.py [models...] [--data results/hm/data.npz] [--save MODEL.json]"""
import json, math, sys, time
import numpy as np
import torch

torch.set_default_dtype(torch.float64)
KNOTS = [0.0, 0.003, 0.01, 0.03, 0.1, 0.3]
DIR_PRIOR = 3.0  # sd of the per-player direction biases

def stage_of(mx):
    return np.where(mx <= 512, 0, np.where(mx <= 2048, 1, np.where(mx <= 8192, 2, 3)))

def dir_classes(ranks, mcell):
    """(n, 4) class of each direction relative to the biggest tile's corner and wall line:
    0 perp_toward (pushes the wall line against its wall), 1 line_toward (along the line, into the corner),
    2 line_away, 3 perp_away (pulls the line off its wall)"""
    n = len(mcell)
    r, c = mcell // 4, mcell % 4
    vt = np.where(r < 2, 0, 2)    # up / down
    ht = np.where(c < 2, 3, 1)    # left / right
    R = ranks.astype(np.int64)
    tiles = np.where(R > 0, 2.0 ** R, 0.0).reshape(n, 4, 4)
    rowsum = tiles[np.arange(n), r, :].sum(1)
    colsum = tiles[np.arange(n), :, c].sum(1)
    horiz = rowsum >= colsum
    opp = lambda d: (d + 2) % 4
    perp_t = np.where(horiz, vt, ht); line_t = np.where(horiz, ht, vt)
    cls = np.zeros((n, 4), dtype=np.int64)
    for d in range(4):
        cls[:, d] = np.where(d == perp_t, 0, np.where(d == line_t, 1, np.where(d == opp(line_t), 2, 3)))
    return cls

RECENT = 20  # moves of history for the habit features

def recent_hist(D):
    """(n, 4) counts of each direction among the player's previous RECENT moves in the same segment (consecutive
    plies; the history restarts at a gap), and (n,) history length"""
    n = len(D['played'])
    key = list(zip(D['video'], D['seg'], D['ply']))
    order = sorted(range(n), key=lambda i: key[i])
    cnt = np.zeros((n, 4)); hl = np.zeros(n)
    hist = []
    last = None
    for i in order:
        v, sg, pl = key[i]
        if last is None or last[0] != v or last[1] != sg or pl != last[2] + 1: hist = []
        h = hist[-RECENT:]
        for d in h: cnt[i, d] += 1
        hl[i] = len(h)
        hist.append(int(D['played'][i]))
        last = (v, sg, pl)
    return cnt, hl

def build(D, model):
    n = len(D['played'])
    legal = D['legal']
    L1 = np.nan_to_num(D['loss1'], nan=0.0)
    LS = np.nan_to_num(D['losss'], nan=0.0)
    st = stage_of(D['mx'])
    V = []
    names_v = []
    use_search = 'search' in model
    L2 = np.nan_to_num(D['loss2'], nan=0.0)
    base = LS if use_search else L2 if '2ply' in model else L1
    if model.startswith('soft'):
        V.append(-base); names_v.append('loss')
    else:
        for k in KNOTS:
            V.append(-np.maximum(0.0, base - k)); names_v.append(f'h{k}')
        if 'both' in model:
            for k in KNOTS:
                V.append(-np.maximum(0.0, LS - k)); names_v.append(f'hs{k}')
    V = np.stack(V, -1)  # (n, 4, kv)
    if 'stage' in model:
        Vs = np.zeros(V.shape[:2] + (V.shape[2] * 4,))
        for g in range(4):
            Vs[st == g, :, g * V.shape[2]:(g + 1) * V.shape[2]] = V[st == g]
        names_v = [f'{x}@{g}' for g in range(4) for x in names_v]
        V = Vs
    S = None; names_s = []
    if model.startswith('full'):
        F = D['F']  # (n, 5, 11): row 0 = the position, 1..4 = afterstates of U R D L
        fn = list(D['feats'])
        A = np.nan_to_num(F[:, 1:, :], nan=0.0)
        P0 = np.nan_to_num(F[:, :1, :], nan=0.0)
        cols = []
        def col(name, x):
            cols.append(x); names_s.append(name)
        g = lambda k: A[:, :, fn.index(k)]
        g0 = lambda k: P0[:, :, fn.index(k)]
        col('corner', g('corner'))
        col('corner_lost', (g0('corner') > 0) * (g('corner') == 0) * 1.0)
        col('chain_len', g('chain_len'))
        col('chain_drop', np.maximum(0.0, g0('chain_len') - g('chain_len')))
        col('exposed', g('exposed'))
        col('trapped', g('trapped'))
        col('big_off_edge', g('big_off_edge'))
        col('corner_dist', g('corner_dist'))
        col('merges_next', g('merges'))
        col('empty', g('empty'))
        col('moved', g('moved') / 16.0)
        rw = D['reward']
        col('merge', (rw > 0) * 1.0)
        col('merge_size', np.log2(1.0 + rw) / 10.0)
        if '2ply' in model or 'death' in model:
            col('death', np.nan_to_num(D['death'], nan=0.0))
        cls = dir_classes(D['ranks'], D['mcell'])
        for k, nm in ((1, 'line_toward'), (2, 'line_away'), (3, 'perp_away')):
            col(nm, (cls == k) * 1.0)
        S = np.stack(cols, -1)
        if 'stage' in model:  # direction classes per stage group too (the corner habit grows with experience)
            extra = []
            for gg in (1, 2, 3):
                for k in (2, 3):
                    extra.append(((cls == k) & (st[:, None] == gg)) * 1.0); names_s.append(f'dir{k}@{gg}')
            S = np.concatenate([S, np.stack(extra, -1)], -1)
    H = None; names_h = []
    if model.startswith('full'):
        p1, p2 = D['prev1'], D['prev2']
        d = np.arange(4)[None, :]
        rep = (d == p1[:, None]) * 1.0
        alt = ((d == p2[:, None]) & (d != p1[:, None]) & (p2[:, None] >= 0)) * 1.0
        H = np.stack([rep, alt], -1); names_h = ['repeat', 'alternate']
        if 'recent' in model.split('_'):
            cnt, hl = D['_recent'] if '_recent' in D else recent_hist(D)
            share = cnt / np.maximum(1.0, hl)[:, None]
            full = (hl >= 10)[:, None]
            unused = ((cnt == 0) & full) * 1.0
            H = np.concatenate([H, share[..., None], unused[..., None]], -1); names_h += ['recent_share', 'unused']
    return dict(V=V, S=S, H=H, legal=legal, played=D['played'], names=(names_v, names_s, names_h),
                player=D['player'], stage=st, tier=D['tier'])

class Model(torch.nn.Module):
    def __init__(self, kv, ks, kh, nplayers, two_skill):
        super().__init__()
        self.wv = torch.nn.Parameter(torch.full((kv,), 10.0) if kv == 1 else torch.zeros(kv).fill_(5.0))
        self.ws = torch.nn.Parameter(torch.zeros(ks)) if ks else None
        self.wh = torch.nn.Parameter(torch.zeros(kh)) if kh else None
        self.theta = torch.nn.Parameter(torch.zeros(nplayers))
        self.gamma = torch.nn.Parameter(torch.zeros(nplayers)) if two_skill == 'free' else None
        # tied: the structure skill follows the value skill (gamma_p = ga + gb * theta_p): one skill parameter
        self.gab = torch.nn.Parameter(torch.tensor([0.0, 1.0])) if two_skill == 'tied' else None
        self.leps = torch.nn.Parameter(torch.tensor(-4.0))
        self.dirb = None  # per-player absolute direction biases (U R D L), set by Model.with_dirs

    def with_dirs(self, nplayers):
        self.dirb = torch.nn.Parameter(torch.zeros(nplayers, 4))
        return self

    def logp(self, B, idx):
        V = B['Vt'][idx]
        s = torch.exp(self.theta[B['pt'][idx]])[:, None]
        z = s * (V @ self.wv)
        if self.ws is not None:
            zs = B['St'][idx] @ self.ws
            if self.gamma is not None: zs = zs * torch.exp(self.gamma[B['pt'][idx]])[:, None]
            if self.gab is not None: zs = zs * torch.exp(self.gab[0] + self.gab[1] * self.theta[B['pt'][idx]])[:, None]
            z = z + zs
        if self.wh is not None: z = z + B['Ht'][idx] @ self.wh
        if self.dirb is not None: z = z + self.dirb[B['pt'][idx]]
        lg = B['lt'][idx]
        z = torch.where(lg, z, torch.tensor(-1e30))
        ls = torch.log_softmax(z, -1)
        eps = torch.sigmoid(self.leps)
        nl = lg.sum(-1, keepdim=True)
        p = (1 - eps) * torch.exp(ls) + eps / nl
        p = torch.where(lg, p, torch.tensor(1e-300))
        return torch.log(p)

def skill_kind(model):
    return 'tied' if 'tied' in model else 'free' if model.startswith('full2') else None

def tensors(B):
    T = dict(Vt=torch.tensor(B['V']), lt=torch.tensor(B['legal']), Pt=torch.tensor(B['played']),
             pt=torch.tensor(B['player']))
    if B['S'] is not None: T['St'] = torch.tensor(B['S'])
    if B['H'] is not None: T['Ht'] = torch.tensor(B['H'])
    return T

def nll(m, T, idx):
    lp = m.logp(T, idx)
    return -lp[torch.arange(len(idx)), T['Pt'][idx]]

def fit_global(m, T, idx, players, prior=1.0, iters=200):
    opt = torch.optim.LBFGS([p for p in m.parameters()], lr=1, max_iter=iters, line_search_fn='strong_wolfe')
    pl = torch.tensor(sorted(players))
    def closure():
        opt.zero_grad()
        th = m.theta[pl]
        reg = ((th - th.mean()) ** 2).sum() / (2 * prior ** 2)
        if m.gamma is not None:
            gm = m.gamma[pl]; reg = reg + ((gm - gm.mean()) ** 2).sum() / (2 * prior ** 2)
        if m.dirb is not None: reg = reg + (m.dirb[pl] ** 2).sum() / (2 * DIR_PRIOR ** 2)
        loss = nll(m, T, idx).sum() + reg
        loss.backward()
        return loss
    opt.step(closure)

def fit_players(m, T, idx, players, prior=1.0, iters=100):
    """theta (gamma) of the given players on idx, other parameters fixed (prior centred on the training mean)"""
    params = [m.theta] + ([m.gamma] if m.gamma is not None else []) + ([m.dirb] if m.dirb is not None else [])
    saved = {n: p.detach().clone() for n, p in m.named_parameters()}
    for p in m.parameters(): p.requires_grad_(False)
    for p in params: p.requires_grad_(True)
    mu_t = m.theta.detach()[m._train_players].mean()
    mu_g = m.gamma.detach()[m._train_players].mean() if m.gamma is not None else None
    with torch.no_grad():
        m.theta[players] = mu_t
        if m.gamma is not None: m.gamma[players] = mu_g
        if m.dirb is not None: m.dirb[players] = 0.0
    opt = torch.optim.LBFGS(params, lr=1, max_iter=iters, line_search_fn='strong_wolfe')
    pl = torch.tensor(players)
    def closure():
        opt.zero_grad()
        reg = ((m.theta[pl] - mu_t) ** 2).sum() / (2 * prior ** 2)
        if m.gamma is not None: reg = reg + ((m.gamma[pl] - mu_g) ** 2).sum() / (2 * prior ** 2)
        if m.dirb is not None: reg = reg + (m.dirb[pl] ** 2).sum() / (2 * DIR_PRIOR ** 2)
        loss = nll(m, T, idx).sum() + reg
        loss.backward()
        return loss
    opt.step(closure)
    for p in m.parameters(): p.requires_grad_(True)

def run_cv(D, model, folds=5, seed=0, verbose=True):
    B = build(D, model)
    T = tensors(B)
    n = len(B['played'])
    nplayers = int(B['player'].max()) + 1
    rng = np.random.RandomState(seed)
    perm = rng.permutation(nplayers)
    fold_of = np.zeros(nplayers, dtype=int)
    for k, p in enumerate(perm): fold_of[p] = k % folds
    # first / second half of each player's decisions (data order)
    half = np.zeros(n, dtype=bool)
    for p in range(nplayers):
        ix = np.where(B['player'] == p)[0]
        half[ix[len(ix) // 2:]] = True
    out = np.full(n, np.nan)
    kv = B['V'].shape[2]; ks = 0 if B['S'] is None else B['S'].shape[2]; kh = 0 if B['H'] is None else B['H'].shape[2]
    for k in range(folds):
        test_p = np.where(fold_of == k)[0]; train_p = np.where(fold_of != k)[0]
        tr = np.where(np.isin(B['player'], train_p))[0]
        m = Model(kv, ks, kh, nplayers, skill_kind(model))
        if 'dir' in model.split('_'): m.with_dirs(nplayers)
        m._train_players = torch.tensor(train_p)
        fit_global(m, T, torch.tensor(tr), train_p)
        cal = np.where(np.isin(B['player'], test_p) & ~half)[0]
        te = np.where(np.isin(B['player'], test_p) & half)[0]
        fit_players(m, T, torch.tensor(cal), torch.tensor(test_p))
        with torch.no_grad():
            out[te] = nll(m, T, torch.tensor(te)).numpy()
    ok = ~np.isnan(out)
    res = dict(model=model, nll=float(out[ok].mean()), n=int(ok.sum()))
    for g in range(4):
        s = ok & (B['stage'] == g); res[f'nll_stage{g}'] = float(out[s].mean())
    for t in range(4):
        s = ok & (B['tier'] == t); res[f'nll_tier{t}'] = float(out[s].mean())
    if verbose:
        print(f"{model:14s} nll/decision {res['nll']:.4f}  by stage " +
              ' '.join(f"{res[f'nll_stage{g}']:.4f}" for g in range(4)) + "  by tier " +
              ' '.join(f"{res[f'nll_tier{t}']:.4f}" for t in range(4)), flush=True)
    return res, out

def fit_all(D, model):
    """the final model on all players (for the C++ policy and the statistics)"""
    B = build(D, model)
    T = tensors(B)
    nplayers = int(B['player'].max()) + 1
    kv = B['V'].shape[2]; ks = 0 if B['S'] is None else B['S'].shape[2]; kh = 0 if B['H'] is None else B['H'].shape[2]
    m = Model(kv, ks, kh, nplayers, skill_kind(model))
    if 'dir' in model.split('_'): m.with_dirs(nplayers)
    m._train_players = torch.arange(nplayers)
    fit_global(m, T, torch.arange(len(B['played'])), np.arange(nplayers))
    return m, B, T

if __name__ == '__main__':
    args = sys.argv[1:]
    data = 'results/hm/data.npz'
    save = None
    models = []
    i = 0
    while i < len(args):
        if args[i] == '--data': data = args[i + 1]; i += 2
        elif args[i] == '--save': save = args[i + 1]; i += 2
        else: models.append(args[i]); i += 1
    D = dict(np.load(data))
    try:
        R = np.load(data.replace('data.npz', 'recent.npz'))
        D['_recent'] = (R['cnt'], R['hl'])
    except OSError:
        pass
    for mname in models or ['soft', 'hinge', 'full']:
        t0 = time.time()
        res, _ = run_cv(D, mname)
        print(f"   ({time.time() - t0:.0f} s)", flush=True)
        with open('results/hm/cv.jsonl', 'a') as f: f.write(json.dumps(res) + '\n')
