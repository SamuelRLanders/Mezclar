import { useState } from "react";
import { getSession, submitAnswer } from "../api/client";
import "./QuipInput.css";

const MAX_QUIP_LENGTH = 200;

type QuipInputProps = {
  sessionId: string;
  playerId: string;
  currentRound: number;
  acceptedAnswer?: string;
};

export default function QuipInput({
  sessionId,
  playerId,
  currentRound,
  acceptedAnswer,
}: QuipInputProps) {
  const [quip, setQuip] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const hasSubmitted = submitted || acceptedAnswer !== undefined;
  const answer = acceptedAnswer ?? quip;

  const isValid = quip.trim().length > 0;

  function handleChange(value: string) {
    setQuip(value.slice(0, MAX_QUIP_LENGTH));
    setMessage("");
  }

  async function handleSubmit() {
    if (!isValid || isSubmitting || hasSubmitted) {
      return;
    }

    setIsSubmitting(true);
    setMessage("");

    try {
      await submitAnswer(sessionId, playerId, quip.trim());
      setSubmitted(true);
    } catch (error) {
      const session = await getSession(sessionId).catch(() => null);
      const received = session?.current_round === currentRound
        && session.submitted_player_ids.includes(playerId);
      if (received) {
        setSubmitted(true);
      } else {
        setMessage(
          error instanceof Error
            ? error.message
            : "Could not submit your quip. Please try again.",
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="quip-input">
      <label className="quip-input__label" htmlFor="quip-input">
        Your quip
      </label>

      <textarea
        className="quip-input__textarea"
        id="quip-input"
        value={answer}
        onChange={(event) => handleChange(event.target.value)}
        maxLength={MAX_QUIP_LENGTH}
        rows={5}
        disabled={hasSubmitted || isSubmitting}
        placeholder="Type your funniest answer..."
        aria-describedby="quip-counter quip-validation"
      />

      <div className="quip-input__meta">
        <p className="quip-input__counter" id="quip-counter">
          {answer.length}/{MAX_QUIP_LENGTH}
        </p>
      </div>

      <p
        className={`quip-input__message ${
          message && !hasSubmitted ? "quip-input__message--error" : ""
        }`}
        id="quip-validation"
        aria-live="polite"
      >
        {hasSubmitted ? "Response received" : message || (!isValid ? "Enter a quip before submitting." : "")}
      </p>

      <button
        type="button"
        className="quip-input__submit"
        onClick={handleSubmit}
        disabled={!isValid || isSubmitting || hasSubmitted}
      >
        {isSubmitting
          ? "Submitting..."
          : hasSubmitted
            ? "Submitted"
            : "Submit quip"}
      </button>
    </section>
  );
}
