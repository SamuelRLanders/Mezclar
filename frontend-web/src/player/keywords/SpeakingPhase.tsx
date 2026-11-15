import type { KeywordsPlayerView } from "../../api/client";
import RoleReminder from "./RoleReminder";

interface SpeakingPhaseProps {
  view: KeywordsPlayerView;
  playerId: string;
  busy: boolean;
  onSaid: () => void;
}

/*
 * Speaking (US 63): players take turns saying one word out loud, in a shuffled
 * order. Only the current speaker sees the "I said my word" button. The
 * instructions differ by role: non-fakers hunt for the faker, while the faker
 * tries to work out the keyword and blend in.
 */
export default function SpeakingPhase({ view, playerId, busy, onSaid }: SpeakingPhaseProps) {
  // Look up a player's display name from their ID.
  const nameOf = (id: string | null) =>
    view.members.find((member) => member.player_id === id)?.name ?? "the next player";

  const isMyTurn = view.current_speaker_id === playerId;
  const speakerName = nameOf(view.current_speaker_id);
  // Position of the current speaker, so earlier speakers can be marked as done.
  const currentPosition = view.speaking_order.indexOf(view.current_speaker_id ?? "");

  // What to tell this player depends on both their role and whose turn it is.
  let heading: string;
  let instruction: string;
  if (isMyTurn) {
    heading = "Your turn!";
    instruction = view.is_faker
      ? "Say one word out loud that you think is related to the keyword, so you blend in. Don't say your guess at the keyword itself!"
      : "Say one word out loud that's related to the keyword. Don't make it too obvious, or the faker might figure it out.";
  } else {
    heading = `Listen to ${speakerName}`;
    instruction = view.is_faker
      ? "Listen closely and try to figure out what the keyword is."
      : "Listen to every word. Who doesn't seem to know the keyword?";
  }

  return (
    <section className="keywords__card">
      <RoleReminder view={view} />

      <h1>{heading}</h1>
      <p>{instruction}</p>

      {isMyTurn && (
        <button type="button" className="keywords__button" disabled={busy} onClick={onSaid}>
          I said my word
        </button>
      )}

      <h2 className="keywords__subheading">Speaking order</h2>
      <ol className="keywords__order">
        {view.speaking_order.map((id, position) => {
          // Earlier speakers are done; the current speaker is highlighted.
          const status =
            position < currentPosition ? "done" : position === currentPosition ? "current" : "upcoming";
          return (
            <li key={id} className={`keywords__order-item keywords__order-item--${status}`}>
              {nameOf(id)}
              {id === playerId && " (you)"}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
