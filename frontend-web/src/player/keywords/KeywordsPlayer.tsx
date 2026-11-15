import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import {
  getKeywordsState,
  keywordsAction,
  keywordsSubmit,
  type KeywordsPlayerView,
} from "../../api/client";
import { usePlayerSocket } from "../usePlayerSocket";
import GatheringPhase from "./GatheringPhase";
import RevealPhase from "./RevealPhase";
import RolePhase from "./RolePhase";
import SpeakingPhase from "./SpeakingPhase";
import VotingPhase from "./VotingPhase";
import "./Keywords.css";

interface KeywordsPlayerState {
  playerId?: string;
  playerName?: string;
  sessionId?: string;
}

/*
 * The player's page for a Keywords game. It holds one `view` object (the
 * player's private view from the backend) and shows the screen for the
 * group's current phase. Three parts of this page each update the screen in
 * a different way, all by replacing `view`: the socket listener, the first
 * fetch, and the `act` helper used by buttons.
 * Phase components never fetch anything; they only render the view and call back.
 */
export default function KeywordsPlayer() {
  const { code } = useParams<{ code: string }>();
  const { state } = useLocation() as { state: KeywordsPlayerState | null };

  // Same lookups as the other player pages: navigation state first, then the saved ID.
  const sessionId = state?.sessionId ?? code;
  const playerId = state?.playerId ?? (sessionId ? sessionStorage.getItem("mezclar-player:" + sessionId) : null);

  const [view, setView] = useState<KeywordsPlayerView | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");

  // Keeps the screen live: the server pushes a fresh view whenever anyone in the group acts.
  const { connectionStatus, error: socketError } = usePlayerSocket(sessionId, playerId, {
    initialName: state?.playerName,
    onMessage: (message) => {
      if (message.type === "keywords_state") {
        // The message is the view plus a "type" field, which the view simply ignores.
        setView(message as unknown as KeywordsPlayerView);
      }
    },
  });

  // Fills the screen when the page first opens or is refreshed.
  useEffect(() => {
    if (!sessionId || !playerId) return;

    getKeywordsState(sessionId, playerId)
      .then(setView)
      .catch((error: unknown) => {
        setActionError(error instanceof Error ? error.message : "Could not load the game.");
      });
  }, [sessionId, playerId]);

  /*
   * Updates the screen right after this player presses a button, by showing the
   * view the request returns. `busy` disables the buttons while a request is in
   * flight so a double tap can't send it twice.
   */
  async function act(request: () => Promise<KeywordsPlayerView>) {
    setBusy(true);
    setActionError("");
    try {
      setView(await request());
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!sessionId || !playerId) {
    return (
      <main className="keywords">
        <p role="alert">Missing session or player information. Please rejoin the game.</p>
        <Link to="/">Back to start</Link>
      </main>
    );
  }

  if (!view) {
    return (
      <main className="keywords">
        <p>{actionError || "Loading your game..."}</p>
      </main>
    );
  }

  // Pick the screen for the group's current phase.
  let screen;
  switch (view.phase) {
    case "gathering":
      screen = (
        <GatheringPhase
          view={view}
          playerId={playerId}
          busy={busy}
          onReady={() => act(() => keywordsAction(sessionId, "ready", playerId))}
        />
      );
      break;
    case "roles":
      screen = (
        <RolePhase
          view={view}
          playerId={playerId}
          busy={busy}
          onGotIt={() => act(() => keywordsAction(sessionId, "role-seen", playerId))}
        />
      );
      break;
    case "speaking":
      screen = (
        <SpeakingPhase
          view={view}
          playerId={playerId}
          busy={busy}
          onSaid={() => act(() => keywordsAction(sessionId, "word-said", playerId))}
        />
      );
      break;
    case "voting":
      screen = (
        <VotingPhase
          view={view}
          playerId={playerId}
          busy={busy}
          onSubmit={(text) => act(() => keywordsSubmit(sessionId, playerId, text))}
        />
      );
      break;
    case "reveal":
      screen = <RevealPhase view={view} playerId={playerId} />;
      break;
  }

  // Every phase after gathering shows the group's name, unless there's only one group.
  const showGroupTag = !view.single_group && view.phase !== "gathering";

  /*
   * The color class sets --group-color for every screen, so the group's color is always visible.
   * A single group needs no color or name: everyone is already together.
   */
  const colorClass = view.single_group ? "" : ` keywords--${view.group_color.toLowerCase()}`;

  return (
    <main className={`keywords${colorClass}`}>
      {showGroupTag && <p className="keywords__group-tag">{view.group_label} Group</p>}
      {screen}

      {(actionError || socketError) && (
        <p role="alert" className="keywords__error">
          {actionError || socketError}
        </p>
      )}

      <p className="keywords__status">Connection: {connectionStatus}</p>
      <Link to="/" className="keywords__leave">Leave game</Link>
    </main>
  );
}
