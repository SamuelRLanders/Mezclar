import type { KeywordsPlayerView } from "../../api/client";

interface GatheringPhaseProps {
  view: KeywordsPlayerView;
  playerId: string;
  busy: boolean;
  onReady: () => void;
}

/*
 * Gathering (US 61): the screen is filled with the group's color so players can
 * hold up their phones and find matching screens. Each player taps "I'm with my
 * group" once they've found everyone; the group moves on when all have tapped.
 */
export default function GatheringPhase({ view, playerId, busy, onReady }: GatheringPhaseProps) {
  const isReady = view.ready_player_ids.includes(playerId);
  // Everyone else in the group; the player doesn't need to look for themselves.
  const teammates = view.members.filter((member) => member.player_id !== playerId);

  return (
    <section className="keywords__card keywords__card--filled">
      <p className="keywords__eyebrow">Find your group</p>
      <h1 className="keywords__group-label">{view.group_label} Group</h1>
      <p>
        Hold up your phone and look for other {view.group_label} screens.
      </p>

      <h2 className="keywords__subheading">Your group</h2>
      <ul className="keywords__members">
        {teammates.map((member) => {
          const memberReady = view.ready_player_ids.includes(member.player_id);
          return (
            <li key={member.player_id}>
              <span>{member.name}</span>
              {/* A check shows who has already found the group. */}
              <span aria-label={memberReady ? "ready" : "not ready"}>{memberReady ? "✓" : "…"}</span>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        className="keywords__button"
        disabled={isReady || busy}
        onClick={onReady}
      >
        {isReady ? "Waiting for your group..." : "I'm with my group"}
      </button>

      {/* aria-live announces the count to screen readers as teammates ready up. */}
      <p className="keywords__progress" aria-live="polite">
        {view.ready_player_ids.length}/{view.members.length} ready
      </p>
    </section>
  );
}
