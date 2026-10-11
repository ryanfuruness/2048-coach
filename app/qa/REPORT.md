# QA report: 2048 Coach v3 (local)

## v3.1 (2026-10-10): the coach panel

Checks:
- typecheck clean;
- 36 web and 10 server unit tests pass (`npm test`; the engine tests are unchanged from v3);
- 17 of 17 journeys clean.

The coach-toggles journey now also checks:
- Explain shows reasons and the plan;
- Coach off folds the panel, and Space and P do not play;
- the engine odds are cards with bars, closed by default.

Screens: `05-explain-desktop`, `05-coach-off-desktop`, `05-engine-odds-desktop`, `07-swipe-phone-full` (the panel below
the board on a phone).

## v3 (2026-10-10): the coach's grades, simplified screen

v2's report, screenshots and journeys are archived in `archive/v2/`.

Checks:
- `npm run typecheck` is clean.
- `npm test`: 37 web and 15 server tests pass, the engine tests included.
- `build/analyze --selftest`: 0 failures; case 12 holds the user's sanity cases.
- `npm run qa`: 17 of 17 journeys clean (rewritten for v3).
- `npm run lighthouse`: 100/100/100/100 on phone and desktop for the board, a position link and How; CLS 0; about
  81 KB transferred.

| journey | checked |
|---|---|
| first-visit | defaults (coach and best move on, warnings and highlights off); no eval bar, timeline, tabs or engine odds; the move list with grades and %; no "of players" |
| corner-blunder | the 2048 snake moved Down: listed and graded "Blunder · Takes your 2048 out of its corner"; with Warn me the move is stopped, also when replayed after an undo |
| edge-blunder | the 4096 snake moved Down on a phone: "Blunder", the 2048 pulled off the edge |
| random-keys | random keys from a 2048 position: most flagged, the first right away |
| free-stretch | leaving the corner with a 128: not flagged |
| coach-toggles | highlights (hint cells, then 1-3 fault cells); Best move off hides the arrow and the list but not the grade; Coach off hides everything; engine odds behind a link |
| keyboard-undo, swipe-phone | keys, Space, Z/X, the arrow plays the coach's move; swipes |
| autoplay | "10" plays exactly 10, "100" 100, "Next tile" stops by itself, P/Esc |
| branch-restore | a different move from the list replaces 50 moves; "Undo" in the toast restores them |
| review | the review sheet counts only your moves; a flagged move jumps to its position |
| game-over, editor, not-judged-block, offline, persistence, shortcuts-how-dark | as in v2, in the new layout; a v2 game and v2 settings open (Coach mode becomes Warn me) |

Fixed after looking at the screenshots:
- The transport buttons spread across the full width.
- The coach's arrow overlapped the score boxes.
- The coach-plays row wrapped badly on phones.
- A generic "the corner strategy's move" caption was noise.


## v2.1 update (2026-10-10): your chance

Changes:
- The engine reports your chance and the coach's move.
- The app shows your chance in the bar, the grades, the warnings, the timeline and the review.
- Space and autoplay play the coach's move.
- Opening corner-habit notes.

Checks:
- `npm run typecheck` is clean.
- `npm test`: 37 web and 15 server tests pass, the engine tests included.
- New tests cover the class thresholds, facts with your chance, the review's skill and the chance fields in reviews.
- `build/analyze --selftest`: 0 failures, including the new case 12: chances in range, the coach keeps the corner in
  the opening, the engine's move from 1024 on.
- `npm run qa`: 15 of 15 journeys clean. The editor journey now waits for "Your chance of reaching 2048" instead of the
  engine's 16384 sentence.

Seen in the screenshots and fixed:
- The arrow on the board's top edge covered the bar's last line on phones: there is now space below the bar.
- The move list showed a higher chance on a move than on the recommended one (a difference of under 1 point in the
  opening). Moves within a point of the recommended one now read "as good".
- On a full board, a game-ending move read only −7 points: chances after a move now count the new tiles that end the
  game. It reads 20% → 2% with a warning.

Lighthouse was not re-run for v2.1. The layout changes are small: the bar's text and a 12 px margin.

Date: 2026-10-10. v1's report, screenshots and journeys are archived in `archive/v1/`.

The server ran `node server/src/index.ts` with 1 engine worker (`--preset best-notables --packed
weights/serve/v6c_i16.wp --stdin --stdin-player`). The browser was the installed Chrome 154, headless, driven by
Playwright 1.63. Phone: 390x844 at 2x with touch emulation. Desktop: 1440x900.

To repeat: `npm run qa` (~2 min), `npm run lighthouse` (~1.5 min; it now removes the stray WSL profile folder itself),
`npm test`, and `npm run test:engine` with the server stopped.

## Result

- All 15 journeys pass with no console errors, page errors, failed requests or HTTP errors (`qa/results.json`).
- Lighthouse (performance / accessibility / best practices / SEO):
  - desktop: 100/100/100/100 on the board, a position link and How;
  - phone: 99 and 97 performance on the board and a position link (total blocking time 120-180 ms on the throttled
    phone CPU), 100 on How; accessibility, best practices and SEO 100 everywhere.
- `npm run typecheck` is clean; all tests pass: 34 web tests and 15 server tests, engine tests included.

## Journeys

| journey | checked | result |
|---|---|---|
| first-visit | fresh browser, phone and desktop: mode Analyze, 2 tiles, eval bar and best move filled, welcome note | pass |
| keyboard-desktop | 35 moves by arrow keys; Space x5 plays 5 coach moves (marked "coach"); Z x3 + X -> move 38 of 40; a click on the board's arrow plays it | pass |
| swipe-phone | 20 real CDP touch swipes: 18 moves (2 illegal ones shake the board); the back button steps back | pass |
| coach-warning | Coach mode, near-dead board, Right: the warning sheet (key and swipe); taking the suggestion keeps the game alive | pass |
| game-over-undo | Right ends the game; the game-over card's Undo returns to the position, the move marked as a blunder in the panel | pass |
| autoplay | 1/s: 3 moves in 2.6 s; full speed: ~150 moves/s on new positions (more from the server cache); "until the next tile" stops by itself | pass |
| scrub-branch-restore | drag the timeline to the middle (the panel shows the move played next); a different move replaces the continuation; "Restore them" brings it back exactly; on the phone a tap on the timeline jumps | pass |
| review | 40 coach moves, then the player to the end (134 moves); the game-over Review: "You played 94 of these moves and the coach 40; only yours count"; a key moment jumps to its position; the same on the phone | pass |
| editor | E (desktop) / the menu (phone): palette taps with live analysis; a pasted board, "Play from here" (old line restorable); Coach mode offers the opening hint, which shows the arrow | pass |
| not-judged-block | expert 3x2 block (32768) from a link: "Not judged", the engine move as a suggestion | pass |
| offline | `/api` refused: moves still work, the eval bar says "Coach offline", autoplay stops with "The coach is offline" | pass |
| persistence | a reload keeps the line and the cursor (792 moves, at 785); a v1 game in progress opens as the line; v1 "Warn me" opens as Analyze | pass |
| shortcuts-a11y | `?` opens the shortcuts, Esc closes them; the focused timeline slider takes the arrow keys (two presses = two steps) | pass |
| how / dark-mode | explainer; dark phone board; dark desktop review | pass |

## Screenshots (`qa/screens/`)

| screen | phone | desktop |
|---|---|---|
| First visit | 01-first-visit-phone | 01-first-visit-desktop |
| Playing, stepped back with the played/best arrows | 03-swipe-phone(-full) | 02-keyboard-desktop |
| Warning (Coach mode) | 04-warning-phone | 04-warning-desktop |
| Game over, then Undo | 05-game-over-phone, 05-after-undo-phone | 05-game-over-desktop, 05-after-undo-desktop |
| Autoplay running / stopped | | 06-autoplay-running-desktop, 06-autoplay-stopped-desktop |
| Scrubbed back, restore toast | 07-scrubbed-phone | 07-scrubbed-desktop, 07-branch-toast-desktop |
| Review | 08-review-phone(-full) | 08-review-desktop(-full), 08-review-key-moment-desktop |
| Editor, play from here, hint | 09-editor-phone, 09-play-from-here-phone, 09-hint-open-phone | 09-editor-desktop, 09-play-from-here-desktop, 09-hint-open-desktop |
| Not judged | | 10-not-judged-desktop |
| Offline | 11-offline-phone | |
| Shortcuts | | 12-shortcuts-desktop |
| How it works | 13-how-phone | 13-how-desktop |
| Dark mode | 14-dark-phone | 14-dark-review-desktop |

In the desktop `-full` captures only the panel's visible part shows (the panel scrolls on its own).

## Measured speed

- Autoplay, one request per move (speeds up to 10/s, or an older server): ~65 moves/s at most in Chrome (the browser's
  fetch costs ~4.6 ms here, the engine ~3 ms).
- Autoplay at full speed (`/api/autoplay`, 24 moves per request): ~150 moves/s on new positions on this laptop: the engine's
  ~3 ms plus WSL's ~4 ms pipe round trip per analysis. 2048 comes after ~7 s, 8192 after ~30 s.
- Analysis: unchanged from v1 (one player p50 5 ms). Review: unchanged (295 moves ~0.5 s).

## Found in the screenshots and tests, and fixed

1. The transport row overflowed the phone screen by 6 px: smaller icon buttons and counter below 480 px.
2. Autoplay rendered the whole screen on every move (state updates per move): refs plus one render per frame, and a
   compact panel card during fast autoplay (~50 -> ~70 moves/s, then batches for ~150/s).
3. During full-speed autoplay the eval bar said "Waiting for the coach": it now shows the chance the batch reported.
4. Desktop layout shift (Lighthouse CLS 0.43-0.67, performance 77-79): the page grew past the window when the first
   analysis arrived and the scrollbar moved everything 7 px. `scrollbar-gutter: stable`, a fixed panel width and a panel
   that scrolls on its own (the page fits the window at 1280x720 to 1920x1080) -> CLS 0.01-0.02, performance 100.
5. Key hints on blue buttons had 3.95:1 contrast; the board's arrow buttons' names lacked their visible label: fixed
   (accessibility 97 -> 100).
6. Two quick arrow presses on the focused timeline moved one step (it used the rendered cursor): it uses the line's.
7. A hint could be skipped when a position's analysis was already cached (effect order): warnings and hints now belong
   to the position they were made for.
8. Choosing the autoplay stop rule with the mouse left the arrow keys on the select: it gives them back.
9. The editor's "Play from here" sat below the palette on phones: it is under the board now. Edit mode keeps the eval
   bar (the board no longer jumps in size). Play mode's bigger board pushed the autoplay row below the fold: same size.
10. Wording: "1 moves"; a game-over eval bar labelled "next tile"; a review of a line the coach played alone now says so
    instead of showing empty numbers.

## Known gaps

- Only emulated Chrome was tested; no Safari, Firefox or real devices.
- Engine odds sit near 100% for most of a casual game (unchanged; see DECISIONS.md, open question 3).
- No end-to-end review of a 16384+ game by a person (autoplay reaches it, reviews of long lines take ~2-10 s).
- Alternatives are replaced, not kept as a tree of variations (the user's choice for now).
