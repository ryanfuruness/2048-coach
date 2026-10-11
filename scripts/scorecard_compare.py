#!/usr/bin/env python3
"""Side-by-side table of the scorecard's key numbers for several configurations (scripts/scorecard.sh outputs in
results/scorecard/NAME/: metrics.json, invariants.json, personal.json, games.json, tiers.json, config.txt).
usage: scorecard_compare.py NAME NAME ... [> results/scorecard/compare.txt]"""
import json, math, sys


def load(name, f):
    try:
        return json.load(open(f'results/scorecard/{name}/{f}'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def g(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict) or k not in d: return default
        d = d[k]
    return d


def fmt(x, spec='.3f', pct=False):
    if x is None or (isinstance(x, float) and math.isnan(x)): return 'n/a'
    return format(100 * x if pct else x, spec) + ('%' if pct else '')


def main():
    names = sys.argv[1:]
    D = {n: dict(m=load(n, 'metrics.json'), inv=load(n, 'invariants.json'), pers=load(n, 'personal.json'),
                 games=load(n, 'games.json'), tiers=load(n, 'tiers.json'),
                 warn=any(l.startswith('warn ') for l in open(f'results/scorecard/{n}/model.txt'))) for n in names}
    rows = []

    def row(label, f, note=''):
        rows.append((label, [f(D[n]) for n in names], note))

    def sec(title):
        rows.append((None, title, ''))

    sec('ROBUSTNESS: engine move significantly worse than the rollout best (z=2), 1,800 unselected real positions')
    for st in ('early', 'late', 'top', 'all'):
        row(f'  {st}', lambda x, st=st: f"{g(x['m'], 'robustness', st, 'errors')}/{g(x['m'], 'robustness', st, 'n')}"
            if g(x['m'], 'robustness', st) else 'n/a')
    sec('LOSS MAPS: RMSE (x100) of the estimated real loss of every non-reference move vs rollouts (lower = better)')
    for st in ('early', 'late', 'top', 'table', 'all'):
        row(f'  {st}', lambda x, st=st: fmt(g(x['m'], 'maps', st, 'rmse'), '.2f'))
    row('  top: mean estimated vs measured (x100)', lambda x: f"{fmt(g(x['m'], 'maps', 'top', 'est'), '.1f')} vs "
        f"{fmt(g(x['m'], 'maps', 'top', 'measured'), '.1f')}")
    row('  positions not judged (block formation)', lambda x: str(g(x['m'], 'maps', 'not_judged_positions', default='n/a')))
    sec("EXPERTS' OWN MOVES at 16384+ (jx + jold, H=1000; review estimate vs rollouts with the engine continuing)")
    for grp in ('snake experts', 'block player'):
        row(f'  {grp}: RMSE (x100)', lambda x, grp=grp: fmt(g(x['m'], 'played', grp, 'rmse'), '.1f'))
        row(f'  {grp}: mean estimated vs measured', lambda x, grp=grp: f"{fmt(g(x['m'], 'played', grp, 'est'), '.1f')} vs "
            f"{fmt(g(x['m'], 'played', grp, 'measured'), '.1f')}")
        row(f'  {grp}: blunder calls on refuted (false alarms)', lambda x, grp=grp:
            f"{g(x['m'], 'played', grp, 'refuted_blunder')}/{g(x['m'], 'played', grp, 'refuted')}" if g(x['m'], 'played', grp) else 'n/a')
        row(f'  {grp}: blunder calls on confirmed (detections)', lambda x, grp=grp:
            f"{g(x['m'], 'played', grp, 'confirmed_blunder')}/{g(x['m'], 'played', grp, 'confirmed')}" if g(x['m'], 'played', grp) else 'n/a')
        row(f'  {grp}: abstained', lambda x, grp=grp: str(g(x['m'], 'played', grp, 'abstained', default='n/a')))
    sec('RAW CLAIMS > 10% on the 210 expert decisions (H=1000 truth): false on refuted / kept on confirmed / abstained')
    for grp in ('block player', 'snake experts'):
        row(f'  {grp}', lambda x, grp=grp: (lambda c: f"{c['false']}/{c['refuted']}  {c['kept']}/{c['confirmed']}  {c['abstained']}"
                                            if c else 'n/a')(g(x['m'], 'claims', f'H=1000 {grp}')))
    row('  unselected late positions: Spearman claim ~ real', lambda x: fmt(g(x['m'], 'late_claims', 'spearman')))
    row('  unselected late positions: claims > 10% not real', lambda x: (lambda c: f"{c['big_not_real']}/{c['big']}" if c else 'n/a')(
        g(x['m'], 'late_claims')))
    sec('ODDS vs engine playouts on real positions (MAE / log-loss; truth3 = 200 positions no model saw)')
    for k in ('truth3 (fresh)', 'truth3 tight', 'r14', 'r15+r15b', 'truth4', 't30'):
        row(f'  {k}', lambda x, k=k: f"{fmt(g(x['m'], 'odds', k, 'mae'))} / {fmt(g(x['m'], 'odds', k, 'logloss'))}"
            if g(x['m'], 'odds', k) else 'n/a')
    row('  near-dead board P(16384) (measured 0.850)', lambda x: str(g(x['m'], 'neardead')))
    row('  fresh board P(16384) / P(32768)', lambda x: f"{g(x['m'], 'fresh', '16384')} / {g(x['m'], 'fresh', '32768')}",
        'benchmarks: best_v5bb 0.954 / 0.598, best_v6b 0.954 / 0.629')
    sec("PERSONAL ODDS vs real players' outcomes (curated games, outcome observed; videos are success-selected)")
    for mult in ('2x', '4x'):
        row(f'  {mult}: log-loss / Brier / AUC', lambda x, mult=mult: (lambda p: f"{fmt(p['logloss'])} / {fmt(p['brier'])} / "
                                                                    f"{fmt(p['auc'])}" if p else 'n/a')(g(x['pers'], mult, 'personal')))
        row(f'  {mult}: mean predicted vs observed', lambda x, mult=mult: (lambda p: f"{fmt(p['predicted'])} vs {fmt(p['observed'])}"
                                                                         if p else 'n/a')(g(x['pers'], mult, 'personal')))
    sec('GAME-LEVEL CONSISTENCY (scorecard_games.py): experts\' 16384 stretches (all reached 32768)')
    row('  chances kept, median over the stretches', lambda x: fmt(g(x['games'], 'expert 16384', 'kept_succ_p50')))
    row('  R (should be ~1-3)', lambda x: fmt(g(x['games'], 'expert 16384', 'R'), '.1f'))
    row('  -ln(kept) per 100 moves', lambda x: fmt(g(x['games'], 'expert 16384', 'nll_per_100_moves')))
    sec('TIER BENCHMARKS (medians over players): best/good, inacc / mistakes / blunders / warnings per 100 moves')
    for t in ('novice', 'intermediate', 'strong', 'expert'):
        row(f'  {t}', lambda x, t=t: (lambda r: f"{fmt(r.get('good'), '.1f', True)}  {fmt(r.get('inacc'), '.2f')} / "
                                       f"{fmt(r.get('mist'), '.2f')} / {fmt(r.get('blun'), '.2f')} / "
                                       f"{fmt(r.get('warn'), '.2f') if x['warn'] else 'n/a'}"
                                       if r else 'n/a')(g(x['tiers'], t)))
    sec('INVARIANTS (violations, by-design issues excluded) and LATENCY (p50 / p99 / max ms, first answer excluded)')
    for k, lab in (('notables_real', 'no tables, 450 real positions'), ('notables_fuzz', 'no tables, 4,553 fuzz boards'),
                   ('tables_real', 'tables, 450 real positions'), ('tables_fuzz', 'tables, 4,553 fuzz boards')):
        def cell(x, k=k):
            v = next((vv for kk, vv in x['inv'].items() if kk.endswith('/' + k)), None)
            if not v: return 'n/a'
            return f"{v['violations']} | {v['p50']:.1f} / {v['p99']:.1f} / {v['max']:.0f}"
        row(f'  {lab}', cell)
    w0 = max(len(r[0]) for r in rows if r[0]) + 2
    w = max(14, max(len(str(v)) for label, vals, _ in rows if label for v in vals) + 3)
    print(' ' * w0 + ''.join(f'{n:>{w}s}' for n in names))
    for label, vals, note in rows:
        if label is None:
            print(f'\n{vals}')
            continue
        print(f'{label:{w0}s}' + ''.join(f'{str(v):>{w}s}' for v in vals) + (f'   ({note})' if note else ''))


if __name__ == '__main__':
    main()
