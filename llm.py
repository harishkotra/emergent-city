import json
from pydantic import BaseModel
from agno.agent import Agent
from agno.models.ollama import Ollama
import config

class ActionResponse(BaseModel):
    action: str
    target: str
    amount: int

def get_llm_agent():
    try:
        return Agent(
            model=Ollama(id=config.OLLAMA_MODEL),
            description="You are an agent in a city simulation.",
            response_model=ActionResponse,
            temperature=0.2,
        )
    except Exception:
        return None

llm_agent = get_llm_agent()

def decide_action(role, wallet, nearby_agents, congestion, last_action, economy_summary, valid_nodes):
    if not llm_agent:
        return ActionResponse(action="idle", target="", amount=0)
        
    prompt = f"""
You are a {role} in a city.
Wallet: ${wallet:.2f}
Nearby agents: {nearby_agents}
Congestion level: {congestion}
Last action: {last_action}
Economy summary: {economy_summary}

Choose your next action.
Rules:
- action must be 'move', 'trade', or 'idle'
- target must be a node_id (if move) or agent_id (if trade).
- If moving, choose one of these valid nodes: {valid_nodes}
- amount must be 0-100 (if trade)
Respond in JSON format.
"""
    try:
        response = llm_agent.run(prompt)
        return response.data
    except Exception as e:
        return ActionResponse(action="idle", target="", amount=0)
