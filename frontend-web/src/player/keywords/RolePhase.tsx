import { useState } from "react";

import type { KeywordsPlayerView } from "../../api/client";

interface RolePhaseProps {
  view: KeywordsPlayerView;
  playerId: string;
  busy: boolean;
  onGotIt: () => void;
}

/*
 * Roles (US 62): each player privately learns whether they know the keyword or
 * are the faker. The role starts covered so nobody nearby can read it, and each
 * player taps "Got it" once they understand their job; the group moves on to
 * speaking when everyone has.
 */
export default function RolePhase({ view, playerId, busy, onGotIt }: RolePhaseProps) {
  // The role stays covered until the player chooses to look. Resets on refresh, which is fine.
  const [revealed, setRevealed] = useState(false);
  const hasSeenRole = view.role_seen_player_ids.includes(playerId);

  // Covered: remind the player to keep it secret before they look.
  if (!revealed) {
    return (
      <section className="keywords__card">
        <p className="keywords__eyebrow">Your role is ready</p>
        <h1>Keep it secret</h1>
        <p>
          Make sure nobody can see your screen, and don't tell anyone what your role is.
        </p>
        <button type="button" className="keywords__button" onClick={() => setRevealed(true)}>
          Tap to see your role
        </button>
        <RoleProgress view={view} />
      </section>
    );
  }

  return (
    <section className="keywords__card">
      {view.is_faker ? (
        <>
          <p className="keywords__eyebrow">Your role</p>
          <h1 className="keywords__role">You're the faker</h1>
          <p>
            Everyone else in your group knows the secret keyword. <strong>You don't.</strong>
          </p>
          <p>
            To win, listen to the words the others say and figure out what the keyword is.
            Blend in so nobody suspects you.
          </p>
        </>
      ) : (
        <>
          <p className="keywords__eyebrow">The keyword is</p>
          <h1 className="keywords__role">{view.keyword}</h1>
          <p>
            Everyone in your group knows this word except <strong>one faker</strong>.
          </p>
          <p>
            To win, figure out who the faker is. Don't make the keyword too obvious,
            or the faker might guess it. Don't say it out loud!
          </p>
        </>
      )}

      <button
        type="button"
        className="keywords__button"
        disabled={hasSeenRole || busy}
        onClick={onGotIt}
      >
        {hasSeenRole ? "Waiting for your group..." : "Got it"}
      </button>
      <RoleProgress view={view} />
    </section>
  );
}

// How many players in the group have finished reading their role.
function RoleProgress({ view }: { view: KeywordsPlayerView }) {
  return (
    <p className="keywords__progress" aria-live="polite">
      {view.role_seen_player_ids.length}/{view.members.length} ready
    </p>
  );
}
