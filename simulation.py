import random
import asyncio
from world import World
from agents import UrbanAgent
from economy import Economy
from llm import decide_action, ActionResponse
import config

class Simulation:
    def __init__(self):
        self.world = World()
        self.economy = Economy(config.DEFAULT_TAX_RATE)
        self.agents = []
        self.tick_count = 0
        
    def setup(self):
        random.seed(config.RANDOM_SEED)
        self.world.load_city()
        self.setup_agents()
        
    def setup_agents(self):
        for i in range(config.NUM_RESIDENTS):
            node = self.world.get_random_node()
            self.agents.append(UrbanAgent(f"R{i}", "resident", node, 100.0))
            
        for i in range(config.NUM_SHOPS):
            node = self.world.get_random_node()
            self.agents.append(UrbanAgent(f"S{i}", "shop", node, 500.0))
            
        for i in range(config.NUM_DRIVERS):
            node = self.world.get_random_node()
            self.agents.append(UrbanAgent(f"D{i}", "driver", node, 50.0))

    def change_city(self, city_name):
        if city_name in config.CITIES:
            config.CITY_CENTER = config.CITIES[city_name]
            self.world.load_city()
            self.agents.clear()
            self.setup_agents()
            
    def get_state_summary(self):
        total_money = sum(a.wallet for a in self.agents) + self.economy.total_tax_collected
        avg_wallet = sum(a.wallet for a in self.agents) / len(self.agents) if self.agents else 0
        total_congestion = sum(self.world.congestion.values())
        return {
            "total_money": total_money,
            "avg_wallet": avg_wallet,
            "congestion": total_congestion,
            "tax_collected": self.economy.total_tax_collected
        }

    def make_it_rain(self):
        for agent in self.agents:
            agent.wallet += 1000.0

    def spawn_traffic_jam(self):
        # Find all active targets of drivers
        targets = [a.target_node for a in self.agents if a.role == "driver" and a.target_node]
        for t in targets:
            if t in self.world.nodes:
                self.world.congestion[t] = self.world.congestion.get(t, 0) + 100

    def smite_agent(self, agent_id: str):
        agent = next((a for a in self.agents if a.id == agent_id), None)
        if agent:
            agent.wallet = 0.0
            return True
        return False

    async def tick(self):
        self.tick_count += 1
        agent_paths = [a.path for a in self.agents if a.path]
        self.world.update_congestion(agent_paths)
        state_summary = self.get_state_summary()
        
        # Pick a larger subset of agents to make LLM decisions
        decision_makers = random.sample(self.agents, min(10, len(self.agents)))
        
        for agent in decision_makers:
            nearby = [a.id for a in self.agents if a.id != agent.id and a.location_node == agent.location_node]
            local_congestion = 0
            valid_nodes = random.sample(self.world.nodes, 3)
            
            try:
                decision = decide_action(
                    role=agent.role,
                    wallet=agent.wallet,
                    nearby_agents=nearby,
                    congestion=local_congestion,
                    last_action=agent.last_action,
                    economy_summary=f"Avg wallet: ${state_summary['avg_wallet']:.2f}",
                    valid_nodes=valid_nodes
                )
                
                if not isinstance(decision, ActionResponse):
                    decision = ActionResponse(action="idle", target="", amount=0)
                    
                agent.last_action = decision.action
                
                if decision.action == "move" and decision.target and agent.role != "shop":
                    try:
                        target_node = int(decision.target)
                        if target_node in self.world.nodes:
                            agent.target_node = target_node
                            agent.path = self.world.get_shortest_path(agent.location_node, target_node)
                    except ValueError:
                        target_agent = next((a for a in self.agents if a.id == decision.target), None)
                        if target_agent:
                            agent.target_node = target_agent.location_node
                            agent.path = self.world.get_shortest_path(agent.location_node, target_agent.location_node)
                            
                elif decision.action == "trade" and decision.target:
                    target_agent = next((a for a in self.agents if a.id == decision.target), None)
                    if target_agent and agent.location_node == target_agent.location_node:
                        self.economy.process_transaction(agent, target_agent, decision.amount)
                        
            except Exception as e:
                print(f"Agent {agent.id} decision failed: {e}")
                
        # Process movement & fuel
        for agent in self.agents:
            if agent.path:
                agent.move_step()
            if agent.role == "driver":
                self.economy.apply_driver_fuel_tax(agent, 0.5)
                
        # Fallback behaviors for agents not using LLM this tick
        for agent in self.agents:
            if agent not in decision_makers:
                if not agent.path and random.random() < 0.1 and agent.role != "shop":
                    target = self.world.get_random_node()
                    agent.path = self.world.get_shortest_path(agent.location_node, target)
                if agent.path:
                    agent.move_step()
                if agent.role == "resident" and random.random() < 0.2:
                    shops_here = [a for a in self.agents if a.role == "shop" and a.location_node == agent.location_node]
                    if shops_here:
                        self.economy.process_transaction(agent, random.choice(shops_here), 10.0)
