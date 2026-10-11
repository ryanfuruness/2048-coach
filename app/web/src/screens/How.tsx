import { Link } from '../components/ui.tsx';
import { useTitle } from '../lib/hooks.ts';

export function How() {
  useTitle('How it works · 2048 Coach');
  return (
    <div class="page how narrow">
      <h1>How it works</h1>
      <p class="lead">Play 2048 with a strong engine beside you. It grades every move you make.</p>

      <dl class="grades-key">
        <div>
          <dt>
            <span class="grade best">Best</span>
          </dt>
          <dd>The coach's move.</dd>
        </div>
        <div>
          <dt>
            <span class="grade good">Good</span>
          </dt>
          <dd>Fine, but the coach would play something else.</dd>
        </div>
        <div>
          <dt>
            <span class="grade questionable">Questionable</span>
          </dt>
          <dd>The coach would never play it, or it drifts your biggest tile away from the corners.</dd>
        </div>
        <div>
          <dt>
            <span class="grade blunder">Blunder</span>
          </dt>
          <dd>An obvious mistake: your biggest tile out of its corner, a big tile pulled off the edge, or a move that can end the game.</dd>
        </div>
      </dl>
      <p>Until your biggest tile reaches 512, corner and edge slips are questionable rather than blunders, and Warn me lets them pass.</p>

      <ul class="how-list">
        <li>
          The <strong>Coach</strong> panel beside the board turns it all on or off. <strong>Best move</strong> shows the coach's move and every move with how
          often the coach would play it. <strong>Explain</strong> says why, and gives the plan. <strong>Warn me</strong> stops you before a blunder.{' '}
          <strong>Highlights</strong> mark the tiles where a move went wrong.
        </li>
        <li>
          To play on your own, turn the coach off and keep <strong>Grades only</strong>: you see just the grade of each move, and
          open the coach when you want to know why.
        </li>
        <li>
          In the panel, <strong>the coach plays</strong> 1, 10 or 100 moves, up to the next tile, or until you stop it.
        </li>
        <li>
          Undo and redo anytime (<kbd>Z</kbd> <kbd>X</kbd>). Play a different move from an earlier position to try another line.
        </li>
      </ul>

      <p class="muted small">No account: your game stays in this browser. To grade a position, the board is sent to the analysis server.</p>

      <section class="credits" aria-labelledby="credits-title">
        <h2 id="credits-title">Credits</h2>
        <p>
          2048 is{' '}
          <a href="https://github.com/gabrielecirulli/2048" rel="noopener">
            Gabriele Cirulli's game
          </a>
          . The engine builds on research by Szubert &amp; Jaśkowski (n-tuple networks and TD learning for 2048), Oka &amp; Matsuzaki (the tuple
          set), Guei, Chen &amp; Wu (optimistic TD learning) and{' '}
          <a href="https://github.com/macroxue/2048-ai" rel="noopener">
            macroxue's 2048-ai
          </a>{' '}
          (the idea of exact endgame tables). How people play was learned from public videos of human games.
        </p>
        <p>
          <a href="https://github.com/ryanfuruness/2048-coach" rel="noopener">
            Source on GitHub
          </a>{' '}
          (MIT license).
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
