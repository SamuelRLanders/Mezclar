import { useState, type FormEvent } from "react";

import type { KeywordsPlayerView } from "../../api/client";
import RoleReminder from "./RoleReminder";

interface VotingPhaseProps {
  view: KeywordsPlayerView;
  playerId: string;
  busy: boolean;
  onSubmit: (text: string) => void;
}

// Matches MAX_ANSWER_LENGTH in the backend's game.py.
const MAX_ANSWER_LENGTH = 50;

/*
 * Voting (US 64): everyone types an answer. Non-fakers type the name of the
 * player they suspect; the faker types their guess at the keyword. Both use
 * the same layout and the same request, with role-specific wording.
 */
export default function VotingPhase({ view, playerId, busy, onSubmit }: VotingPhaseProps) {
  const [text, setText] = useState("");
  // Everyone else in the group, listed for non-fakers so they can spell names correctly.
  const suspects = view.members.filter((member) => member.player_id !== playerId);

  function handleSubmit(event: FormEvent) {
    // Stop the browser from reloading the page on form submit.
    event.preventDefault();
    if (text.trim()) onSubmit(text.trim());
  }

  // Once submitted, just wait for the rest of the group.
  if (view.has_submitted) {
    return (
      <section className="keywords__card">
        <RoleReminder view={view} />
        <h1>Answer locked in</h1>
        <p>Waiting for the rest of your group to answer.</p>
        <p className="keywords__progress" aria-live="polite">
          {view.submitted_count}/{view.members.length} answered
        </p>
      </section>
    );
  }

  return (
    <section className="keywords__card">
      <RoleReminder view={view} />

      {view.is_faker ? (
        <>
          <h1>Guess the keyword</h1>
          <p>
            Type the word you think everyone else was given. If you guess it right,
            you win, even if they catch you!
          </p>
        </>
      ) : (
        <>
          <h1>Who's the faker?</h1>
          <p>Type the name of the player you think is the faker.</p>
        </>
      )}

      <form onSubmit={handleSubmit}>
        <input
          className="keywords__input"
          value={text}
          onChange={(event) => setText(event.target.value)}
          maxLength={MAX_ANSWER_LENGTH}
          placeholder={view.is_faker ? "Your guess at the keyword" : "Player's name"}
          aria-label={view.is_faker ? "Your guess at the keyword" : "Name of the player you suspect"}
          autoComplete="off"
        />
        <button type="submit" className="keywords__button" disabled={busy || !text.trim()}>
          Lock in answer
        </button>
      </form>

      {/* Non-fakers get the list of names to choose from; the faker doesn't need it. */}
      {!view.is_faker && (
        <>
          <h2 className="keywords__subheading">Players in your group</h2>
          <ul className="keywords__members">
            {suspects.map((member) => (
              <li key={member.player_id}>{member.name}</li>
            ))}
          </ul>
        </>
      )}

      <p className="keywords__progress" aria-live="polite">
        {view.submitted_count}/{view.members.length} answered
      </p>
    </section>
  );
}
