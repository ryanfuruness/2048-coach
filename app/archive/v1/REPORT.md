# QA report: 2048 Coach v1 (local)

Date: 2026-10-07. Saved by the coordinator from the app agent's final report (the agent could not write this file).

The server ran `node server/src/index.ts` with 1 engine worker (`--preset best-notables --packed
weights/serve/v6c_i16.wp --stdin --stdin-player`). The browser was the installed Chrome 154, headless, driven by
Playwright 1.63. Phone: 390x844 at 2x with touch emulation. Desktop: 1440x900.

To repeat: `npm run qa` (~65 s), `npm run lighthouse` (~60 s), `npm test`, and `npm run test:engine` with the server
stopped.

## Result

- All 12 journeys pass with no console errors, page errors, failed requests or HTTP errors (`qa/results.json`).
- Lighthouse scores 100/100/100/100 (performance, accessibility, best practices, SEO) on Play, Analyze and How, mobile
  and desktop.
- All tests pass.
- `build/analyze --selftest` has 0 failures with the default preset (exact tables, 3.6 GB peak, run alone) and with
  `--preset best-notables --packed`.

## Journeys

| journey | checked | result |
|---|---|---|
| first-visit | fresh browser, phone and desktop: 2 tiles, coach "Warn me", eval bar filled | pass |
| keyboard-desktop | 55 moves by arrow keys; "Best move" shows the arrow | pass |
| swipe-phone | 20 real CDP touch swipes: 18 moves; the 2 illegal swipes shake the board | pass |
| warning | near-dead debug board, Right is costly: warning sheet (key / swipe), "Play Down" continues | pass |
| game-over | debug board + seed: game-over card with "Review this game" | pass |
| full-game-review | 295-move game with coach on (2 warnings: 1 taken, 1 overridden); review; arrow and Shift+arrow stepping; same review on phone | pass |
| editor-play-from-here | palette builds a position; pasted string loads; Play from here; opening hint offered and opens | pass |
| not-judged-block | expert 3x2 block (32768): "Not judged", engine move shown only as a suggestion | pass |
| offline | `/api` refused: game playable, eval bar says "Coach offline" | pass |
| history / how / dark-mode | list with review summary; explainer; dark Play and Review | pass |

## Screenshots (`qa/screens/`)

| screen | phone | desktop |
|---|---|---|
| Play, first visit | 01-first-visit-phone | 01-first-visit-desktop |
| Play, mid-game | 03-swipe-phone | 02-keyboard-desktop |
| Best move mode | | 02-best-move-desktop |
| Hint opened | 07-hint-open-phone | 07-hint-open-desktop |
| Warning | 04-warning-phone (+04-after-warning-phone) | 04-warning-desktop |
| Game over | 05-game-over-phone | 05-game-over-desktop |
| Review | 06-review-phone(-full) | 06-review-desktop(-full) |
| Review step-through | 06-review-step-phone | 06-review-step-desktop |
| Analyze | 07-editor-phone | 07-editor-desktop(-full) |
| Not judged | | 11-not-judged-desktop |
| Play from here | 07-play-from-here-phone | 07-play-from-here-desktop |
| History | 08-history-phone | 08-history-desktop |
| How it works | 09-how-phone | 09-how-desktop |
| Dark mode | 10-dark-play-phone | 10-dark-review-desktop |
| Offline | 12-offline-phone | |

In the `-full` captures the fixed phone tab bar shows mid-page; that is a capture artifact, not a page bug.

## Lighthouse (`qa/lighthouse/`)

| page | preset | perf | a11y | BP | SEO | FCP | LCP | TBT | CLS | transfer |
|---|---|---|---|---|---|---|---|---|---|---|
| Play | mobile | 100 | 100 | 100 | 100 | 1.1 s | 1.7 s | 0 | 0 | 94 KB |
| Play | desktop | 100 | 100 | 100 | 100 | 0.3 s | 0.4 s | 0 | 0.001 | 94 KB |
| Analyze | mobile/desktop | 100 | 100 | 100 | 100 | 1.2/0.3 s | 1.7/0.4 s | 0 | <= 0.005 | 94 KB |
| How | mobile/desktop | 100 | 100 | 100 | 100 | 1.2/0.3 s | 1.7/0.4 s | 0 | <= 0.005 | 92 KB |

First load is about 19 KB JS and 8 KB CSS (gzip) plus a 48 KB self-hosted font, with no other origins.

## Tests

- vitest, 20 tests:
  - rules: merges, all directions, tile tracking, big tiles, spawn distribution over 140k draws, ambiguous
    transitions, encodings;
  - game-record replay; the animation model always ends on the exact board; formatting;
  - client rules vs `build/analyze` on 3,000 boards: legal moves, afterstates, points and game over all identical
    (over 5,000 comparisons).
- node:test, 13 tests:
  - validation, rate limiter, LRU cache, review slimming;
  - engine pool with a fake engine: ordering, crash recovery, hang -> timeout -> restart, full queue refused;
  - API end to end with the real engine.

## Measured speed

- Analysis: one player p50 5 ms, p95 16 ms. With 8 concurrent clients one worker serves 260/s (p50 21 ms).
- Review: 295 moves in ~0.5 s; 3,000 moves in 1.8 s (130 KB gzipped).
- Engine start: ~1 s.

## Found in the screenshots and fixed

1. The desktop board was not square, so tiles sat off the grid.
2. The review page overflowed horizontally on phones; the graph drew at 640 px before measuring. This also blocked a
   click in the first QA run.
3. The eval graph was flat at 100%. It now uses a scale stretched near 100%, a lost game ends at 0%, and the cost panel
   is labeled.
4. The desktop warning covered the board; it now sits beside the board, and the phone sheet is more compact.
5. Warnings now cite only checked causes, and a game-ending move says exactly that.
6. The palette's white numbers failed contrast (Lighthouse 96); they are now large text and score 100.
7. Edge arrows were clipped on phones, and tapped cells kept a hover outline.
8. "Not judged" was explained twice; expert positions no longer show "played by X%".
9. Wording fixes: "1 moves", 99.7% shown as 100%, unclear warning counts, an arrow overlapping the controls hint.
10. Under WSL, chrome-launcher created a profile folder named "C:\..." inside `app/`. It is removed, and the runner now
    passes its own temp profile. (Coordinator, 2026-10-07: one more such folder,
    `\\wsl.localhost\Ubuntu-22.04\tmp\lighthouse-profile-*`, was found and removed - check after `npm run lighthouse`.)

## Known gaps

- Engine odds sit near 100% for most of a casual game (this is how the odds behave).
- Only emulated Chrome was tested; no Safari, Firefox or real devices.
- The full game in QA is played by a script.
- No end-to-end review of a 16384+ game.
