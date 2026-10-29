
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  getSession,
  playerSocketUrl,
  type SessionResponse,
  submitVote,
} from "../api/client";
import QuipInput from "./QuipInput";
import "./GameLanding.css";

interface GameLandingState {
  playerId?: string;
  playerName?: string;
  sessionId?: string;
  gameId?: string;
}

export default function GameLanding() {
  const { state } = useLocation() as {
    state: GameLandingState | null;
  };

  const { playerId, sessionId } = state || {};

  const [session, setSession] = useState<SessionResponse | null>(null);
  const [playerPrompt, setPlayerPrompt] = useState<{
    round: number;
    prompt: string;
  } | null>(null);

  const [voting, setVoting] = useState<{
    round: number;
    groups: {
      group_index: number;
      prompt: string;
      answers: {
        player_id: string;
        answer: string;
      }[];
    }[];
  } | null>(null);

  const [selectedAnswerIds, setSelectedAnswerIds] = useState<
    Record<number, string>
  >({});

  const [voteSubmitted, setVoteSubmitted] = useState(false);
  const [voteError, setVoteError] = useState("");
  const [voteSubmitting, setVoteSubmitting] = useState(false);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(
    null,
  );

  useEffect(() => {
    if (!sessionId) {
      setError("Missing session information. Please rejoin the game.");
      setLoading(false);
      return;
    }

    getSession(sessionId)
      .then(setSession)
      .catch((error: unknown) => {
        setError(
          error instanceof Error ? error.message : "Could not load the game.",
        );
      })
      .finally(() => setLoading(false));
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || !playerId) {
      return;
    }

    const websocket = new WebSocket(playerSocketUrl(sessionId, playerId));

    websocket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === "player_prompt") {
          setPlayerPrompt({
            round: message.current_round,
            prompt: message.current_prompt,
          });
        }

        if (message.type === "voting_started") {
          setSelectedAnswerIds({});
          setVoteSubmitted(false);
          setVoteError("");
          setVoteSubmitting(false);

          setSession((currentSession) =>
            currentSession
              ? { ...currentSession, phase: "voting" }
              : currentSession,
          );

          setVoting({
            round: message.current_round,
            groups: message.groups,
          });
        }

        if (message.type === "round_updated") {
          setVoting(null);

          getSession(sessionId)
            .then((updatedSession) => {
              setSession(updatedSession);

              setPlayerPrompt((currentPrompt) =>
                currentPrompt?.round === updatedSession.current_round
                  ? currentPrompt
                  : null,
              );
            })
            .catch((error: unknown) => {
              setError(
                error instanceof Error
                  ? error.message
                  : "Could not load the next round.",
              );
            });
        }

        if (message.type === "game_finished") {
          setVoting(null);
          setPlayerPrompt(null);

          getSession(sessionId)
            .then(setSession)
            .catch((error: unknown) => {
              setError(
                error instanceof Error
                  ? error.message
                  : "Failed to load final results.",
              );
            });
        }
      } catch (error) {
        console.error("Failed to process WebSocket message:", error);
      }
    };

    websocket.onerror = (event) => {
      console.error("Game updates WebSocket error:", event);
    };

    return () => {
      websocket.close();
    };
  }, [sessionId, playerId]);

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

  async function handleSubmitVote() {
    if (
      !sessionId ||
      !playerId ||
      !voting ||
      voteSubmitting ||
      voteSubmitted ||
      !voting.groups.every((group) => selectedAnswerIds[group.group_index])
    ) {
      return;
    }

    setVoteSubmitting(true);
    setVoteError("");

    try {
      await Promise.all(
        voting.groups.map((group) =>
          submitVote(
            sessionId,
            playerId,
            group.group_index,
            selectedAnswerIds[group.group_index],
          ),
        ),
      );

      setVoteSubmitted(true);
    } catch (error) {
      setVoteError(
        error instanceof Error
          ? error.message
          : "Could not submit all votes. Please try again.",
      );
    } finally {
      setVoteSubmitting(false);
    }
  }

  const isFinished = session?.phase === "finished";
  const isVoting = session?.phase === "voting";
  const isAnswering = session?.phase === "answering";

  const prompt =
    playerPrompt && playerPrompt.round === session?.current_round
      ? playerPrompt.prompt
      : session?.current_prompt;

  const standings = Object.entries(session?.scores ?? {}).sort(
    ([, scoreA], [, scoreB]) => scoreB - scoreA,
  );

  return (
    <main className="game">
      <div className="game__inner">
        <header className="game__header">
          <Link to="/" className="game__back">
            <span aria-hidden="true">←</span> Leave game
          </Link>

          <div className="game__brand">
            <span className="game__brand-mark" aria-hidden="true">
              M
            </span>
            <span>MEZCLAR</span>
          </div>

          {session && !isFinished && (
            <span className="game__round-badge">
              ROUND {session.current_round}
            </span>
          )}
          {isFinished && (
            <span className="game__round-badge game__round-badge--finished">
              COMPLETED
            </span>
          )}
        </header>

        {loading && (
          <section className="game__message-card">
            <span className="game__eyebrow">GETTING THINGS READY</span>
            <h1>Loading your game...</h1>
            <p>Please wait while we get everything ready.</p>
          </section>
        )}

        {error && (
          <section className="game__message-card game__message-card--error">
            <span className="game__eyebrow">SOMETHING WENT WRONG</span>
            <h1>We hit a snag.</h1>
            <p role="alert">{error}</p>
            <Link to="/" className="game__secondary-button">
              Return home
            </Link>
          </section>
        )}

        {!loading && !error && session && (
          <>
            {isAnswering && (
              <section className="game__play">
                <div className="game__intro">
                  <span className="game__eyebrow">YOUR MOMENT TO SHINE</span>
                  <h1>
                    Make it <span>memorable.</span>
                  </h1>
                  <p>
                    Welcome, {state?.playerName ?? "Player"}. Come up with your
                    funniest answer.
                  </p>
                </div>

                <div className="game__prompt-card">
                  <div className="game__prompt-top">
                    <span className="game__prompt-icon" aria-hidden="true">
                      ✳
                    </span>
                    <span className="game__eyebrow">YOUR PROMPT</span>
                    {secondsRemaining !== null && (
                      <span
                        className={`game__timer ${
                          secondsRemaining <= 10 ? "game__timer--urgent" : ""
                        }`}
                        role="timer"
                        aria-live="off"
                      >
                        <span aria-hidden="true">◷</span> {secondsRemaining}s
                      </span>
                    )}
                  </div>

                  <h2>{prompt || "Waiting for your prompt..."}</h2>

                  <p className="game__prompt-hint">
                    Think outside the box. The funnier, the better.
                  </p>
                </div>

                {session.game_id === "quiplash" && playerId && sessionId && (
                  <div className="game__input-card">
                    <div className="game__section-heading">
                      <div>
                        <span className="game__eyebrow">YOUR ANSWER</span>
                        <h2>What have you got?</h2>
                      </div>
                      <span className="game__step">ROUND {session.current_round}</span>
                    </div>

                    <QuipInput
                      key={session.current_round}
                      sessionId={sessionId}
                      playerId={playerId}
                    />
                  </div>
                )}

                <p className="game__footnote">
                  Your answer will be revealed when voting begins.
                </p>
              </section>
            )}

            {isVoting && (
              <section className="game__play">
                <div className="game__intro">
                  <span className="game__eyebrow">THE CROWD DECIDES</span>
                  <h1>
                    Pick your <span>favorite.</span>
                  </h1>
                  <p>
                    Choose one answer for every prompt. Go with the one that
                    makes you laugh.
                  </p>
                </div>

                {voting && voting.round === session.current_round ? (
                  <>
                    <div className="game__vote-progress">
                      <div className="game__progress-copy">
                        <span>YOUR VOTES</span>
                        <strong>
                          {
                            voting.groups.filter(
                              (group) =>
                                selectedAnswerIds[group.group_index],
                            ).length
                          }{" "}
                          <span>/ {voting.groups.length}</span>
                        </strong>
                      </div>
                      <div
                        className="game__progress-track"
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={voting.groups.length}
                        aria-valuenow={
                          voting.groups.filter(
                            (group) => selectedAnswerIds[group.group_index],
                          ).length
                        }
                      >
                        <div
                          className="game__progress-fill"
                          style={{
                            width: `${
                              voting.groups.length
                                ? (voting.groups.filter(
                                    (group) =>
                                      selectedAnswerIds[group.group_index],
                                  ).length /
                                    voting.groups.length) *
                                  100
                                : 0
                            }%`,
                          }}
                        />
                      </div>
                    </div>

                    <div className="game__vote-groups">
                      {voting.groups.map((group, index) => (
                        <section
                          key={group.group_index}
                          className="game__vote-group"
                        >
                          <div className="game__vote-group-heading">
                            <span className="game__vote-number">
                              {String(index + 1).padStart(2, "0")}
                            </span>
                            <span className="game__eyebrow">
                              PROMPT {index + 1}
                            </span>
                            {selectedAnswerIds[group.group_index] && (
                              <span className="game__selected-label">
                                ✓ Selected
                              </span>
                            )}
                          </div>

                          <h2 className="game__vote-prompt">{group.prompt}</h2>

                          <div className="game__answer-options">
                            {group.answers.map((option, optionIndex) => {
                              const selected =
                                selectedAnswerIds[group.group_index] ===
                                option.player_id;

                              return (
                                <button
                                  key={option.player_id}
                                  type="button"
                                  className={`game__answer-option ${
                                    selected
                                      ? "game__answer-option--selected"
                                      : ""
                                  }`}
                                  onClick={() =>
                                    setSelectedAnswerIds((current) => ({
                                      ...current,
                                      [group.group_index]: option.player_id,
                                    }))
                                  }
                                  disabled={voteSubmitting || voteSubmitted}
                                  aria-pressed={selected}
                                >
                                  <span className="game__answer-letter">
                                    {String.fromCharCode(65 + optionIndex)}
                                  </span>
                                  <span className="game__answer-text">
                                    {option.answer}
                                  </span>
                                  <span className="game__answer-check">
                                    {selected ? "✓" : ""}
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        </section>
                      ))}
                    </div>

                    {voteError && (
                      <p className="game__error" role="alert">
                        {voteError}
                      </p>
                    )}

                    <div className="game__submit-area">
                      {voteSubmitted ? (
                        <div className="game__submitted">
                          <span className="game__submitted-icon">✓</span>
                          <div>
                            <strong>Votes locked in!</strong>
                            <p>Your choices have been submitted.</p>
                          </div>
                        </div>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="game__primary-button"
                            onClick={handleSubmitVote}
                            disabled={
                              !voting.groups.every(
                                (group) =>
                                  selectedAnswerIds[group.group_index],
                              ) ||
                              voteSubmitting ||
                              voteSubmitted
                            }
                          >
                            {voteSubmitting
                              ? "Submitting votes..."
                              : "Lock in my votes"}
                            {!voteSubmitting && (
                              <span aria-hidden="true">→</span>
                            )}
                          </button>
                          <p className="game__footnote">
                            Make sure you're happy with your choices before
                            submitting.
                          </p>
                        </>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="game__message-card">
                    <span className="game__eyebrow">GET READY</span>
                    <h2>Voting is about to begin.</h2>
                    <p>Your answer choices will appear here shortly.</p>
                  </div>
                )}
              </section>
            )}

            {isFinished && (
              <section className="game__results">
                <div className="game__results-hero">
                  <span className="game__trophy" aria-hidden="true">
                    ♛
                  </span>
                  <span className="game__eyebrow">THAT'S A WRAP</span>
                  <h1>
                    Game <span>over!</span>
                  </h1>
                  <p>
                    That's what we call a good round. Here's how everyone
                    finished.
                  </p>
                </div>

                <section className="game__leaderboard">
                  <div className="game__section-heading">
                    <div>
                      <span className="game__eyebrow">THE FINAL TALLY</span>
                      <h2>Leaderboard</h2>
                    </div>
                    <span className="game__count">
                      {standings.length} PLAYERS
                    </span>
                  </div>

                  {standings.length > 0 ? (
                    <div className="game__standings">
                      {standings.map(([standingPlayerId, score], index) => {
                        const player = session.players.find(
                          (candidate) =>
                            candidate.player_id === standingPlayerId,
                        );

                        const previousScore =
                          index > 0 ? standings[index - 1][1] : null;

                        const place =
                          previousScore === score
                            ? standings.findIndex(
                                ([, otherScore]) => otherScore === score,
                              ) + 1
                            : index + 1;

                        return (
                          <div
                            key={standingPlayerId}
                            className={`game__standing ${
                              index === 0 ? "game__standing--first" : ""
                            }`}
                          >
                            <span className="game__standing-place">
                              {place === 1
                                ? "♛"
                                : String(place).padStart(2, "0")}
                            </span>
                            <span className="game__standing-avatar">
                              {(player?.name ?? "?").charAt(0).toUpperCase()}
                            </span>
                            <span className="game__standing-name">
                              {player?.hidden
                                ? "Hidden player"
                                : player?.name ?? "Unknown player"}
                              {index === 0 && (
                                <span className="game__winner-label">
                                  WINNER
                                </span>
                              )}
                            </span>
                            <span className="game__standing-score">
                              {score}
                              <small>pts</small>
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="game__empty">
                      No final scores are available.
                    </p>
                  )}
                </section>

                <section className="game__round-results">
                  <div className="game__section-heading">
                    <div>
                      <span className="game__eyebrow">THE HIGHLIGHTS</span>
                      <h2>Round recap</h2>
                    </div>
                    <span className="game__count">
                      {session.round_results.length} ROUNDS
                    </span>
                  </div>

                  {session.round_results.length > 0 ? (
                    session.round_results.map((round) => (
                      <section
                        key={round.round}
                        className="game__result-round"
                      >
                        <h3 className="game__round-title">
                          <span>ROUND {round.round}</span>
                          <span className="game__round-line" />
                        </h3>

                        <div className="game__result-groups">
                          {round.groups.map((group, index) => (
                            <article
                              key={group.group_index}
                              className="game__result-card"
                            >
                              <span className="game__eyebrow">
                                PROMPT {index + 1}
                              </span>
                              <h4>{group.prompt}</h4>

                              <div className="game__result-answers">
                                {Object.entries(group.answers)
                                  .sort(
                                    ([playerA], [playerB]) =>
                                      (group.vote_counts[playerB] ?? 0) -
                                      (group.vote_counts[playerA] ?? 0),
                                  )
                                  .map(([answerPlayerId, answer]) => {
                                    const answerPlayer = session.players.find(
                                      (player) =>
                                        player.player_id === answerPlayerId,
                                    );

                                    return (
                                      <div
                                        key={answerPlayerId}
                                        className="game__result-answer"
                                      >
                                        <div className="game__result-answer-copy">
                                          <strong>
                                            {answerPlayer?.hidden
                                              ? "Hidden player"
                                              : answerPlayer?.name ??
                                                "Unknown player"}
                                          </strong>
                                          <p>{answer}</p>
                                        </div>
                                        <span className="game__result-votes">
                                          {group.vote_counts[answerPlayerId] ??
                                            0}
                                          <small>votes</small>
                                        </span>
                                      </div>
                                    );
                                  })}
                              </div>
                            </article>
                          ))}
                        </div>
                      </section>
                    ))
                  ) : (
                    <p className="game__empty">
                      No round results are available.
                    </p>
                  )}
                </section>

                <div className="game__end-note">
                  <span aria-hidden="true">✳</span>
                  Thanks for playing. Same time next round?
                </div>
              </section>
            )}
          </>
        )}

        <footer className="game__footer">
          <span>MEZCLAR · GAME ON</span>
          <Link to="/">Back to home</Link>
        </footer>
      </div>
    </main>
  );
}
