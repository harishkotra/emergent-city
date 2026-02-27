import osmnx as ox
import networkx as nx
import random
import config

class World:
    def __init__(self):
        self.graph = None
        self.nodes = []
        self.edges = []
        self.congestion = {}

    def load_city(self):
        self.graph = ox.graph_from_point(config.CITY_CENTER, dist=config.CITY_DIST, network_type='drive', simplify=True)
        self.nodes = list(self.graph.nodes())
        for u, v, key in self.graph.edges(keys=True):
            self.congestion[(u, v, key)] = 0
            
    def get_random_node(self):
        return random.choice(self.nodes)
        
    def get_shortest_path(self, source, target):
        try:
            return nx.shortest_path(self.graph, source, target, weight='length')
        except nx.NetworkXNoPath:
            return [source]
            
    def update_congestion(self, agent_paths):
        for k in self.congestion:
            self.congestion[k] = 0
        for path in agent_paths:
            if len(path) > 1:
                u, v = path[0], path[1]
                if self.graph.has_edge(u, v):
                    keys = list(self.graph[u][v].keys())
                    if keys:
                        self.congestion[(u, v, keys[0])] += 1
