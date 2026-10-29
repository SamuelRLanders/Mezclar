import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  advanceRound,
  getSession,
  type SessionResponse,
  startRoundTimer,
} from "../api/client";
import "./HostGameView.css";

export default function HostGameView() {
  const { code } = useParams<{ code: string }>();

  const [session, setSession] = useState<SessionResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [isAdvancing, setIsAdvancing] = useState(false);
  const [advanceError, setAdvanceError] = useState("");

  const [timerDuration, setTimerDuration] = useState(60);
  const [isStartingTimer, setIsStartingTimer] = useState(false);
  const [timerError, setTimerError] = useState("");

  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(
    null,
  );

  useEffect(() => {
    if (!code) {
      setError("No session code found.");
      setLoading(false);
      return;
    }

    let isMounted = true;

    async function loadSession() {
      try {
        const data = await getSession(code!);

        if (isMounted) {
          setSession(data);
          setError("");
        }
      } catch (error) {
        if (isMounted) {
          setError(
            error instanceof Error
              ? error.message
              : "Unable to load the game.",
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadSession();

    const intervalId = window.setInterval(loadSession, 2000);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, [code]);

  async function handleAdvanceRound() {
    if (!code || isAdvancing) {
      return;
    }

    setIsAdvancing(true);
    setAdvanceError("");

    try {
      await advanceRound(code);
    } catch (error) {
      setAdvanceError(
        error instanceof Error
          ? error.message
          : "Unable to start the next round.",
      );
    } finally {
      setIsAdvancing(false);
    }
  }

  async function handleStartTimer() {
    if (!code || isStartingTimer) {
      return;
    }

    setIsStartingTimer(true);
    setTimerError("");

    try {
      await startRoundTimer(code, timerDuration);
      const updatedSession = await getSession(code);
      setSession(updatedSession);
    } catch (error) {
      setTimerError(
        error instanceof Error
          ? error.message
          : "Failed to start the round timer.",
      );
    } finally {
      setIsStartingTimer(false);
    }
  }

  useEffect(() => {
    const deadline = session?.round_deadline;

    if (!deadline || session?.phase === "finished") {
      setSecondsRemaining(null);
      return;
    }

    const updateCountdown = () => {
      const remaining = Math.max(
        0,
        Math.ceil((new Date(deadline).getTime() - Date.now()) / 1000),
      );

      setSecondsRemaining(remaining);
    };

    updateCountdown();

    const intervalId = window.setInterval(updateCountdown, 250);

    return () => window.clearInterval(intervalId);
  }, [session?.round_deadline, session?.phase]);

  const isFinished = session?.phase === "finished";

  const sortedStandings = Object.entries(session?.scores ?? {}).sort(
    ([, scoreA], [, scoreB]) => scoreB - scoreA,
  );

  return (
    <main className="host-game">
      <div className="host-game__inner">
        <header className="host-game__header">
          <Link to={`/host/lobby/${code}`} className="host-game__back">
            <span aria-hidden="true">←</span> Back to lobby
          </Link>

          <div className="host-game__brand">
            <span className="host-game__brand-mark" aria-hidden="true">
              M
            </span>
            <span>MEZCLAR</span>
          </div>

          {session && (
            <span
              className={`host-game__status ${
                isFinished
                  ? "host-game__status--finished"
                  : "host-game__status--active"
              }`}
            >
              {isFinished ? "COMPLETED" : "HOST VIEW"}
            </span>
          )}
        </header>

        <section className="host-game__intro">
          <span className="host-game__eyebrow">
            HOST CONTROL PANEL
            {code ? ` · JOIN CODE: ${code}` : ""}
          </span>

          <h1>
            {isFinished ? (
              <>
                Game <span>over.</span>
              </>
            ) : (
              <>
                Game <span>control.</span>
              </>
            )}
          </h1>

          <p>
            {isFinished
              ? "The game has ended. Review the final standings and round results below."
              : "Keep an eye on the action, manage the timer, and move the game forward."}
          </p>
        </section>

        {loading && (
          <section className="host-game__message">
            <span className="host-game__eyebrow">PLEASE WAIT</span>
            <h2>Loading game...</h2>
            <p>Getting the latest session details.</p>
          </section>
        )}

        {error && (
          <section className="host-game__message host-game__message--error">
            <span className="host-game__eyebrow">SOMETHING WENT WRONG</span>
            <h2>Unable to load the game.</h2>
            <p role="alert">{error}</p>
          </section>
        )}

        {!loading && !error && session && (
          <>
            {!isFinished && (
              <section className="host-game__overview">
                <article className="host-game__stat">
                  <span className="host-game__stat-label">CURRENT ROUND</span>
                  <strong>{session.current_round}</strong>
                </article>

                <article className="host-game__stat">
                  <span className="host-game__stat-label">PLAYERS</span>
                  <strong>{session.players.length}</strong>
                </article>

                <article className="host-game__stat">
                  <span className="host-game__stat-label">GAME PHASE</span>
                  <strong className="host-game__phase">
                    {session.phase === "voting"
                      ? "Voting"
                      : session.phase === "answering"
                        ? "Answering"
                        : session.phase}
                  </strong>
                </article>

                <article className="host-game__stat">
                  <span className="host-game__stat-label">TIME REMAINING</span>
                  <strong
                    className={
                      secondsRemaining !== null && secondsRemaining <= 10
                        ? "host-game__time host-game__time--urgent"
                        : "host-game__time"
                    }
                  >
                    {secondsRemaining !== null
                      ? `${secondsRemaining}s`
                      : "--"}
                  </strong>
                </article>
              </section>
            )}

            {isFinished ? (
              <div className="host-game__results">
                <section className="host-game__panel">
                  <div className="host-game__section-heading">
                    <div>
                      <span className="host-game__eyebrow">
                        THE FINAL TALLY
                      </span>
                      <h2>Final standings</h2>
                    </div>

                    <span className="host-game__count">
                      {sortedStandings.length} PLAYERS
                    </span>
                  </div>

                  {sortedStandings.length > 0 ? (
                    <div className="host-game__standings">
                      {sortedStandings.map(([playerId, score], index) => {
                        const player = session.players.find(
                          (candidate) => candidate.player_id === playerId,
                        );

                        return (
                          <div
                            key={playerId}
                            className={`host-game__standing ${
                              index === 0
                                ? "host-game__standing--first"
                                : ""
                            }`}
                          >
                            <span className="host-game__standing-place">
                              {String(index + 1).padStart(2, "0")}
                            </span>

                            <span className="host-game__avatar">
                              {(player?.name ?? "?")
                                .charAt(0)
                                .toUpperCase()}
                            </span>

                            <strong className="host-game__standing-name">
                              {player?.hidden
                                ? "Hidden player"
                                : player?.name ?? "Player"}
                              {index === 0 && (
                                <span className="host-game__winner">
                                  WINNER
                                </span>
                              )}
                            </strong>

                            <span className="host-game__score">
                              {score}
                              <small>pts</small>
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="host-game__empty">
                      No final scores available.
                    </p>
                  )}
                </section>

                <section className="host-game__panel">
                  <div className="host-game__section-heading">
                    <div>
                      <span className="host-game__eyebrow">
                        GAME HISTORY
                      </span>
                      <h2>Round results</h2>
                    </div>

                    <span className="host-game__count">
                      {session.round_results.length} ROUNDS
                    </span>
                  </div>

                  {session.round_results.length > 0 ? (
                    <div className="host-game__round-list">
                      {session.round_results.map((roundResult) => (
                        <section
                          key={roundResult.round}
                          className="host-game__round"
                        >
                          <h3 className="host-game__round-title">
                            <span>ROUND {roundResult.round}</span>
                            <span className="host-game__round-line" />
                          </h3>

                          <div className="host-game__group-grid">
                            {roundResult.groups.map((group) => (
                              <article
                                key={group.group_index}
                                className="host-game__group-card"
                              >
                                <span className="host-game__eyebrow">
                                  GROUP {group.group_index + 1}
                                </span>

                                <h4>
                                  {group.prompt || "No prompt available."}
                                </h4>

                                <div className="host-game__player-list">
                                  {group.players.map((player) => (
                                    <div
                                      key={player.player_id}
                                      className="host-game__player-entry"
                                    >
                                      <div className="host-game__player-heading">
                                        <strong>
                                          {player.hidden
                                            ? "Hidden player"
                                            : player.name}
                                        </strong>

                                        <span className="host-game__vote-count">
                                          {group.vote_counts[
                                            player.player_id
                                          ] ?? 0}
                                          <small>votes</small>
                                        </span>
                                      </div>

                                      <p>
                                        {group.answers[player.player_id] ??
                                          "No answer submitted."}
                                      </p>
                                    </div>
                                  ))}
                                </div>
                              </article>
                            ))}
                          </div>
                        </section>
                      ))}
                    </div>
                  ) : (
                    <p className="host-game__empty">
                      No round results available.
                    </p>
                  )}
                </section>
              </div>
            ) : (
              <>
                {session.phase !== "voting" && (
                  <section className="host-game__panel">
                    <div className="host-game__section-heading">
                      <div>
                        <span className="host-game__eyebrow">
                          ROUND {session.current_round}
                        </span>
                        <h2>Group prompts</h2>
                      </div>

                      <span className="host-game__count">
                        {session.groups.length} GROUPS
                      </span>
                    </div>

                    {session.game_id === "quiplash" &&
                    session.groups.length > 0 ? (
                      <div className="host-game__group-grid">
                        {session.groups.map((group) => (
                          <article
                            key={group.group_index}
                            className="host-game__group-card"
                          >
                            <span className="host-game__eyebrow">
                              GROUP {group.group_index + 1}
                            </span>

                            <h3>
                              {group.prompt || "No prompt available."}
                            </h3>

                            <div className="host-game__player-list">
                              {group.players.map((player) => (
                                <div
                                  key={player.player_id}
                                  className="host-game__player-entry"
                                >
                                  <strong>
                                    {player.hidden
                                      ? "Hidden player"
                                      : player.name}
                                  </strong>

                                  <p>
                                    {group.answers[player.player_id] ??
                                      "Waiting for response..."}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="host-game__fallback-prompt">
                        {session.current_prompt ?? "No prompt available."}
                      </p>
                    )}
                  </section>
                )}

                {session.phase === "voting" && (
                  <section className="host-game__panel">
                    <div className="host-game__section-heading">
                      <div>
                        <span className="host-game__eyebrow">
                          ROUND {session.current_round}
                        </span>
                        <h2>Voting results</h2>
                      </div>

                      <span className="host-game__count">
                        {session.groups.length} GROUPS
                      </span>
                    </div>

                    <p className="host-game__description">
                      Review each group's answers and the votes received.
                    </p>

                    {session.game_id === "quiplash" &&
                    session.groups.length > 0 ? (
                      <div className="host-game__group-grid">
                        {session.groups.map((group) => (
                          <article
                            key={group.group_index}
                            className="host-game__group-card"
                          >
                            <span className="host-game__eyebrow">
                              GROUP {group.group_index + 1}
                            </span>

                            <h3>
                              {group.prompt || "No prompt available."}
                            </h3>

                            <div className="host-game__player-list">
                              {group.players.map((player) => (
                                <div
                                  key={player.player_id}
                                  className="host-game__player-entry"
                                >
                                  <div className="host-game__player-heading">
                                    <strong>
                                      {player.hidden
                                        ? "Hidden player"
                                        : player.name}
                                    </strong>

                                    <span className="host-game__vote-count">
                                      {group.vote_counts[player.player_id] ??
                                        0}
                                      <small>votes</small>
                                    </span>
                                  </div>

                                  <p>
                                    {group.answers[player.player_id] ??
                                      "No answer submitted."}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="host-game__empty">
                        No voting results available.
                      </p>
                    )}
                  </section>
                )}

                {secondsRemaining !== null && (
                  <p className="host-game__timer-note" role="timer" aria-live="off">
                    Time remaining: {secondsRemaining}s
                  </p>
                )}

                <section className="host-game__controls">
                  <div className="host-game__control-heading">
                    <span className="host-game__eyebrow">HOST CONTROLS</span>
                    <h2>Manage the round</h2>
                    <p>
                      Set a time limit or move the game to the next round.
                    </p>
                  </div>

                  <div className="host-game__control-grid">
                    <div className="host-game__control-card">
                      <label
                        className="host-game__label"
                        htmlFor="round-timer-duration"
                      >
                        Round timer duration
                      </label>

                      <select
                        className="host-game__select"
                        id="round-timer-duration"
                        value={timerDuration}
                        onChange={(event) =>
                          setTimerDuration(Number(event.target.value))
                        }
                        disabled={isStartingTimer}
                      >
                        <option value={30}>30 seconds</option>
                        <option value={60}>60 seconds</option>
                        <option value={90}>90 seconds</option>
                        <option value={120}>120 seconds</option>
                        <option value={180}>180 seconds</option>
                        <option value={300}>300 seconds</option>
                      </select>

                      {timerError && (
                        <p className="host-game__error" role="alert">
                          {timerError}
                        </p>
                      )}

                      <button
                        type="button"
                        className="host-game__secondary-button"
                        onClick={handleStartTimer}
                        disabled={
                          isStartingTimer || !session.game_started
                        }
                      >
                        {isStartingTimer
                          ? "Starting timer..."
                          : "Start round timer"}
                      </button>
                    </div>

                    <div className="host-game__control-card host-game__control-card--advance">
                      <span className="host-game__label">
                        Ready to move on?
                      </span>

                      <p>
                        Start the next round and update the game for everyone.
                      </p>

                      {advanceError && (
                        <p className="host-game__error" role="alert">
                          {advanceError}
                        </p>
                      )}

                      <button
                        type="button"
                        className="host-game__primary-button"
                        onClick={handleAdvanceRound}
                        disabled={isAdvancing || !session.game_started}
                      >
                        {isAdvancing
                          ? "Starting next round..."
                          : "Start next round"}
                        {!isAdvancing && (
                          <span aria-hidden="true">→</span>
                        )}
                      </button>
                    </div>
                  </div>
                </section>
              </>
            )}
          </>
        )}

        <footer className="host-game__footer">
          <span>MEZCLAR · HOST CONTROL</span>
          <Link to="/">Back to home</Link>
        </footer>
      </div>
    </main>
  );
}