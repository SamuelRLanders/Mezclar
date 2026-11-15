import type { KeywordsPlayerView } from "../../api/client";

interface RevealPhaseProps {
  view: KeywordsPlayerView;
  playerId: string;
}

/*
 * Reveal (US 65): the end of the group's game. Shows who won, who the faker
 * was, what the keyword was, what the faker guessed, and how everyone voted.
 * There are no buttons; the game ends on this screen.
 */
export default function RevealPhase({ view, playerId }: RevealPhaseProps) {
  const result = view.result;

  // The backend always includes the result in this phase; this only guards a bad message.
  if (!result) {
    return (
      <section className="keywords__card">
        <h1>Revealing results...</h1>
      </section>
    );
  }

  // Look up a player's display name from their ID.
  const nameOf = (id: string) =>
    view.members.find((member) => member.player_id === id)?.name ?? "Unknown player";

  const iWasFaker = result.faker_id === playerId;
  const fakerWon = result.winner === "faker";

  // A personal line on top, from this player's point of view.
  let personal: string;
  if (iWasFaker) {
    personal = fakerWon ? "You were the faker, and you won!" : "You were the faker, and they caught you.";
  } else {
    personal = fakerWon ? "The faker beat your group this time." : "Your group caught the faker!";
  }

  // Why the game ended the way it did.
  let reason: string;
  if (!result.faker_caught) {
    reason = `${result.faker_name} wasn't caught.`;
  } else if (result.faker_guessed_keyword) {
    reason = `${result.faker_name} was caught, but guessed the keyword.`;
  } else {
    reason = `${result.faker_name} was caught and didn't guess the keyword.`;
  }

  // Most-voted players first.
  const voteRows = Object.entries(result.vote_counts).sort(([, a], [, b]) => b - a);

  return (
    <section className="keywords__card">
      <p className="keywords__eyebrow">{personal}</p>
      <h1 className="keywords__role">{fakerWon ? "The faker wins!" : "Players win!"}</h1>
      <p>{reason}</p>

      <dl className="keywords__details">
        <dt>The faker</dt>
        <dd>{result.faker_name}</dd>

        <dt>The keyword</dt>
        <dd>{result.keyword}</dd>

        <dt>The faker's guess</dt>
        <dd>
          {result.faker_guess ?? "No guess"}{" "}
          <span aria-label={result.faker_guessed_keyword ? "correct" : "incorrect"}>
            {result.faker_guessed_keyword ? "✓" : "✗"}
          </span>
        </dd>
      </dl>

      <h2 className="keywords__subheading">Votes</h2>
      <ul className="keywords__members">
        {voteRows.map(([id, count]) => (
          <li key={id}>
            <span>
              {nameOf(id)}
              {id === result.faker_id && " (faker)"}
              {id === playerId && " (you)"}
            </span>
            <span>{count} {count === 1 ? "vote" : "votes"}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
