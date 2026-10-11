#!/usr/bin/env python3
"""Builds the self-contained replay page from game records and a page description.

usage: build_viewer.py page.json out.html record.txt [record.txt ...] [--top N]

Record lines (written by `play --record`): "<id> <score> <maxtile> <init16> <moves>"
where <moves> is a sequence of 3-character steps: direction (URDL), spawn cell
(hex), spawned tile ('2' or '4').
"""
import json
import sys
from pathlib import Path


def main():
    args = sys.argv[1:]
    top = 6
    if "--top" in args:
        i = args.index("--top")
        top = int(args[i + 1])
        del args[i : i + 2]
    page_json, out, *records = args
    page = json.loads(Path(page_json).read_text())
    games = []
    for rec in records:
        for line in Path(rec).read_text().splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            gid, score, maxtile, init, moves = parts[:5]
            games.append({"id": int(gid), "score": int(score), "maxtile": int(maxtile), "init": init, "moves": moves,
                          "src": Path(rec).stem})
    games.sort(key=lambda g: -g["score"])
    chosen = games[:top]
    labels = page.get("game_labels", {})
    data = dict(page)
    data["games"] = [
        {"label": labels.get(str(k), f"Game {k + 1}"), "init": g["init"], "moves": g["moves"]}
        for k, g in enumerate(chosen)
    ]
    template = (Path(__file__).resolve().parent.parent / "viewer" / "template.html").read_text()
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    Path(out).write_text(template.replace("__DATA__", blob))
    print(f"wrote {out}: {len(chosen)} games, {Path(out).stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
