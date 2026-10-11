# Design decisions (app v3, and v2 / v1 where still valid) and open questions

## v3.4: no green highlight; a blocked chain is a warning (2026-10-10)

Measured first (`../results/plancell/REPORT.md`, 1,200 real positions, the coach playing on).
- **Green is gone.** In its plan case, green matched what the coach then did 40% of the time. Its merge case marks two
  equal tiles you can already see. Highlights now only mark where a move went wrong (red). The engine still sends
  `hint_cells`, but the app ignores them.
- **Blocked chain.** With Explain, a blocked chain shows as a warning in place of the plan: "Chain blocked. The 128 in
  the top row, third column blocks your chain: merge it away or rebuild the chain around it."
  - A blocked chain means a bigger tile sits in the cell the chain needs next.
  - It is the one plan insight that holds up: the coach goes through the blocked cell only 8% of the time.
- **Not done: a labelled plan cell** ("build an 8 here"). It would be right only 37-45% of the time for grow/build.

## v3.3: grades only, and a shorter grade line (2026-10-10)

- **Grades only.** This is the user's idea: play on your own, see how you are doing, and dig in only when curious.
  - With the coach off, the folded panel offers one option, "Grades only" (off by default, so "off" can still mean just
    the game).
  - With it on, each move gets its grade under the board and nothing else: no arrow, list, reasons or warnings.
  - A questionable move or blunder adds "Why?" and Undo. "Why?" turns the coach on, and the line then gives the reason
    and the coach's move.
  - Review and the game-over counts work in this mode too.
- **A shorter line under the board.** The move's name is gone, since you just played it. A best move shows only "Best".
  Other grades show the reason, the coach's move and Undo, as before.

## v3.2: design polish (2026-10-10)

A cleanup pass within the existing look, with no new features. Method: Playwright screenshots of the key states
(`qa/design-shots.mjs`, before/after in `qa/design/`), critique, change, screenshot again.

- **Panel:** no cards inside the card. The options sit in one tinted well, and the moves are one list with dividers.
  The move list has fixed columns, so the grade chips and bars line up. The panel is 400 px wide.
- **The plan:** a quiet line with an accent rule, not a blue block.
- **The coach plays:** one joined control. **Engine odds:** a disclosure with a chevron, not an underlined link.
- **Under the board:** "Move N" is gone (the counter below already says it). The better move reads "Coach: → Right".
  Undo is a small button on the same line. Each new grade fades in.
- **Feel:** "+N" floats up from the score after a merge, as in the original game. Bars animate their width. Switches,
  rows and buttons ease. Everything respects reduced motion.
- **Phone:** the panel sits under the board, so it shows the moves first, then the engine odds and "the coach plays".
  The settings come last, since you set them once. The desktop order is unchanged.
- **Fit:** the board grows on short laptop screens (430 px instead of 360 at 1280x720). The header lines up with the
  board and panel.
- Lighthouse is still 100 for accessibility. The QA journeys key on `data-k` rather than the removed "Move N" text.

## v3.1: the coach is the panel (2026-10-10, third round)

- **The panel is the coach.** A big Coach switch sits in the panel's header, with a subtitle: "Grades every move you
  make" or "Off: just the game". Off folds the panel to that header, hides the grade line, arrows and highlights, and
  Space and P do nothing.
- **Options are rows with a one-line description**, each with a switch:
  - Best move: the coach's move and every move's grade;
  - Explain (new): why each move is good or bad, and the plan;
  - Warn me: stop me before a blunder;
  - Highlights: green where the coach's move acts, red where a move went wrong.
- **Explain** brings back the useful text as an option, off by default:
  - each move's reason (the coach's move: what it does; others: what is wrong with them);
  - "good" moves' reasons in the grade line;
  - the plan in at most two sentences, without the engine's asides;
  - what the % means.
  - Without it, only a blunder's reason shows.
- **Engine odds** are cards with a bar (tile, %, bar), still behind the link and closed by default.
- **"The coach plays"** (1 / 10 / 100 / next tile / ∞ and the speed menu) moved to the bottom of the panel.
- Before the first move the grade line says "Make a move: the coach grades it here."


The user's direction:
- Simplify drastically.
- No player levels and no exact percentages; the AI's percentages are the only ones that matter, and not as a big bar.
- Players care whether a move was a blunder, questionable, or good but not the best.
- Blunders are obvious mistakes the AI would never make, such as taking tiles out of corners for no reason.
- Toggles instead of the Play / Coach / Analyze tabs; one toggle hides it all.
- The coach must keep up in real time.
- Much less text.
- Test every threshold in real situations: a 2048+ tile out of its corner, and random keys, must trigger.

**Grades** (src/analyze.cpp `grade_moves`; results/grades/REPORT.md):
- **Best** = the coach's move or within 0.5% value loss. **Good** = 0.5-5%. **Questionable** = 5%+ (where a deeper search
  almost never prefers the move) or a big tile pulled off the edge.
- **Blunder** = a named, obvious mistake that a fine move avoids: the biggest tile out of its corner, the biggest tiles
  off the edge, a move that lets 10%+ of new tiles end the game, or a 10%+ real loss.
- Blunders are read from the board because the engine's value misses them: it repairs a 2048 out of its corner and
  calls it cheap.
- The early game up to a 256 tile is free (no corner or edge verdicts): rollouts showed it costs nothing there.

**Checked:**
- **Corner breaks:** 98-100% are blunders from 512 on.
- **Random keys:** 41-47% flagged, the first within 2-3 moves.
- **Strong players:** 0.23% of their moves are blunders.
- **Where:** engine selftest case 12 and the QA journeys corner-blunder, edge-blunder, random-keys and free-stretch.

**Screen**, top to bottom:
- score, best, New game, ⋯;
- the board (with the coach's arrow when Best move is on);
- one grade line for the last move ("Move 41 → Right · Blunder · Takes your 2048 out of its corner · ↓ Down · Undo");
- undo/redo;
- "Coach plays 1 · 10 · 100 · Next tile · ∞" with a speed menu;
- four toggles.

Toggles:
- **Coach:** everything off = just the game.
- **Best move:** the arrow plus a move list: each move's grade and how often the coach would play it, as a bar and a %;
  a blunder's reason under it.
- **Warn me:** blunders only. The move waits for the coach's verdict, which takes 2 ms in the engine and is usually
  already there; a spinner shows after 0.1 s, and the move goes through after 2 s. It also warns when you replay a
  blunder after an undo.
- **Highlights:** at most 2-3 cells. Where the coach's move acts (a merge, or the next cell to build); after a flagged
  move, where it went wrong.

The engine's odds sit behind an "Engine odds" link in the move list, closed by default.

**Cut:**
- the eval bar, timeline, Review tab, review graph, accuracy, level, phases and decisive-moment cards;
- the plan text and the snake outline (replaced by highlights);
- "Deeper": 120-230 ms per position at depth 5, which made the coach lag;
- opening hints, "your chance", player levels and the automatic level reviews;
- the mode tabs and the intro card;
- the "next in the line" card, reason percentages and the engine's summary paragraph;
- "Copy the position" (copy link stays); the Edit button (the editor is in the ⋯ menu);
- the How page was cut down to one short screen.

**Review:** "Review your moves" in the ⋯ menu and on the game-over card. It shows counts by grade (your moves only) and
the questionable moves and blunders to jump to. Grades are kept with the game as you play (facts: the coach's move and
the played move's grade, 2 characters per position); a batch fills the gaps.

**The %** used to be "played by X% of players at your level", which needed a player level. It is now how often the
coach would play the move. It is fitted to which move a deeper search picks, so the coach's move has the top share and
a blunder about 0%.

**Kept:** undo/redo with the line model and its restore toast, autoplay (now 1/10/100/next tile/∞), the editor, links
to positions, shortcuts, offline play. "Your chance" (results/yc/) stays in the engine behind `--chance-model` as
research; the app does not load it.

## v2.1: your chance, and a coach's move people can follow (2026-10-10, first playtest)

The user's playtest found two problems:

1. However badly they played, the chance of 2048 stayed near 100%, and warnings came only on the game-ending move.
   With a 4096, moving it out of its corner showed 98% for 8192 and no warning.
2. The coach's early moves did not care where the biggest tile is.

The root cause is shared. Every number was the engine's: what the engine would make of the position if it took over.
It repairs almost anything early on. Measurements and the model: `results/yc/REPORT.md`.

- **Your chance** replaces the engine's odds as the main evaluation, up to a largest tile of 8192.
  - What it is: the chance that a player of your level, playing on themselves, reaches the next milestone (2048, then
    each doubling). It comes from the simulated human players of the personal odds, learned into small networks
    (`weights/calib/chance.hv`) and checked against rollouts from 210 real positions and against 237 real games.
  - Where it shows:
    - the eval bar, with a mark for the engine's odds and the cost of the last move in points;
    - the verdict under the board ("Mistake −7 pts", with "your chance of 2048: 62% → 55%");
    - the move list (each move's chance);
    - the warning sheet ("lowers your chance of reaching 4096 from 32% to 21%");
    - the timeline and the review graph (plain 0-100% scale);
    - the review's classes, decisive moment and key moments.
  - Classes, by the share of your chance a move gives away: inaccuracy 5% (and 2 points), mistake 10% (2 points),
    blunder 25% (4 points). Warnings start at 20% and 2 points. At the default level that is about 0.3-1.6 warnings per
    100 moves of real intermediate and strong players.
  - The engine's numbers stay visible as "the engine": the bar's mark and the "If the engine played on" odds in the
    analysis. From 16384 on, where no simulated player gets, the engine's numbers are used as before.
- **The coach's move** (Space, the board's arrow, the "Play" button, autoplay):
  - Up to a 512 tile it plays the corner strategy: the move a strong human makes (the human move model at a high skill,
    with your recent moves). It picks only among moves that cost nothing for the engine (real loss at most 0.5%) or for
    you (at most 1 point).
  - From 1024 on it plays the engine's move, which keeps the corner by itself there (20 of 21 positions at 512, all
    from 1024 to 4096).
  - This was the user's suggestion: separate concerns, a simple corner-minded coach in the opening, where the strong AI
    can pull any position back anyway. The analysis says why when it differs: "keeps your 128 in its corner". The
    engine's own preference is named in the panel ("the engine would play Down, as good for it").
- **The very early game stays quiet, by measurement.**
  - 76 random moves from the start do not lower a simulated player's chance of 2048: 600 playouts per move, even on
    the nearly full boards of moves 70-76. Small tiles are easily cleaned up. So random early moves are not graded as
    mistakes.
  - Instead, a corner-leaving move that costs nothing yet gets a note in place of a grade: "Left the corner · → Right
    keeps it · costs from 256 on". The corner is worth 2-3 points at 256 and 17-20 points with a 2048, and those moves
    are graded.
- **Your level.**
  - It comes from a review of a game you play yourself. Automatic 120 own moves into a line while it is unknown, as
    before. Reviews now send the level, so a review's costs are your chance at your level.
  - Until it is measured, the in-between default (-0.5) stands. Your chance never assumes a lower level: novice-level
    simulated players never reach 2048, and a 0% bar says nothing about moves.

## v2: one workbench instead of Play / Analyze / Review / History (2026-10-10)

The user's feedback after testing v1: undo (also after the game ends), the coach playing at various speeds (to zoom to a
late game or see how it plays on from a position), sliding back through the game, accepting the coach's move without
the arrow keys, Play and Analyze together, no game history needed: "a very active dojo with on-the-fly analysis and
experimentation instead of 'play a game, then analyze'".

- **One screen.** The board with the eval bar, a verdict line, the transport (start / back / forward / end, the move
  counter, "Play the coach's move"), the timeline and the autoplay controls on the left; on the right a panel with the
  mode switch and two tabs: Analysis (of the position on the board) and Review (of the whole line). The History screen
  and the separate Review and Analyze screens are gone (archived in `archive/v1/`); `/analyze`, `/history` and
  `/review/...` open the workbench; the explainer stays at `/how`.
- **The line.** One sequence of positions with a cursor (`web/src/lib/line.ts`). Undo/redo move the cursor; nothing is
  lost by going back. From an earlier position, playing the move the line already has *follows the line* (the same new
  tile: replaying is deterministic, as on a chess analysis board); any other move *replaces the continuation* (the user
  accepted losing it). Replacing 8+ moves, a new game and "Play from here" in the editor offer a 9-second "Restore"
  toast instead of a confirmation dialog (shorter replacements go quietly: going back one move to try another is the
  normal case). Every move records who played it: the player, or the coach (autoplay, Space, a taken warning).
- **Facts.** What the analyses said about each position (milestone chance, best move, cost of the move played from it)
  is kept with the line, 8 characters per position in localStorage, so the timeline and the review graph survive a
  reload. Live analyses and reviews fill them; reviews overwrite (they are the official verdicts of played moves).
- **Modes** (replacing Off / Warn me / Best move): **Analyze** (default) shows everything: eval bar, best-move arrow
  (clickable), the full analysis, and after each move a verdict line under the board ("Move 41 ↓ Down · Mistake −4.2% ·
  ← Left was best · Undo"); no blocking warnings (undo is right there). **Coach** keeps v1's warning sheet and opening
  hints, hides the analysis until asked (H), and when you step back to a costly move it says a better move exists
  without telling which (a find-it loop). **Play** is the plain game. v1's "off" opens as Play, the others as Analyze.
- **The coach's move** once: Space/Enter, the "Play ↓ Down" button, or a click on the arrow at the board's edge.
- **Autoplay** ("Coach plays", P): 1/s, 3/s, 10/s or full speed; until stopped, until the next tile, or for 100 moves;
  any move key, undo or Esc stops it. The coach plays the analysis' reference move (loss 0), the move the panel shows
  as best, so a played-back line agrees with the analysis. Below full speed: one analysis request per move (the eval
  bar and verdicts update live; animations up to 10/s). At full speed at the end of the line: `POST /api/autoplay`
  batches of 24 moves (the server plays them with the same analyses and a client-chosen seed; the client checks every
  move and tile against its own rules). Measured on this laptop: ~65 moves/s with one request per move in Chrome (the
  browser's ~4.6 ms per fetch dominates), ~150/s with batches (the rest is the engine's ~3 ms and WSL's ~4 ms pipe
  round trip per analysis; on a real Linux server the pipe costs ~0.1 ms). During fast autoplay the panel shows a
  compact "the coach is playing" card and the view renders once per frame.
- **Review in the panel**, of the whole line, on request (R) or by itself at the end of a game (up to 4,000 moves).
  When the coach played part of the line its moves are left out (`web/src/lib/summary.ts`: the engine's own formulas,
  lichess accuracy on the real loss, classes, key moments, decisive moment): coach moves cost nothing and would inflate
  the good-move share, the accuracy and the level. The level is measured only when the player made 90%+ of the moves.
  A review that no longer matches the line (moves replaced after it) says which moves it still covers and offers an
  update. Lines longer than 20,000 moves are reviewed from their last 20,000.
- **Editor on the board** (E or the menu): the board becomes the editor, the palette and samples appear under it, the
  panel analyzes every change, "Play from here" makes it the new line. Copy the position or a link to it from the menu.
- **Keyboard first, touch equal**: every action has a key (`?` lists them); buttons give the keys back to the board after
  a click (no focus trap: Space after clicking "Back" plays the coach's move, not "Back" again); the timeline is an ARIA
  slider (arrows scrub only while it has focus). Phone: swipes, the transport buttons, taps on the timeline and arrows.
- **Rate limits** (local defaults): analyses 200/s (burst 400) per IP, autoplay batches 20/s (burst 40). v1 had 20/s
  analyses, which capped autoplay at 20 moves/s. A public server needs a decision (see the open questions).

## v1 decisions (2026-10-07; the parts above replace the play / review / history screens)

### Product

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

### Engineering

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

## Deliberately left out

v1 left out undo (it would blur what a review means); v2 adds it, and reviews count only the player's moves. Still out:
a tree of variations (alternatives are replaced, with a short restore window), game history, sharing whole games (a link
shares a position), accounts/sync, server-side storage, analytics, service-worker offline mode, translations, sound.
Screenshot import, LLM chat, WASM and payments were non-goals.

## Open questions

0. **Your chance for weak players and in-game skill** (v2.1).
   - For players whose chance of 2048 is near 0, the next doubling would be the informative target. That needs networks
     for it (stages up to 512).
   - With that target, a live skill estimate from the current game's moves could make the bar reflect a run of poor
     play ("if you keep playing like this"). Today a run of random moves early on leaves the bar where it was, because
     the position itself is not worse. for you

1. **Name.** "2048 Coach" is a working title (the UI, `<title>` and manifest use it; one place each). Is "2048" in the
   name acceptable for you legally and brand-wise? (The original game is MIT-licensed; the name is used by many clones.)
2. **Domain** and whether the app should live at the root or under a path.
3. **Which odds lead the eval bar.** The bar shows the engine's odds ("with best play"); they sit at 99%+ until real
   danger. Personal odds (`--skill`) are much lower and more personal, but they depend on the estimated level and are
   rougher. Keep, swap, or show both once the level is known (a marker shows them now)?
7. **Autoplay on a public server.** Full-speed autoplay keeps one engine worker ~50-100% busy per user (300+ analyses/s
   on a Linux server). Options: per-IP batch limits (now 20 batches/s), a cap on the speed, or autoplay in the browser
   (WASM build + the 55 MB stage-0 network, which covers everything below 16384).
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
