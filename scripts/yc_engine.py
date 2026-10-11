#!/usr/bin/env python3
"""Workstream yc: the current engine's analysis (the app server's /api/analyze, skill -0.5) of each position of a
positions file -> JSON lines {id, engine_move, moves: {U: {real_loss, your_cost, warn, loss_rel}}, odds, personal}.
usage: yc_engine.py POS.tsv OUT.jsonl [URL]"""
import csv, json, sys, urllib.request

pos_file, out_file = sys.argv[1], sys.argv[2]
url = sys.argv[3] if len(sys.argv) > 3 else 'http://127.0.0.1:8048/api/analyze'
D = {'up': 'U', 'right': 'R', 'down': 'D', 'left': 'L'}
with open(out_file, 'w') as f:
    for r in csv.DictReader(open(pos_file), delimiter='\t'):
        tiles = [0 if c == '0' else 1 << int(c, 16) for c in r['board']]
        body = json.dumps({'board': tiles, 'skill': -0.5, 'hist': r.get('hist', '')[-20:]}).encode()
        req = urllib.request.Request(url, body, {'content-type': 'application/json'})
        a = json.load(urllib.request.urlopen(req))
        best = max((m['value'] for m in a['moves']), default=0)
        mv = {}
        for m in a['moves']:
            mv[D[m['move']]] = {'real_loss': m.get('real_loss'), 'your_cost': m.get('your_cost'), 'warn': m.get('warn'),
                                'loss_rel': (best - m['value']) / max(abs(best), 100000.0), 'find_prob': m.get('find_prob')}
        f.write(json.dumps({'id': r['id'], 'engine_move': D.get(a.get('engine_move') or '', None), 'moves': mv,
                            'odds': a.get('odds'), 'personal': a.get('personal_odds')}) + '\n')
