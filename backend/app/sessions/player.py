class Player:
    def __init__(self, player_id: str, name: str, device_token: str | None = None):
        self.player_id = player_id
        self.name = name
        self.ready = False
        self.hidden: bool = False
        self.is_mod: bool = False
        self.device_token = device_token
