
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  advanceRound,
  getSession,
  type SessionResponse,
  startRoundTimer,
} from "../api/client";

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

  const handleStartTimer = async () => {
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
  };

  useEffect(() => {
    const deadline = session?.round_deadline;

    if (!deadline) {
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
  }, [session?.round_deadline]);

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <header>
        <p style={{ color: "var(--text-muted)", marginBottom: 4 }}>
          Host gameplay · Join code: {code}
        </p>
        <h1>Game Moderation</h1>
      </header>

      {loading && <p>Loading game...</p>}
      {error && <p role="alert">{error}</p>}

      {session && (
        <>
          {session.phase !== "voting" && (
            <section
              style={{
                marginTop: 24,
                padding: 24,
                border: "1px solid var(--border)",
                borderRadius: 12,
              }}
            >
              <p style={{ color: "var(--text-muted)" }}>
                Round {session.current_round}
              </p>
              <h2>Group Prompts</h2>

              {session.game_id === "quiplash" &&
              session.groups.length > 0 ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fit, minmax(280px, 1fr))",
                    gap: 16,
                  }}
                >
                  {session.groups.map((group) => (
                    <article
                      key={group.group_index}
                      style={{
                        padding: 16,
                        border: "1px solid var(--border)",
                        borderRadius: 8,
                      }}
                    >
                      <h3 style={{ marginTop: 0 }}>
                        Group {group.group_index + 1}
                      </h3>

                      <p>
                        <strong>Prompt:</strong>{" "}
                        {group.prompt || "No prompt available."}
                      </p>

                      {group.players.map((player) => (
                        <div
                          key={player.player_id}
                          style={{
                            marginTop: 12,
                            paddingTop: 12,
                            borderTop: "1px solid var(--border)",
                          }}
                        >
                          <strong>
                            {player.hidden ? "Hidden player" : player.name}
                          </strong>
                          <p style={{ marginBottom: 0 }}>
                            {group.answers[player.player_id] ??
                              "Waiting for response..."}
                          </p>
                        </div>
                      ))}
                    </article>
                  ))}
                </div>
              ) : (
                <p>{session.current_prompt ?? "No prompt available."}</p>
              )}
            </section>
          )}

          {session.phase === "voting" && (
            <section
              style={{
                marginTop: 24,
                padding: 24,
                border: "1px solid var(--border)",
                borderRadius: 12,
              }}
            >
              <p style={{ color: "var(--text-muted)" }}>
                Round {session.current_round}
              </p>
              <h2>Voting Results</h2>
              <p style={{ color: "var(--text-muted)" }}>
                Review each group’s answers and the votes received.
              </p>

              {session.game_id === "quiplash" &&
              session.groups.length > 0 ? (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fit, minmax(280px, 1fr))",
                    gap: 16,
                  }}
                >
                  {session.groups.map((group) => (
                    <article
                      key={group.group_index}
                      style={{
                        padding: 16,
                        border: "1px solid var(--border)",
                        borderRadius: 8,
                      }}
                    >
                      <h3 style={{ marginTop: 0 }}>
                        Group {group.group_index + 1}
                      </h3>

                      <p>
                        <strong>Prompt:</strong>{" "}
                        {group.prompt || "No prompt available."}
                      </p>

                      {group.players.map((player) => (
                        <div
                          key={player.player_id}
                          style={{
                            marginTop: 12,
                            paddingTop: 12,
                            borderTop: "1px solid var(--border)",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              gap: 16,
                            }}
                          >
                            <strong>
                              {player.hidden ? "Hidden player" : player.name}
                            </strong>
                            <span
                              style={{
                                whiteSpace: "nowrap",
                                fontWeight: 600,
                              }}
                            >
                              Votes: {group.vote_counts[player.player_id] ?? 0}
                            </span>
                          </div>

                          <p style={{ marginBottom: 0 }}>
                            {group.answers[player.player_id] ??
                              "No answer submitted."}
                          </p>
                        </div>
                      ))}
                    </article>
                  ))}
                </div>
              ) : (
                <p>No voting results available.</p>
              )}
            </section>
          )}

          {secondsRemaining !== null && (
            <p role="timer" aria-live="off">
              Time remaining: {secondsRemaining}s
            </p>
          )}
        </>
      )}

      <section style={{ marginTop: 24 }}>
        <label htmlFor="round-timer-duration">
          Round timer duration
        </label>

        <select
          id="round-timer-duration"
          value={timerDuration}
          onChange={(event) => setTimerDuration(Number(event.target.value))}
          disabled={isStartingTimer}
        >
          <option value={30}>30 seconds</option>
          <option value={60}>60 seconds</option>
          <option value={90}>90 seconds</option>
          <option value={120}>120 seconds</option>
          <option value={180}>180 seconds</option>
          <option value={300}>300 seconds</option>
        </select>

        <button
          type="button"
          onClick={handleStartTimer}
          disabled={isStartingTimer || !session?.game_started}
        >
          {isStartingTimer ? "Starting Timer..." : "Start Round Timer"}
        </button>

        {timerError && <p role="alert">{timerError}</p>}
      </section>

      <section style={{ marginTop: 32, textAlign: "center" }}>
        {advanceError && <p role="alert">{advanceError}</p>}

        <button
          type="button"
          onClick={handleAdvanceRound}
          disabled={isAdvancing || !session?.game_started}
        >
          {isAdvancing ? "Starting next round..." : "Start Next Round"}
        </button>
      </section>

      <p style={{ marginTop: 24 }}>
        <Link to={`/host/lobby/${code}`}>Back to lobby</Link>
      </p>
    </main>
  );
}
