from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[
            str,
            dict[str, WebSocket],
        ] = defaultdict(dict)

    async def connect(
        self,
        session_id: str,
        player_id: str,
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()

        self.active_connections[session_id][player_id] = websocket

    def disconnect(
        self,
        session_id: str,
        player_id: str,
    ) -> None:
        session_connections = self.active_connections.get(session_id)

        if not session_connections:
            return

        session_connections.pop(player_id, None)

        if not session_connections:
            self.active_connections.pop(session_id, None)

    async def send_to_player(
        self,
        session_id: str,
        player_id: str,
        message: dict,
    ) -> None:
        websocket = self.active_connections.get(
            session_id,
            {},
        ).get(player_id)

        if websocket is None:
            return
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(session_id, player_id)

    async def broadcast_to_session(
        self,
        session_id: str,
        message: dict,
        exclude: str | None = None,
    ) -> None:
        connections = self.active_connections.get(
            session_id,
            {},
        )

        disconnected_players: list[str] = []

        for player_id, websocket in list(connections.items()):
            if player_id == exclude:
                continue

            try:
                await websocket.send_json(message)
            except Exception:
                disconnected_players.append(player_id)

        for player_id in disconnected_players:
            self.disconnect(session_id, player_id)

    async def disconnect_player(self, session_id: str, player_id: str, code: int = 4403) -> None:
        websocket = self.active_connections.get(session_id, {}).get(player_id)

        self.disconnect(session_id, player_id)

        if websocket is None:
            return

        try:
            await websocket.close(code=code)
        except Exception:
            pass

connection_manager = ConnectionManager()
