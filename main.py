import asyncio
import time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import uvicorn
import logging

from simulation import Simulation
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Emergent City - API")

# Mount dynamic frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

sim = Simulation()
sim.setup()

is_running = False
is_loading = False

@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")

@app.post("/api/toggle")
def toggle_simulation():
    global is_running
    is_running = not is_running
    return {"running": is_running}

from pydantic import BaseModel
class CityRequest(BaseModel):
    city: str

@app.post("/api/change-city")
async def change_city_endpoint(req: CityRequest):
    global is_loading, is_running
    if req.city in config.CITIES:
        is_loading = True
        is_running = False # Force pause the simulation when changing cities
        try:
            # Run in a threadpool so we don't block the FastAPI event loop completely
            # while OSMnx downloads and processes the graph.
            await asyncio.to_thread(sim.change_city, req.city)
        except Exception as e:
            logger.error(f"Failed to load city {req.city}: {e}")
        finally:
            is_loading = False
        return {"success": True, "city": req.city}
    return {"success": False, "error": "City not found"}

@app.post("/api/rain")
def api_make_it_rain():
    sim.make_it_rain()
    return {"success": True, "message": "It's raining money!"}

@app.post("/api/jam")
def api_spawn_traffic_jam():
    sim.spawn_traffic_jam()
    return {"success": True, "message": "Traffic jam spawned!"}

@app.post("/api/smite/{agent_id}")
def api_smite_agent(agent_id: str):
    success = sim.smite_agent(agent_id)
    return {"success": success}

@app.get("/api/state")
def get_state():
    summary = sim.get_state_summary()
    
    # Get nodes coordinates for frontend
    agents_data = []
    for agent in sim.agents:
        lat, lon = 0.0, 0.0
        target_lat, target_lon = None, None
        
        if agent.location_node in sim.world.graph.nodes:
            node_data = sim.world.graph.nodes[agent.location_node]
            lat = node_data['y']
            lon = node_data['x']
            
        if agent.target_node and agent.target_node in sim.world.graph.nodes:
            t_node_data = sim.world.graph.nodes[agent.target_node]
            target_lat = t_node_data['y']
            target_lon = t_node_data['x']
            
        path_coords = []
        for p in agent.path:
            p_node_data = sim.world.graph.nodes[p]
            path_coords.append((p_node_data['y'], p_node_data['x']))

        agents_data.append({
            "id": agent.id,
            "role": agent.role,
            "wallet": agent.wallet,
            "lat": lat,
            "lon": lon,
            "target_lat": target_lat,
            "target_lon": target_lon,
            "action": agent.last_action,
            "path": path_coords
        })
        
    # Get city center
    center_lat, center_lon = 0, 0
    if sim.world.nodes:
        lats = [sim.world.graph.nodes[n]['y'] for n in sim.world.nodes]
        lons = [sim.world.graph.nodes[n]['x'] for n in sim.world.nodes]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)

    return {
        "running": is_running,
        "loading": is_loading,
        "summary": summary,
        "agents": agents_data,
        "center": {"lat": center_lat, "lon": center_lon}
    }

async def simulation_loop():
    global is_running, is_loading
    logger.info("Starting simulation background task")
    while True:
        if is_running and not is_loading:
            try:
                 await sim.tick()
            except Exception as e:
                logger.error(f"Error in simulation tick: {e}")
        await asyncio.sleep(config.TICK_INTERVAL)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
