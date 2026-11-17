import { useCallback, useEffect, useId, useRef, useState } from "react";
import "./ReadAloud.css";

const SETTING_KEY = "mezclar-read-aloud";

interface ReadAloudProps {
  text: string;
  contentKey?: string | number;
}

export default function ReadAloud({ text, contentKey }: ReadAloudProps) {
  const [enabled, setEnabled] = useState(() => {
    try {
      return localStorage.getItem(SETTING_KEY) === "true";
    } catch {
      return false;
    }
  });
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");
  const [storageError, setStorageError] = useState("");
  const utterance = useRef<SpeechSynthesisUtterance | null>(null);
  const helpId = useId();
  const supported = "speechSynthesis" in window
    && typeof window.SpeechSynthesisUtterance === "function";

  const stop = useCallback(() => {
    if (utterance.current) {
      utterance.current.onend = null;
      utterance.current.onerror = null;
      utterance.current = null;
      window.speechSynthesis.cancel();
    }
    setPlaying(false);
  }, []);

  // A new prompt or screen must never keep reading the previous instructions.
  useEffect(() => {
    setError("");
    stop();
    return stop;
  }, [text, contentKey, enabled, stop]);

  useEffect(() => {
    window.addEventListener("pagehide", stop);
    return () => window.removeEventListener("pagehide", stop);
  }, [stop]);

  function changeEnabled(value: boolean) {
    stop();
    setEnabled(value);
    setStorageError("");
    try {
      localStorage.setItem(SETTING_KEY, String(value));
    } catch {
      setStorageError("Your browser could not save this setting. It may reset after refresh.");
    }
  }

  function play() {
    if (!supported || !enabled || !text.trim()) return;
    stop();
    setError("");

    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = document.documentElement.lang || "en";
    speech.onend = () => {
      if (utterance.current !== speech) return;
      utterance.current = null;
      setPlaying(false);
    };
    speech.onerror = () => {
      if (utterance.current !== speech) return;
      utterance.current = null;
      setPlaying(false);
      setError("Read-aloud could not play. Check your browser's speech settings and try again.");
    };
    utterance.current = speech;
    setPlaying(true);
    try {
      window.speechSynthesis.speak(speech);
    } catch {
      stop();
      setError("Read-aloud could not play. Check your browser's speech settings and try again.");
    }
  }

  return (
    <fieldset className="read-aloud">
      <legend>Accessibility</legend>
      <label className="read-aloud__setting">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => changeEnabled(event.target.checked)}
          aria-describedby={helpId}
        />
        Enable read-aloud
      </label>
      <p id={helpId}>
        {supported
          ? "Play reads the current prompt and instructions. Audio stops when the screen changes."
          : "Read-aloud is unavailable in this browser. Try a browser with text-to-speech support."}
      </p>
      {enabled && supported && (
        <div className="read-aloud__controls">
          <button type="button" onClick={play} disabled={playing || !text.trim()}>
            Play read-aloud
          </button>
          <button type="button" onClick={stop} disabled={!playing}>
            Stop read-aloud
          </button>
        </div>
      )}
      <p role="status" className="read-aloud__status">
        {error || storageError || (playing ? "Reading aloud..." : "")}
      </p>
    </fieldset>
  );
}
