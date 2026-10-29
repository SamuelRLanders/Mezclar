import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GAMES, formatPlayerRange, formatTimeRange } from "./games";
import GameSelect from "./GameSelect";
import {
  GAME_OPTIONS,
  defaultOptionValues,
  type GameOptionValues,
} from "./gameOptions";
import {
  activeFilterCount,
  emptyFilters,
  filterGames,
  type GameFilters,
} from "./gameFilters";
import GameFilterPopover from "./GameFilterPopover";
import "./CreateGame.css";

export default function CreateGame() {
  const navigate = useNavigate();
  const [hostName, setHostName] = useState("");
  const [gameId, setGameId] = useState("");
  const [rounds, setRounds] = useState(3);
  const [options, setOptions] = useState<GameOptionValues>(defaultOptionValues);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<GameFilters>(emptyFilters);
  const [password, setPassword] = useState("");

  const passwordRequired = options["requiresPassword"] ?? false;

  // Looked up against the full catalog, not the filtered list: filtering is a
  // way to find a game, and must not disturb one that's already chosen.
  const selectedGame = GAMES.find((game) => game.id === gameId);
  const visibleGames = filterGames(GAMES, filters);
  const filtersActive = activeFilterCount(filters) > 0;

  function setOption(id: string, value: boolean) {
    setOptions((previous) => ({ ...previous, [id]: value }));
  }

  async function handleStart() {
    if (!selectedGame || !hostName.trim() || isCreating) return;

    setIsCreating(true);
    setError("");
  
    if (passwordRequired && !password.trim()) {
      setError("Please enter a password for the game.");
      return;
    }

    try {
      
      const response = await fetch("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host_name: hostName.trim(),
          settings: {
            gameId: selectedGame.id,
            options,
            ...(selectedGame.id === "quiplash" ? { rounds } : {}),
          },
          password: password.trim() || null
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const data: { session_id: string } = await response.json();

      navigate("/host/lobby/" + data.session_id, {
        state: {
          sessionId: data.session_id,
          gameId: selectedGame.id,
          options,
          password: password.trim() || null
        },
      });

    } catch (error) {

      console.error("Failed to create session:", error);
      setError("Unable to create a game session. Please try again.");

    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="create">
      <div className="create__inner">
        <button className="create__back" type="button" onClick={() => navigate("/")}>
          &larr; Back
        </button>

        <header className="create__header">
          <h1 className="create__title">Host a game</h1>
          <p className="create__lede">
            Pick a game and set your options. You&rsquo;ll get a join code to share
            on the next screen, and players can join right up until you start.
          </p>
        </header>

        <section className="create__section" aria-labelledby="host-heading">
          <h2 className="create__heading" id="host-heading">Your name</h2>
          <input
            className="create__name"
            value={hostName}
            onChange={(event) => setHostName(event.target.value)}
            placeholder="Host name"
            maxLength={40}
            autoComplete="name"
          />
        </section>

        <section className="create__section" aria-labelledby="game-heading">
          <div className="create__heading-row">
            <h2 className="create__heading" id="game-heading">
              Choose a game
            </h2>
            <div className="create__heading-tools">
              {/* Always mounted — a live region inserted alongside its first
                  message tends not to get announced. */}
              <span className="create__count" aria-live="polite">
                {filtersActive
                  ? `${visibleGames.length} of ${GAMES.length} games`
                  : ""}
              </span>
              <GameFilterPopover filters={filters} onApply={setFilters} />
            </div>
          </div>

          <GameSelect
            games={visibleGames}
            value={gameId}
            onChange={setGameId}
            describedBy={selectedGame ? "game-detail" : undefined}
          />

          {selectedGame ? (
            <div className="create__detail" id="game-detail">
              <div className="create__detail-name">{selectedGame.name}</div>
              <div className="create__meta">
                <span className="create__tag">{formatPlayerRange(selectedGame)}</span>
                <span className="create__tag">{formatTimeRange(selectedGame)}</span>
              </div>
              <p className="create__description">{selectedGame.description}</p>
            </div>
          ) : (
            <p className="create__empty">
              Select a game to see its player count, length, and description.
            </p>
          )}
        </section>

        <section className="create__section" aria-labelledby="options-heading">
          <h2 className="create__heading" id="options-heading">
            Game options
          </h2>

          <div className="create__options">
            {GAME_OPTIONS.map((option) => (
              <label className="option" key={option.id}>
                <span className="option__text">
                  <span className="option__label">{option.label}</span>
                  <span className="option__description">{option.description}</span>
                </span>
                <input
                  className="option__input"
                  type="checkbox"
                  checked={options[option.id] ?? option.defaultValue}
                  onChange={(event) => setOption(option.id, event.target.checked)}
                />
                <span className="option__switch" aria-hidden="true" />
              </label>
            ))}
            
            {passwordRequired && (
              <label className="option option--password">
                <span className="option__text">Room password</span>
                <input
                  type ="text"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter a password"
                  maxLength={50}
                  autoComplete = "new-password"
                  />
              </label>
            )}
          </div>
        </section>

        {selectedGame?.id === "quiplash" && (
          <section className="create__section" aria-labelledby="rounds-heading">
            <h2 className="create__heading" id="rounds-heading">
              Number of rounds
            </h2>

            <label htmlFor="rounds-select">
              Submission rounds
            </label>

            <select
              id="rounds-select"
              className="create__name"
              value={rounds}
              onChange={(event) => setRounds(Number(event.target.value))}
            >
              {[1, 2, 3, 4, 5].map((count) => (
                <option key={count} value={count}>
                  {count} {count === 1 ? "round" : "rounds"}
                </option>
              ))}
            </select>

            <p className="create__hint">
              Players will be regrouped between rounds.
            </p>
          </section>
        )}

        <div className="create__actions">
          {error && <p className="create__hint" role="alert">{error}</p>}
          <button
            className="create__start"
            type="button"
            onClick={handleStart}
            disabled={!selectedGame || !hostName.trim() || isCreating}
          >
            {isCreating ? "Creating..." : "Create lobby"}
          </button>
          {!selectedGame && (
            <p className="create__hint">Choose a game to continue.</p>
          )}
        </div>
      </div>
    </main>
  );
}
