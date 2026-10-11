import { useState } from 'preact/hooks';
import { fromBoardCode, tileValue } from '@shared/rules.ts';
import { Board } from '../components/Board.tsx';
import { Confirm, Link, Stat } from '../components/ui.tsx';
import { int, relTime, share } from '../lib/format.ts';
import { clearHistory, currentGameId, deleteGame, history } from '../lib/games.ts';
import { useStore, useTitle } from '../lib/hooks.ts';
import { navigate } from '../lib/router.ts';
import { player, resetSkill, skillLabel } from '../lib/skill.ts';

export function History() {
  useTitle('Your games · 2048 Coach');
  const games = useStore(history);
  const me = useStore(player);
  const [confirm, setConfirm] = useState<null | { kind: 'one'; id: string } | { kind: 'all' }>(null);
  const current = currentGameId();
  const best = games.reduce((m, g) => Math.max(m, g.score), 0);
  const bestTile = games.reduce((m, g) => Math.max(m, g.maxRank), 0);
  const reviewed = games.filter((g) => g.review);

  return (
    <div class="page history">
      <div class="page-head">
        <h1>Your games</h1>
        <p class="lead">Kept in this browser only: no account, nothing to sign up for.</p>
      </div>
      <section class="stats" aria-label="Your stats">
        <Stat label="Your level" value={skillLabel(me.skill)} sub={me.skill === null ? 'after your first reviewed game' : `skill ${me.skill.toFixed(2)} · from ${me.samples.length} game${me.samples.length === 1 ? '' : 's'}`} />
        <Stat label="Games" value={String(games.length)} sub={`${reviewed.length} reviewed`} />
        <Stat label="Best score" value={int(best)} />
        <Stat label="Best tile" value={bestTile ? String(tileValue(bestTile)) : '–'} />
      </section>

      {games.length === 0 ? (
        <div class="card empty">
          <h2>No games yet</h2>
          <p>Play a game: it is saved here automatically, ready for a move-by-move review.</p>
          <Link href="/" class="btn primary">
            Play now
          </Link>
        </div>
      ) : (
        <ul class="game-list" role="list">
          {games.map((g) => {
            const b = fromBoardCode(g.final);
            const live = !g.over && g.id === current;
            return (
              <li key={g.id} class="game-item card">
                {b && <Board board={b} label="Final position" class="mini" />}
                <div class="game-info">
                  <div class="game-top">
                    <strong>{int(g.score)} points</strong>
                    <span class="tag neutral">best tile {tileValue(g.maxRank)}</span>
                    {live && <span class="tag best">in progress</span>}
                    {g.origin === 'position' && <span class="tag neutral">from a position</span>}
                  </div>
                  <div class="game-meta">
                    {relTime(g.startedAt)} · {g.moves} moves
                    {g.review ? ` · ${share(g.review.good)} best or good · accuracy ${g.review.accuracy.toFixed(1)}` : ''}
                  </div>
                  <div class="game-actions">
                    {live ? (
                      <Link href="/" class="btn small primary">
                        Continue
                      </Link>
                    ) : null}
                    {g.moves > 0 && (
                      <button type="button" class={`btn small ${live ? '' : 'primary'}`} onClick={() => navigate(`/review/${g.id}`)}>
                        {g.review ? 'Open review' : 'Review'}
                      </button>
                    )}
                    <button type="button" class="btn small ghost danger" onClick={() => setConfirm({ kind: 'one', id: g.id })}>
                      Delete
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {games.length > 0 && (
        <div class="history-foot">
          <button type="button" class="btn small ghost danger" onClick={() => setConfirm({ kind: 'all' })}>
            Clear all history
          </button>
        </div>
      )}

      {confirm && (
        <Confirm
          title={confirm.kind === 'all' ? 'Clear all history?' : 'Delete this game?'}
          body={confirm.kind === 'all' ? 'All games and your estimated level are removed from this browser.' : 'The game and its review are removed from this browser.'}
          yes={confirm.kind === 'all' ? 'Clear everything' : 'Delete'}
          onYes={() => {
            if (confirm.kind === 'all') {
              clearHistory();
              resetSkill();
            } else deleteGame(confirm.id);
            setConfirm(null);
          }}
          onNo={() => setConfirm(null)}
        />
      )}
    </div>
  );
}
