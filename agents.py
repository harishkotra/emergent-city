class UrbanAgent:
    def __init__(self, agent_id: str, role: str, location_node: int, wallet: float):
        self.id = agent_id
        self.role = role
        self.location_node = location_node
        self.wallet = wallet
        self.last_action = "idle"
        self.memory = []
        self.path = []
        self.target_node = None

    def move_step(self):
        if len(self.path) > 1:
            self.location_node = self.path[1]
            self.path = self.path[1:]
        elif len(self.path) == 1:
            self.location_node = self.path[0]
            self.path = []
