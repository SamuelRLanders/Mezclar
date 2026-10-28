import { useEffect, useState } from "react";

export default function useRoundTimer(seconds: number, paused: boolean, round: number) {
  const [remaining, setRemaining] = useState(seconds);

  useEffect(() => {
    setRemaining(seconds);
    if (paused || seconds <= 0) return;

    const startedAt = performance.now();
    const intervalId = window.setInterval(() => {
      setRemaining(Math.max(0, seconds - (performance.now() - startedAt) / 1000));
    }, 250);
    return () => window.clearInterval(intervalId);
  }, [seconds, paused, round]);

  return Math.ceil(remaining);
}
