# 2048 Coach (app v2 "workbench", local)

A web app for the 2048 analysis engine, built as one workbench: play on the board with live analysis of every position,
take back any move (also after the game ends), scrub through the line on a timeline, let the coach play on from any
position at a chosen speed, set up any position, and review the game on the same screen. No sign-up, no payment; the
game stays in the browser.

Since v3 (the second playtest) everything is built around the coach's **grade** of each move:

- **Best:** the coach's move, or one just as good.
- **Good:** fine, but the coach would play something else.
- **Questionable:** the coach would never play it.
- **Blunder:** an obvious, named mistake, such as your biggest tile out of its corner.

The early game (largest tile up to 256) is free.

Four toggles replace the modes:
- **Coach:** everything on or off.
- **Best move:** the arrow and the move list with how often the coach would play each move.
- **Warn me:** stops you before a blunder.
- **Highlights:** marks the tiles where a move went wrong.

The engine's odds sit behind a link in the move list. See `DECISIONS.md` (v3) and `../results/grades/REPORT.md`.

## Run it

```bash
cd app
npm start            # first run: installs dependencies and builds the web app
```

Open **http://127.0.0.1:8048/**. `Ctrl+C` (or `npm run stop` from another terminal) stops the server and its engine
process. Starting it twice just prints the address of the running one.

Requirements: the engine built in the project root (`make -j8`, with the two app flags of `engine-patch/`), Node 22.18+
(24 is installed), the weights in `weights/`. `npm start` checks the engine, rebuilds the web app when its sources
changed, and starts one server that serves both the app and the API. The server binds to 127.0.0.1 only.

Development with hot reload: `npm run dev` (API server + Vite on http://127.0.0.1:5173, which proxies `/api`).

| command | what it does |
|---|---|
| `npm start` | build if needed, then serve app + API on :8048 |
| `npm run stop` | stop the server started by `npm start` (and its engine) |
| `npm run dev` | API server + Vite dev server (:5173) |
| `npm run build` | production build into `web/dist/` (+ brotli/gzip copies) |
| `npm test` | unit tests: rules, the line model, the workbench controller against a fake server, tile animation, formatting, own-move review (vitest); server validation, rate limiter, cache, engine pool with a fake engine (node:test) |
| `npm run test:engine` | the above plus the engine tests: client rules vs `build/analyze` on 3,000 boards, and the API end to end. Stop a running server first (one engine process at a time) |
| `npm run typecheck` | TypeScript, web and server |
| `npm run qa` | the Playwright user journeys in headless Chrome; screenshots in `qa/screens/` |
| `npm run lighthouse` | Lighthouse (mobile and desktop) on the board, a position link, How; reports in `qa/lighthouse/` |

Links: `/?board=CODE` opens a position as a new line (16 hex digits, the app's 16-character board code, or 16 tile
values; "Copy a link to this position" in the menu makes one; the line it replaces can be restored). Debug: `/?seed=42`
starts a game with a fixed random seed; `/?board=1241356247932180&seed=1` is a near-dead board where Right is a costly
move and, with this seed, ends the game. v1 paths (`/analyze`, `/history`, `/review/...`) open the workbench.

## Using it

| key | action |
|---|---|
| arrows / WASD, swipe | move |
| Space / Enter, or a click on the arrow at the board's edge or on a move in the list | play the coach's move (or that move) |
| Z / Backspace (Shift+Z: 10) | back one move |
| X (Shift+X: 10) | forward one move |
| Home / End | start / end of the game |
| P | the coach plays on / stops; the buttons play 1, 10 or 100 moves or to the next tile |
| C / H | coach on/off / best move on/off |
| R | review your moves (counts and the questionable moves and blunders to revisit) |
| E | set up a position |
| ? | the shortcuts |

From an earlier position, the move the game already has follows it (same new tile); any other move starts a new line
from there, and a replaced stretch of 8+ moves can be brought back from the toast for 9 s.

## What is where

```
app/
  shared/rules.ts        2048 rules exactly as the engine (moves, merges, scoring, spawns, board encodings), used by
                         the web app and the server; cross-checked against build/analyze
  server/src/            the API server (Node, TypeScript run directly by Node, no dependencies)
    index.ts             HTTP: routes (analyze, review, autoplay batches), CORS, security headers, gzip, errors,
                         graceful shutdown
    engine.ts            pool of resident `build/analyze --stdin` processes, queue, timeouts, restarts with backoff
    review.ts            game reviews in short-lived `--review` processes (light networks when the game allows)
    validate.ts          request validation -> engine request lines
    ratelimit.ts, lru.ts per-IP token buckets, analysis cache
    static.ts            the web build, with immutable caching for hashed assets and precompressed files
  web/                   Vite + Preact + TypeScript
    src/screens/         Dojo (the board, grade line, transport, coach plays, toggles, move list), How
    src/components/      Board (animated, clickable arrows, highlighted cells), MoveList, ReviewSheet, WarnSheet,
                         Editor, Menu, ...
    src/lib/             line.ts (the game: moves, new tiles, who moved, cursor, compact facts = the coach's move and
                         the played move's grade), workbench.ts (controller: analyses, autoplay, review), grades.ts,
                         API client and analysis cache, input
  engine-patch/          the two flag-guarded engine options (README.md, diff, originals)
  qa/                    journeys, Lighthouse runner, screenshots, REPORT.md
```

## API

`POST /api/analyze`: `{board, hist?, depth?, risk?, line?, played?}` -> the engine's analysis (fields: `docs/api.md`;
each move's `grade`, `why`, `pick`, `hint_cells`, `fault_cells`, and `coach_move`). `board`: 16 tile values, a 4x4
array, or a board string. `hist`: the player's recent moves (`"LDDR..."`, the last 20 count; the coach's opening
corner strategy uses them). `depth` 0-5, `risk` 0-3, `line` 0-50. (`skill` is still accepted for the engine's research
fields; the app sends none.)

`POST /api/review`: `{boards: [code...], moves: "URDL..."}` -> `{summary, plies[], engine}` (each ply carries every
move's `grade`, the played move's `why` and `fault_cells`, and `coach_move`). `boards` are 16-character
board codes (one base-36 rank per cell; equal to the engine's hex for tiles up to 32768) or 16 tile values;
`boards[i+1]` must follow from `boards[i]` by `moves[i]` and one new tile. `summary` is the engine's review summary;
`plies[i]` is the analysis of move `i+1` (played, best, odds, every move's loss, real loss, your cost, warning, reasons).

`POST /api/autoplay`: `{board, hist?, n, seed, stop_rank?}` -> `{moves, spawns, facts[], over}`: the coach's next `n`
moves (at most 64), each the coach's move of the position's analysis (`coach_move`, else the reference move), with the
new tiles drawn from `seed`; `facts[i]` = `{t, p, b}` (milestone tile, the engine's chance of it, the move). Full-speed
autoplay uses it (one request per move would spend more time on the request than on the engine); every analysis is a
separate engine job, so other requests are served in between, and lands in the analysis cache.

`GET /api/health`: engine workers, queue, reviews, cache, counters.

Errors are JSON `{error}` with 400 (bad input), 405, 413 (too large), 415, 429 (rate limit, with `Retry-After`), 503
(engine busy or restarting), 504 (engine timeout).

## Configuration (environment variables)

| variable | default | meaning |
|---|---|---|
| `PORT`, `HOST` | 8048, 127.0.0.1 | where the server listens |
| `ENGINE_ROOT` | the project root | directory with `build/` and `weights/` |
| `ENGINE_BIN` | build/analyze | the engine binary |
| `ENGINE_PRESET` | best-notables | `best` adds the exact tables (~3.7 GB per process) |
| `ENGINE_PACKED` | weights/serve/v6c_i16.wp | packed networks for the workers (identical answers, 775 MB); empty = the preset's |
| `ENGINE_PACKED_LIGHT` | weights/serve/v6c_s0only_i16.wp | light networks for reviews of games without a 16384 and with a tile sum below 20480 (identical there, ~150 MB); empty = never |
| `ENGINE_WORKERS` | 1 | resident engine processes |
| `ENGINE_MAX_QUEUE`, `ENGINE_QUEUE_WAIT_MS` | 64, 15000 | queue length and wait before a 503 |
| `ANALYZE_TIMEOUT_MS` | 10000 | per analysis; a hung engine is killed and restarted |
| `MAX_DEPTH` | 5 | deepest analysis a request may ask for (the engine caps at 6) |
| `ANALYZE_CACHE_SIZE` | 5000 | cached analyses (requests are deterministic) |
| `REVIEW_CONCURRENCY`, `REVIEW_MAX_WAITING` | 1, 8 | review processes at once, and waiting reviews before a 503 |
| `REVIEW_MAX_MOVES` | 20000 | longest reviewable game |
| `RATE_ANALYZE_PER_SEC`, `RATE_ANALYZE_BURST` | 200, 400 | per IP (autoplay below full speed asks one analysis per move; v1 had 20, 60) |
| `RATE_AUTOPLAY_PER_SEC`, `RATE_AUTOPLAY_BURST` | 20, 40 | autoplay batches per IP |
| `AUTOPLAY_MAX_MOVES` | 64 | longest batch |
| `RATE_REVIEW_PER_MIN`, `RATE_REVIEW_BURST` | 12, 6 | per IP |
| `TRUST_PROXY` | 0 | 1: take the client IP from `X-Forwarded-For` (behind a proxy only) |
| `CORS_ORIGINS` | localhost/127.0.0.1:5173 | origins allowed to call the API from another origin |
| `STATIC_DIR` | web/dist | the web build |
| `LOG_REQUESTS` | 1 (0 under `npm start`) | one JSON log line per API request |

Memory on this machine: one resident engine (775 MB) plus, during a review, one short-lived review process (~150 MB
for most games, 775 MB for games reaching 16384 or a tile sum of 20480).
