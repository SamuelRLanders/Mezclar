import type { KeywordsPlayerView } from "../../api/client";

/*
 * A small reminder at the top of the speaking and voting screens, so players
 * never have to remember their role: non-fakers see the keyword, and the faker
 * sees that they're the faker.
 */
export default function RoleReminder({ view }: { view: KeywordsPlayerView }) {
  return (
    <p className="keywords__reminder">
      {view.is_faker ? (
        <>You're the <strong>faker</strong></>
      ) : (
        <>Keyword: <strong>{view.keyword}</strong></>
      )}
    </p>
  );
}
