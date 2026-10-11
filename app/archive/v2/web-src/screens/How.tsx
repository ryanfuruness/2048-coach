import { Link } from '../components/ui.tsx';
import { useTitle } from '../lib/hooks.ts';

export function How() {
  useTitle('How it works · 2048 Coach');
  return (
    <div class="page how narrow">
      <div class="page-head">
        <h1>How it works</h1>
        <p class="lead">
          2048 Coach is a board to play on with a strong 2048 engine beside you. It analyzes every position you reach, lets you take back moves and try other
          ones, plays on from any position when you ask, and reviews your game, using what research with real players' games found to matter.
        </p>
      </div>

      <section>
        <h2>One board for playing, analyzing and reviewing</h2>
        <ul class="how-list">
          <li>
            <strong>Take back any move.</strong> Undo (<kbd>Z</kbd>) and redo (<kbd>X</kbd>) step through the game, also after it ends. The timeline under the
            board shows the whole line: drag it to jump anywhere. From an earlier position, playing the move that was played follows the line; any other move
            starts a new line from there (a long continuation you replace can be restored right after).
          </li>
          <li>
            <strong>Let the coach play.</strong> <kbd>Space</kbd> (or a tap on the arrow at the board's edge) plays the coach's move once. "Coach plays"
            (<kbd>P</kbd>) plays on at one, three or ten moves a second, or as fast as the engine answers: until you stop it, until the next tile, or for 100
            moves. Use it to see how the coach would go on from a position, or to get to a late game quickly.
          </li>
          <li>
            <strong>The coach's move.</strong> In the opening (until your biggest tile is 512) the coach plays the corner strategy: your biggest tile stays in
            its corner, the big tiles line up along the edge, and it sticks to three directions, the way strong players play. It picks only among moves that
            cost nothing. The engine itself does not care this early because it can repair almost anything, so its own moves look random. From 1024 on, the
            coach plays the engine's move, which keeps the corner by itself there.
          </li>
          <li>
            <strong>Set up any position</strong> (<kbd>E</kbd>): place tiles on the board, paste a board, or pick a sample; the analysis follows every change.
            "Play from here" makes it the board's new line.
          </li>
          <li>
            <strong>Review the game</strong> (<kbd>R</kbd>) at any time: how it went, your key moments and your level. Moves the coach played are left out, so
            the review is about your own moves.
          </li>
        </ul>
      </section>

      <section>
        <h2>What the coach shows</h2>
        <ul class="how-list">
          <li>
            <strong>Analyze</strong> (the default): the analysis of the position on the board, live: the best move for you and why, every move with your chance
            after it, the plan. After each of your moves a line under the board says how good it was, with an undo right there.
          </li>
          <li>
            <strong>Coach</strong>: the analysis stays hidden until you ask (<kbd>H</kbd>). Just before you make a move that would cost you a fifth of your
            chance or more, the coach stops you, says what it does to your chance and offers a better move. Our research found that a warning right before a
            bad move is the most useful help there is: one or two warnings per 100 moves close most of the gap to the engine. Hints appear only in the opening
            (until your biggest tile is 512), in positions where players at your level often go wrong.
          </li>
          <li>
            <strong>Play</strong>: just the game. Undo, the timeline and the coach's autoplay still work, and you can look at the analysis of a position any
            time (<kbd>H</kbd>).
          </li>
          <li>The coach never makes you wait: if its analysis of a position is not ready yet, your move simply goes through.</li>
        </ul>
      </section>

      <section>
        <h2>The bar above the board: your chance</h2>
        <p>
          It shows <strong>your chance</strong> of reaching your next milestone tile (2048, then 4096, ...) if <em>you</em> play on from here: how often
          players at your level get there from this position. It comes from simulated players that move like real people (a model of 115,000 moves of 80
          real players, matched to how far those players actually got), not from the engine. The engine would rescue almost any position early on, so its own
          odds stay near 100% until the game is nearly lost; the thin mark on the bar shows them for comparison. After a move that cost you something, the bar
          says how many points it cost.
        </p>
        <p>
          Your level comes from a review of a game you played yourself (<kbd>R</kbd>); until then the coach assumes an in-between level. The chance covers
          games up to an 8192 tile. From 16384 on, where no simulated player gets, the bar shows the engine's odds again.
        </p>
      </section>

      <section>
        <h2>Reading the numbers</h2>
        <dl class="how-terms">
          <dt>Cost of a move</dt>
          <dd>
            How much of your chance a move gives away compared with the best move for you, in points (your chance of 2048 from 62% to 55%: 7 points). Keeping
            your biggest tile in its corner matters little in the first few hundred moves, then more and more: with a 2048, moving it out of its corner costs
            simulated players about a fifth of their chance of 4096, while the engine calls it free.
          </dd>
          <dt>Inaccuracy, mistake, blunder</dt>
          <dd>
            A move that gives away 5%, 10% or 25% of your chance or more (and at least 2, 2 or 4 points; smaller differences are within the model's noise).
            From 16384 on: the engine's real loss of 1-3%, 3-10%, 10% or more (the share of the expected score with good play afterwards).
          </dd>
          <dt>Engine</dt>
          <dd>
            The engine's own view: its odds if it played on, and a move's real loss for it (measured by letting it play on from 2,200 real positions of 80
            players). It is shown next to yours: it is the right measure for the late game, where the engine plays much better than people.
          </dd>
          <dt>Reasons</dt>
          <dd>
            Every reason for a costly move is checked in the position itself: the engine removes exactly that defect and measures how much of the loss comes back.
            "Mainly because" means it explains at least half of the loss, "partly because" less. The first reason is the main cause.
          </dd>
          <dt>Not judged</dt>
          <dd>
            Some strong players keep their biggest tiles in a 3x2 block in a corner. The engine plays a different formation (a snake along an edge), so it does not
            rate moves in such positions and shows its move only as a suggestion.
          </dd>
        </dl>
      </section>

      <section>
        <h2>Game reviews</h2>
        <ul class="how-list">
          <li>
            <strong>Good moves</strong>: the share of your moves that were not an inaccuracy or worse for you.
          </li>
          <li>
            <strong>Decisive moment</strong>: the move that cost you the most of your chance.
          </li>
          <li>
            <strong>Key moments</strong>: your mistakes and blunders, costliest first, each with its reasons.
          </li>
          <li>
            <strong>Your level</strong>: estimated from your moves with a model of how 80 real players move (higher is stronger). It needs about 50 moves, and only
            games you played (nearly) yourself count: when the coach played more than a tenth of the moves, the level is not measured. Hints and "your
            chances" adapt to it; until it is known the coach assumes an in-between level.
          </li>
          <li>For beginners, the moves a review flags are real losses. For strong players a review mostly confirms good play.</li>
        </ul>
      </section>

      <section>
        <h2>Privacy</h2>
        <p>
          There is no account. The game on the board and your level stay in this browser (local storage). To analyze a position, the board (and your last
          moves, which the model of players at your level uses) is sent to the analysis server; nothing else about you is.
        </p>
      </section>

      <div class="how-cta">
        <Link href="/" class="btn primary big">
          To the board
        </Link>
      </div>
    </div>
  );
}
