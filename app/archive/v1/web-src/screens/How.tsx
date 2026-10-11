import { Link } from '../components/ui.tsx';
import { useTitle } from '../lib/hooks.ts';

export function How() {
  useTitle('How it works · 2048 Coach');
  return (
    <div class="page how narrow">
      <div class="page-head">
        <h1>How it works</h1>
        <p class="lead">
          2048 Coach plays along with you. A strong 2048 engine looks at every position you reach, and the coach uses what it finds, based on research with real
          players' games, to help you only when it matters.
        </p>
      </div>

      <section>
        <h2>The coach while you play</h2>
        <ul class="how-list">
          <li>
            <strong>Warn me</strong> (the default): just before you make a move that would cost you a lot, the coach stops you, says what the move costs and offers a
            better one. One tap takes the suggestion, another plays your move anyway. Our research found that a warning right before a bad move is the most useful
            help there is: one or two warnings per 100 moves close most of the gap to the engine.
          </li>
          <li>
            <strong>Hints</strong> appear only in the opening (until your biggest tile is 512), in positions where players at your level often go wrong: "Tricky
            position · want a hint?". That is where hints were shown to help on real games.
          </li>
          <li>
            <strong>Best move</strong> shows the engine's move all the time. <strong>Off</strong> lets you play alone; your game is still saved for review.
          </li>
          <li>The coach never makes you wait: if its analysis of a position is not ready yet, your move simply goes through.</li>
        </ul>
      </section>

      <section>
        <h2>The bar above the board</h2>
        <p>
          It shows the chance of reaching your next milestone tile (2048, then 4096, ...) <em>with best play from here</em>: how often the engine gets there if it
          takes over. It stays high most of the game because the engine repairs a lot of damage; it falls when the board is in real danger. Its color compares the
          position with a typical one at this stage: green is fine, amber is a bit worse, red is in trouble.
        </p>
      </section>

      <section>
        <h2>Reading the numbers</h2>
        <dl class="how-terms">
          <dt>Cost of a move (real loss)</dt>
          <dd>How much of the expected score with good play afterwards a move gives up, as measured by letting the engine play on from 2,200 real positions of 80 players.</dd>
          <dt>Your chances</dt>
          <dd>
            The share of <em>your own</em> chances of reaching the next tile (the next doubling of your biggest tile) that a move gives away. Human players repair less
            than the engine, so this is usually larger than the real loss.
          </dd>
          <dt>Inaccuracy, mistake, blunder</dt>
          <dd>A move that costs 1-3%, 3-10%, or 10% or more.</dd>
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
            <strong>Best or good moves</strong>: the share of moves that cost under 1%. Players who reach 1024 make about 99% of them; the rest decides the game.
          </li>
          <li>
            <strong>Decisive moment</strong>: the most costly move made from a still-healthy position. This is the most reliable part of a review.
          </li>
          <li>
            <strong>Key moments</strong>: the biggest losses, each with its reasons. Only moves costing 3% or more are listed; smaller differences are within the
            noise of the measurements, so a review may list none.
          </li>
          <li>
            <strong>Your level</strong>: estimated from your moves with a model of how 80 real players move (higher is stronger). It needs about 50 moves. Hints and
            "your chances" adapt to it; until it is known the coach assumes an in-between level.
          </li>
          <li>For beginners, the moves a review flags are real losses. For strong players a review mostly confirms good play.</li>
        </ul>
      </section>

      <section>
        <h2>Privacy</h2>
        <p>
          There is no account. Your games, reviews and level stay in this browser (local storage). To analyze a position, the board is sent to the analysis
          server; nothing else about you is.
        </p>
      </section>

      <div class="how-cta">
        <Link href="/" class="btn primary big">
          Start playing
        </Link>
        <Link href="/analyze" class="btn big">
          Analyze a position
        </Link>
      </div>
    </div>
  );
}
