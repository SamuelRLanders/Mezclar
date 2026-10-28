import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { getSession, playerSocketUrl, type SessionResponse, submitVote } from "../api/client";
import QuipInput from "./QuipInput";

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

  // const sessionId = state?.sessionId;

  const [session, setSession] = useState<SessionResponse | null>(null);
  const [playerPrompt, setPlayerPrompt] = useState<{
    round: number;
    prompt: string;
  } | null>(null);

  const [voting, setVoting] = useState<{
    round: number;
    groupIndex: number;
    prompt: string;
    answers: {
      player_id: string;
      answer: string;
    }[];
  } | null>(null);

  const [selectedAnswerId, setSelectedAnswerId] = useState<string | null>(
    null,
  );

  const [voteSubmitted, setVoteSubmitted] = useState(false);
  const [voteError, setVoteError] = useState("");
  const [voteSubmitting, setVoteSubmitting] = useState(false);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);

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
          error instanceof Error
            ? error.message
            : "Could not load the game."
        );
      })
      .finally(() => setLoading(false));
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || !playerId) {
      return;
    }

    const websocket = new WebSocket(
      playerSocketUrl(sessionId, playerId),
    );

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
          setSelectedAnswerId(null);
          setVoteSubmitted(false);
          setVoteError("");
          setVoteSubmitting(false);

          setSession((currentSession) =>
            currentSession
              ? { ...currentSession, phase: "voting" }
              : currentSession
          );

          setVoting({
            round: message.current_round,
            groupIndex: message.group_index,
            prompt: message.prompt,
            answers: message.answers,
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
                  : null
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

  async function handleSubmitVote() {
    if (!sessionId || !playerId || !selectedAnswerId || voteSubmitting || voteSubmitted) {
      return;
    }

    setVoteSubmitting(true);
    setVoteError("");

    try {
      await submitVote(sessionId, playerId, selectedAnswerId);
      setVoteSubmitted(true);
    } catch (error) {
      setVoteError(
        error instanceof Error
          ? error.message
          : "Could not submit your vote. Please try again.",
      );
    } finally {
      setVoteSubmitting(false);
    }
  }

  return (
    <main
      style={{
        maxWidth: 560,
        margin: "0 auto",
        padding: 24,
        textAlign: "center",
      }}
    >
      <p
        style={{
          color: "var(--text-muted)",
          fontSize: 14,
        }}
      >
        Game started
      </p>

      <h1>Get ready!</h1>

      <p>
        Welcome, {state?.playerName ?? "Player"}.
      </p>

      {loading && <p>Loading game...</p>}

      {error && <p role="alert">{error}</p>}

      {!loading && !error && session && (
        <section>
          <h2>Round {session.current_round}</h2>
          <p>
            {playerPrompt?.round === session.current_round
              ? playerPrompt.prompt
              : session.current_prompt ?? "Waiting for your prompt..."}
          </p>
          {session.game_id === "quiplash" && session.phase === "answering" && playerId && sessionId && (
            <QuipInput
              key={session.current_round}
              sessionId={sessionId}
              playerId={playerId}
            />
          )}

          {session.phase === "voting" &&
            voting &&
            voting.round === session.current_round && (
              <div>
                <h3>Vote for your favorite answer</h3>
                <p>{voting.prompt}</p>

                {voting.answers.map((option) => (
                  <button
                    key={option.player_id}
                    type="button"
                    onClick={() => setSelectedAnswerId(option.player_id)}
                    aria-pressed={selectedAnswerId === option.player_id}
                    style={{
                      display: "block",
                      width: "100%",
                      margin: "8px 0",
                      padding: 12,
                      border: selectedAnswerId === option.player_id
                        ? "2px solid var(--accent)"
                        : "1px solid var(--border)",
                      borderRadius: 8,
                      cursor: "pointer",
                    }}
                  >
                    {option.answer}
                  </button>
                ))}

                <p>
                  {selectedAnswerId
                    ? "Answer selected. Ready to vote!"
                    : "Select an answer to vote for."}
                </p>

                {voteError && <p role="alert">{voteError}</p>}
                  <button
                    type="button"
                    onClick={handleSubmitVote}
                    disabled={!selectedAnswerId || voteSubmitting || voteSubmitted}
                  >
                    {voteSubmitting
                      ? "Submitting vote..."
                      : voteSubmitted
                        ? "Vote submitted!"
                        : "Submit vote"}
                  </button>

              </div>
            )}
        </section>
      )}

      {secondsRemaining !== null && (
        <p role="timer" aria-live="off">
          Time remaining: {secondsRemaining}s
        </p>
      )}

      

      <p>
        Game: {state?.gameId ?? "Unknown"}
      </p>

      <Link to="/">Leave game</Link>
    </main>
  );
}