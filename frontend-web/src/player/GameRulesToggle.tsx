import { useId, useState } from "react";
import GameRules from "./GameRules";
import "./GameRulesToggle.css";

export default function GameRulesToggle({ gameId }: { gameId: string | null }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <div className="game-rules-toggle">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? "Hide rules" : "View rules"}
      </button>
      <div id={panelId} hidden={!open}>
        {open && <GameRules key={gameId} gameId={gameId} />}
      </div>
    </div>
  );
}
