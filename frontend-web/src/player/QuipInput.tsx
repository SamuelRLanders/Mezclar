
import { useState } from "react";
import { submitAnswer } from "../api/client";

const MAX_QUIP_LENGTH = 200;

type QuipInputProps = {
  sessionId: string;
  playerId: string;
  currentRound: number;
  disabled: boolean;
};

export default function QuipInput({
  sessionId,
  playerId,
  currentRound,
  disabled,
}: QuipInputProps) {
  const [quip, setQuip] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [hasSubmitted, setHasSubmitted] = useState(false);

  const isValid = quip.trim().length > 0;

  function handleChange(value: string) {
    setQuip(value.slice(0, MAX_QUIP_LENGTH));
    setMessage("");
  }

  async function handleSubmit() {
    if (!isValid || isSubmitting || hasSubmitted || disabled) {
      return;
    }

    setIsSubmitting(true);
    setMessage("");

    try {
      await submitAnswer(sessionId, playerId, quip.trim(), currentRound);
      setHasSubmitted(true);
      setMessage("Your quip was submitted!");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not submit your quip. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section>
      <label htmlFor="quip-input">Your quip</label>

      <textarea
        id="quip-input"
        value={quip}
        onChange={(event) => handleChange(event.target.value)}
        maxLength={MAX_QUIP_LENGTH}
        rows={5}
        disabled={hasSubmitted || isSubmitting || disabled}
        placeholder="Type your funniest answer..."
        aria-describedby="quip-counter quip-validation"
        style={{
          display: "block",
          boxSizing: "border-box",
          width: "100%",
          marginTop: 8,
          padding: 12,
          border: "1px solid var(--border)",
          borderRadius: 8,
          font: "inherit",
          resize: "vertical",
        }}
      />

      <p id="quip-counter" style={{ textAlign: "right" }}>
        {quip.length}/{MAX_QUIP_LENGTH}
      </p>

      <p id="quip-validation" aria-live="polite">
        {message || (!isValid ? "Enter a quip before submitting." : "")}
      </p>

      <button
        type="button"
        onClick={handleSubmit}
        disabled={!isValid || isSubmitting || hasSubmitted || disabled}
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
