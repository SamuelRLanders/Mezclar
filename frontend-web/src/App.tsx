import { Navigate, Route, Routes } from "react-router-dom";
import LandingPage from "./landing/LandingPage";
import About from "./landing/About";
import JoinScreen from "./player/JoinScreen";
import CreateGame from "./host/CreateGame";
import LobbyView from "./host/LobbyView";
import PlayerLobby from "./player/PlayerLobby";
import GameLanding from "./player/GameLanding";
import HostGameView from "./host/HostGameView";
import GameInSession from "./player/GameInSession";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/join/:code" element={<JoinScreen />} />
      <Route path="/player/:code" element={<PlayerLobby />} />
      <Route path="/player/:code/in-session" element={<GameInSession />} />
      <Route path="/player/:code/game" element={<GameLanding />} />
      <Route path="/host/new" element={<CreateGame />} />
      <Route path="/host/lobby/:code" element={<LobbyView />} />
      <Route path="/host/game/:code" element={<HostGameView />} />
      <Route path="/host/lobby" element={<LobbyView />} />
      <Route path="/about" element={<About />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
