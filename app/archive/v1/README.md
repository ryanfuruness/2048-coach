# 2048 Coach (app v1, local)

A web app for the 2048 analysis engine: play with a coach that warns you before big mistakes, review every game move
by move, analyze any position. No sign-up, no payment; games stay in the browser.

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
| `npm test` | unit tests: rules, game records, tile animation, formatting (vitest); server validation, rate limiter, cache, engine pool with a fake engine (node:test) |
| `npm run test:engine` | the above plus the engine tests: client rules vs `build/analyze` on 3,000 boards, and the API end to end. Stop a running server first (one engine process at a time) |
| `npm run typecheck` | TypeScript, web and server |
| `npm run qa` | the Playwright user journeys in headless Chrome; screenshots in `qa/screens/` |
| `npm run lighthouse` | Lighthouse (mobile and desktop) on Play, Analyze, How; reports in `qa/lighthouse/` |

Debug links (handy for testing): `/?seed=42` starts a game with a fixed random seed; `/?board=1241356247932180&seed=1`
starts from a given board (16 hex digits or 16 tile values; this one is a near-dead board where Right is a costly move
and, with this seed, ends the game); `/analyze?board=...` opens a position in the editor.

## What is where

```
app/
  shared/rules.ts        2048 rules exactly as the engine (moves, merges, scoring, spawns, board encodings), used by
                         the web app and the server; cross-checked against build/analyze
  server/src/            the API server (Node, TypeScript run directly by Node, no dependencies)
    index.ts             HTTP: routes, CORS, security headers, gzip, errors, graceful shutdown
    engine.ts            pool of resident `build/analyze --stdin` processes, queue, timeouts, restarts with backoff
    review.ts            game reviews in short-lived `--review` processes (light networks when the game allows)
    validate.ts          request validation -> engine request lines
    ratelimit.ts, lru.ts per-IP token buckets, analysis cache
    static.ts            the web build, with immutable caching for hashed assets and precompressed files
  web/                   Vite + Preact + TypeScript
    src/screens/         Play (landing), Review, Analyze, History, How
    src/components/      Board (animated), EvalBar, EvalGraph, MoveRows, WarnSheet, ...
    src/lib/             API client and analysis cache, game records and history (localStorage), skill, input
  engine-patch/          the two flag-guarded engine options (README.md, diff, originals)
  qa/                    journeys, Lighthouse runner, screenshots, REPORT.md
```

## API

`POST /api/analyze`: `{board, skill?, hist?, depth?, risk?, line?, played?}` -> the engine's analysis (fields:
`docs/api.md`). `board`: 16 tile values, a 4x4 array, or a board string. `skill`: the player's skill on the human move
model's scale (-3 to 3). `hist`: the player's recent moves (`"LDDR..."`, the last 20 count). `depth` 0-5, `risk` 0-3,
`line` 0-50.

`POST /api/review`: `{boards: [code...], moves: "URDL..."}` -> `{summary, plies[], engine}`. `boards` are 16-character
board codes (one base-36 rank per cell; equal to the engine's hex for tiles up to 32768) or 16 tile values;
`boards[i+1]` must follow from `boards[i]` by `moves[i]` and one new tile. `summary` is the engine's review summary;
`plies[i]` is the analysis of move `i+1` (played, best, odds, every move's loss, real loss, your cost, warning, reasons).

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
| `RATE_ANALYZE_PER_SEC`, `RATE_ANALYZE_BURST` | 20, 60 | per IP |
| `RATE_REVIEW_PER_MIN`, `RATE_REVIEW_BURST` | 12, 6 | per IP |
| `TRUST_PROXY` | 0 | 1: take the client IP from `X-Forwarded-For` (behind a proxy only) |
| `CORS_ORIGINS` | localhost/127.0.0.1:5173 | origins allowed to call the API from another origin |
| `STATIC_DIR` | web/dist | the web build |
| `LOG_REQUESTS` | 1 (0 under `npm start`) | one JSON log line per API request |

Memory on this machine: one resident engine (775 MB) plus, during a review, one short-lived review process (~150 MB
for most games, 775 MB for games reaching 16384 or a tile sum of 20480).
