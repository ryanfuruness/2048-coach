#!/usr/bin/env python3
"""Is the plan right? (workstream plan, 2026-10-07)

  plan_study.py sample [N_PER_CELL]          stratified sample of real positions (results/human_ds_v6b/analysis.jsonl)
                                             by plan type x stage, with the real player's continuation in the same
                                             video segment -> results/plan/sample.jsonl
  plan_study.py engine SHARD NSHARDS [BIN]   the engine's continuation from each sampled position (build/analyze
                                             --preset best, "line=200" requests chained up to the plan's horizon)
                                             -> results/plan/engine_SHARD.jsonl   (run on the instance)
  plan_study.py eval [--engine-glob G] [--tag T]
                                             agreement of each plan type's predicted event with the engine's and the
                                             players' continuations, per type x stage (and tier for players)

Plan types and checks: scripts/plan_lib.py."""
import collections, glob, json, math, os, random, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan_lib as pl

STAGES = ('<=512', '1024-2048', '4096-8192', '16384+')


def stage_of(maxtile):
    return '<=512' if maxtile <= 512 else '1024-2048' if maxtile <= 2048 else '4096-8192' if maxtile <= 8192 else '16384+'


def text_type(p):
    if not p:
        return 'none'
    if p.startswith('Get your biggest'):
        return 'no_corner'
    if p.startswith('Keep the'):
        return 'single'
    if p.startswith('Your biggest tiles form a block'):
        return 'block'
    if 'blocks it' in p:
        return 'blocked'
    if 'Merge the' in p:
        return 'merge'
    if 'Build ' in p:
        return 'build'
    if 'Grow the' in p:
        return 'grow'
    return 'full'


def cmd_sample(args):
    per = int(args[0]) if args else 80
    rows = []
    seqs = collections.defaultdict(list)
    with open('results/human_ds_v6b/analysis.jsonl') as f:
        for i, line in enumerate(f):
            a = json.loads(line)
            r = pl.ranks_of_tiles(a['board'])
            key = (a['video'], a.get('segment', 0))
            seqs[key].append((a['ply'], i))
            rows.append({'i': i, 'key': key, 'ply': a['ply'], 'ranks': r, 'tier': a.get('tier'), 'player': a.get('player'),
                         'plan': a.get('plan', ''), 'hex': a['hex'], 'board': a['board'], 'observed': a.get('observed'),
                         'played': a.get('played'), 'engine_move': a.get('engine_move')})
    for k in seqs:
        seqs[k].sort()
    pos_in_seq = {}
    for k, v in seqs.items():
        for j, (ply, i) in enumerate(v):
            pos_in_seq[i] = (k, j)
    cells = collections.defaultdict(list)
    for a in rows:
        t = text_type(a['plan'])
        if t in ('none', 'full'):
            continue
        st = stage_of(max(max(r) for r in a['board']))
        cells[(t, st)].append(a['i'])
    random.seed(2048)
    out = open('results/plan/sample.jsonl', 'w')
    n = 0
    for (t, st), ids in sorted(cells.items()):
        random.shuffle(ids)
        for i in ids[:per]:
            a = rows[i]
            k, j = pos_in_seq[i]
            # the player's continuation: boards at ply offsets 1..600 (gaps filled with the last known board)
            seq, last, p0 = [], None, a['ply']
            for ply, ii in seqs[k][j + 1:]:
                off = ply - p0
                if off > 600:
                    break
                while len(seq) < off - 1:
                    seq.append(last if last is not None else a['ranks'])
                seq.append(rows[ii]['ranks'])
                last = rows[ii]['ranks']
            P = pl.plan_info(a['ranks'])
            rec = {'id': n, 'type': t, 'py_type': P['type'], 'stage': st, 'tier': a['tier'], 'player': a['player'],
                   'plan': a['plan'], 'hex': a['hex'], 'board': a['board'], 'ranks': a['ranks'], 'human': seq,
                   'played': a['played'], 'engine_move': a['engine_move']}
            out.write(json.dumps(rec) + '\n')
            n += 1
    out.close()
    print(f'{n} positions -> results/plan/sample.jsonl')


def cmd_engine(args):
    shard, nsh = int(args[0]), int(args[1])
    binary = args[2] if len(args) > 2 else './build/analyze'
    recs = [json.loads(l) for l in open('results/plan/sample.jsonl')]
    recs = [r for r in recs if r['id'] % nsh == shard]
    extra = os.environ.get('PLAN_ENGINE_FLAGS', '').split()  # e.g. "--weights weights/best_v6b.w"
    proc = subprocess.Popen([binary, '--preset', 'best'] + extra + ['--stdin', '--json'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    out = open(f'results/plan/engine_{shard}.jsonl', 'w')
    for r in recs:
        if max(r['ranks']) > 15:  # a 65536+ tile: the engine's line boards are lowered, skip
            continue
        P = pl.plan_info(r['ranks'])
        H = pl.horizon(P) if P['type'] else 100
        if r['type'] == 'block':
            H = 100
        board = ' '.join(str(v) for row in r['board'] for v in row)
        boards, info, first = [], None, True
        while len(boards) < H:
            proc.stdin.write(f'line={min(200, H - len(boards))} | {board}\n')
            proc.stdin.flush()
            a = json.loads(proc.stdout.readline())
            if first:
                info, first = a.get('plan_info'), False
            line = a.get('line') or []
            if not line:
                break
            boards += [x['board'] for x in line]
            board = line[-1]['board']
            if max(pl.ranks_of_hex(board)) > 15:
                break
        out.write(json.dumps({'id': r['id'], 'plan_info': info, 'boards': boards}) + '\n')
        out.flush()
    out.close()
    proc.stdin.close()
    proc.wait()


def rate(xs):
    v = [x for x in xs if x is not None]
    return (sum(v) / len(v), len(v)) if v else (float('nan'), 0)


def cmd_eval(args):
    eglob, tag = 'results/plan/engine_*.jsonl', ''
    while args:
        a = args.pop(0)
        if a == '--engine-glob':
            eglob = args.pop(0)
        elif a == '--tag':
            tag = args.pop(0)
    recs = {}
    for l in open('results/plan/sample.jsonl'):
        r = json.loads(l)
        recs[r['id']] = r
    eng = {}
    for f in glob.glob(eglob):
        for l in open(f):
            e = json.loads(l)
            eng[e['id']] = e
    agree_py = sum(1 for r in recs.values() if r['type'] == r['py_type'] or r['type'] == 'block')
    print(f'{len(recs)} sampled positions ({agree_py} with the Python plan type = the stored text type), '
          f'{len(eng)} engine continuations {tag}')
    rows = collections.defaultdict(lambda: collections.defaultdict(list))
    for i, r in recs.items():
        t = r['type']
        if t == 'block':
            continue
        P = pl.plan_info(r['ranks'])
        if P['type'] != t:
            continue
        ch = pl.main_check(t)
        if i in eng:
            ev = pl.events(P, r['ranks'], [pl.ranks_of_hex(h) for h in eng[i]['boards']])
            rows[('engine', t, r['stage'])]['main'].append(ev.get(ch))
            rows[('engine', t, r['stage'])]['anchor'].append(ev.get('anchor'))
            if 'chain_grew' in ev:
                rows[('engine', t, r['stage'])]['chain_grew'].append(ev.get('chain_grew'))
        ev = pl.events(P, r['ranks'], r['human'])
        for grp in ('players', r['tier']):
            rows[(grp, t, r['stage'])]['main'].append(ev.get(ch))
            rows[(grp, t, r['stage'])]['anchor'].append(ev.get('anchor'))
            if 'chain_grew' in ev:
                rows[(grp, t, r['stage'])]['chain_grew'].append(ev.get('chain_grew'))
    types = ('merge', 'build', 'grow', 'blocked', 'single', 'no_corner')
    for grp in ('engine', 'players', 'novice', 'intermediate', 'strong', 'expert'):
        print(f'\n== {grp}: share of positions where the plan\'s event happened within its horizon (n)')
        print('   type        check         ' + ''.join(f'{s:>18s}' for s in STAGES) + '               all')
        for t in types:
            for chk in ('main', 'chain_grew', 'anchor'):
                cells = [rows[(grp, t, s)][chk] for s in STAGES]
                if not any(cells):
                    continue
                allv = [x for c in cells for x in c]
                name = pl.main_check(t) if chk == 'main' else chk
                line = f'   {t:11s} {name:13s} '
                for c in cells:
                    p, n = rate(c)
                    line += f'{p:12.2f} ({n:3d})' if n else f'{"-":>18s}'
                p, n = rate(allv)
                line += f'{p:12.2f} ({n:4d})'
                print(line)


if __name__ == '__main__':
    cmd = sys.argv[1]
    {'sample': cmd_sample, 'engine': cmd_engine, 'eval': cmd_eval}[cmd](sys.argv[2:])
