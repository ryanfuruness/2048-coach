# Design decisions (app v1) and open questions

## Product

- **The game is the landing page.** A new visitor sees a playable board within ~0.4 s (desktop) / ~1.7 s (slow-4G
  mobile, Lighthouse LCP), with the coach already on ("Warn me") and one line of welcome text. Nothing to sign up for;
  games, reviews and the estimated level live in `localStorage`.
- **Coach modes**: Off / Warn me (default) / Best move. Off also hides the eval bar (a player who switches the coach off
  wants a plain game); the game is still saved and reviewable.
- **Warnings** (the research's most efficient advice): when the move the player makes has `warn: true` *in an analysis
  that is already there*, a sheet stops the move: what it costs ("gives away about 26% of your chances to reach 1024",
  from `your_cost`; "will very likely end your game" when the real loss is 80%+), the main cause (only a checked reason,
  one with a `share`), and the engine's move. One tap/key takes the suggestion, one plays the move anyway, Esc goes
  back. If the analysis is not ready, the move simply happens (the coach never blocks). On desktop the sheet sits beside
  the board so the board and both arrows stay visible.
- **Prefetch**: the analysis request for a position leaves as soon as the move is computed (before the render); the
  client de-duplicates requests and caches answers, the server caches by request line. Typical round trip ~5-10 ms.
- **Hints** only as an offer ("Tricky position · want a hint?") when the engine says `hint: true` (it only does so up
  to a 512 tile) and only in "Warn me" mode; tapping shows the best move on the board with its main reason.
- **Default skill -0.5** until the player's own is known. Measured on the 15 novice stretches of the curated data:
  -0.8 would offer ~7 hints per 100 opening moves, -0.5 ~0.8 (the engine's skill bands split at -0.5, so the novice
  "your cost" map, ~3x larger, applies only below it). -0.5 avoids nagging a stronger newcomer while still offering the
  clearest hints; the first review replaces it. The skill is then the moves-weighted mean of the last 6 reviewed games
  (`review.skill`, 50+ moves needed); a first game gets a mid-game reading at move 120 (a background review of the moves
  so far). Every analysis request carries the skill and the player's last 20 moves (the human move model's window).
- **Eval bar**: the engine's odds (`odds`, "with best play from here") of the next milestone tile, which is the smallest
  tile the odds cover: 2048 until it is reached, then 4096, ... Shown as a linear meter with the exact percentage.
  Its color is the engine's own verdict of the position against a typical one at this stage (the summary's
  "about as good as / a bit worse than / in trouble compared with a typical position"), so green/amber/red mean
  something even when the chance itself is 99.9%. While the next analysis is on its way the bar shows the previous
  analysis' odds after the move just played. Once the player's skill is known, a marker shows the personal odds of the
  same tile ("at your level"), when the model gives them. Block positions say "not judged"; positions without odds say so.
- **Review**: the engine's own review (`--review`), started in the background at game over so it is usually ready when
  "Review this game" is tapped. Summary cards (best-or-good share, accuracy, decisive moment, level), a one-line count of
  inaccuracies/mistakes/blunders and coach warnings, the eval graph, a step-through that opens at the decisive moment,
  and the key moments (the engine lists only those of 3%+). Reasons read "Mainly because ..." (share 0.5+) / "Partly
  because ..." (0.1-0.5) / plain for unchecked hints, as docs/guide.md suggests for a language layer.
- **Eval graph**: two panels on one move axis instead of a dual-axis chart: the chance of the next milestone before
  each move, and each move's real loss as bars colored inaccuracy/mistake/blunder (status colors, always with a legend
  and labels). The chance uses a scale stretched near 100% (log of the chance to fail, ticks 99.9/99/90/50%): the
  engine's odds sit at 99%+ for most of a game, and the drops that matter would be invisible on a linear axis. A
  finished game ends at 0% on its final position. Hover/tap shows a tooltip, click jumps to the move, and a "Show as
  table" twin lists every move that cost 1%+.
- **Analyze**: palette editor (pick a tile, tap cells; tap again clears), six presets from the engine's samples
  (ordinary 512, blocked chain, near-dead, unusual formation with the odds caveat, expert block = not judged, opening),
  paste/copy of board strings (16 values or 16 hex digits), live analysis (debounced), "Deeper analysis" (depth 5),
  the plan's chain outlined on the board, "Play from here". The URL keeps the board (`/analyze?board=...`).
  "Played by X% of players at your level" is hidden from 16384 on (the human model is weakest there).
- **History**: up to 200 games, ~2 characters per move (start board + moves + new tiles), replayed into boards on
  demand; review summaries stored with the game; full reviews recomputed by the server when reopened (deterministic,
  ~0.5-2 s), so storage stays small. Delete one / clear all (also resets the level).

## Engineering

- **Front-end**: Vite 8 + Preact 10 + TypeScript, no UI library, one stylesheet with light/dark tokens. First load
  ~93 KB transferred in total (~19 KB JS + 8 KB CSS gzipped, a self-hosted 48 KB variable font, no external requests);
  other screens are lazy chunks preloaded after the game is on screen. Tiles animate with CSS `translate` transitions
  (merging tiles slide in as ghosts under a popping merged tile, new tiles appear), `prefers-reduced-motion` respected.
  The tile palette is contrast-checked (all numbers at least 3:1 as large text, most 4.5:1+).
- **Rules** (`shared/rules.ts`) are shared by client and server and match the engine: unit tests plus a cross-check of
  legal moves, afterstates and points against `build/analyze` on 3,000 boards (random and played), all identical.
- **Server**: Node (TypeScript run natively by Node 24, zero runtime dependencies) rather than Python, so the whole app
  is one toolchain. Resident `--stdin` workers (default 1) with a bounded queue, per-request timeout (kill + restart with
  exponential backoff), warm-up check at start, health endpoint; JSON validation with plain error messages, body size
  limits, per-IP token buckets, LRU cache, gzip, security headers (CSP, nosniff, frame-ancestors none), CORS allow-list
  for development, graceful shutdown. Static files with immutable caching for hashed assets and precompressed br/gzip.
- **Reviews in short-lived processes** (`--review FILE --json`) instead of the resident workers: the review summary
  (skill fit, hints, hard moments, decisive moment) only exists in the engine's review mode, so it is used as is; a
  review does not hold up live analyses; at most `REVIEW_CONCURRENCY` (1) run at once. Games that stay below 16384 and
  a tile sum of 20480 (almost all) use the light stage-0 networks: identical answers (checked on a review), ~150 MB and
  0.2 s start-up; others use the full packed networks. A 300-move game takes ~0.5 s, 3,000 moves ~1.8 s (130 KB gzipped).
- **Engine changes** (minimal, flag-guarded, documented in `engine-patch/README.md`):
  `--stdin-player` (per-request `skill=` and `hist=`; without it one 775 MB process per skill would be needed) and
  `--review-moves` (reviews take the known moves: 0.7% of consecutive board pairs can be explained by two different
  moves, and the inference then picks the wrong one about half the time). Without the flags the engine's output is
  byte-identical to before; `--selftest` passes.
- **Memory on this laptop**: one resident engine (775 MB packed int16) plus, briefly, one review process. The exact
  tables (`--preset best`) are not used by default.

## Deliberately left out of v1

Undo (it would blur what a review means), sharing links to games, accounts/sync, server-side storage, analytics,
service-worker offline mode, translations, sound. Screenshot import, LLM chat, WASM and payments were non-goals.

## Open questions for you

1. **Name.** "2048 Coach" is a working title (the UI, `<title>` and manifest use it; one place each). Is "2048" in the
   name acceptable for you legally and brand-wise? (The original game is MIT-licensed; the name is used by many clones.)
2. **Domain** and whether the app should live at the root or under a path.
3. **Which odds lead the eval bar.** v1 shows the engine's odds ("with best play"), as specified; they sit at 99%+ until
   real danger. Personal odds (`--skill`) are much lower and more personal, but they depend on the estimated level and
   are rougher. Keep, swap, or show both once the level is known (v1 adds a marker)?
4. **Default level -0.5** (see above): fewer hints for unknown players. Prefer more help for beginners (-0.8)?
5. **Exact tables in production?** Without them (best-notables) 16384+ endgames are a little weaker and expert block
   positions are "not judged". With them: ~3.7 GB RAM per engine process plus 141 GB of tables on SSD.
6. **Reviews server-side?** v1 stores nothing on the server. Accounts or cross-device history would need storage and a
   privacy policy.

## What deployment will need

- A Linux host with an x86-64 CPU with BMI2 for the native build (`-march=native`: build on the target, or use the
  portable build, ~2.3x slower), ~1 GB RAM per resident engine worker plus ~0.2-0.8 GB per concurrent review, and the
  weights (`weights/serve/v6c_i16.wp` 753 MB, `v6c_s0only_i16.wp` 120 MB, `weights/calib/`, `weights/best.cfg` and
  the files it names). One worker answers ~260 analyses/s (measured: 3,000 distinct positions with skill and history from 8 concurrent clients, p50 21 ms; one player alone: p50 5 ms, p95 16 ms); a player sends about one request per move.
- TLS and a reverse proxy (Caddy/nginx) in front of `node server/src/index.ts` with `HOST=127.0.0.1`, `TRUST_PROXY=1`,
  CORS left empty (same origin); a process supervisor (systemd) with restart on failure; log collection for the JSON
  logs; `/api/health` for monitoring.
- With more than one server instance: shared rate limiting (the buckets are in memory) and sticky nothing else (the
  API is stateless).
- A short privacy note: boards are sent to the server for analysis; games stay in the browser; no cookies or tracking.
- Decisions 1-2 above (name, domain) and 5 (tables) before sizing the machine.
