import numpy as np
from typing import List
from models import FleetConfiguration

class ClarkeWrightSolver:
    def __init__(self, nodes: List, fleet: 'FleetConfiguration', dist_matrix: np.ndarray, time_matrix: np.ndarray):
        self.nodes = nodes
        self.fleet = fleet
        self.dist_matrix = dist_matrix
        self.time_matrix = time_matrix / 60.0 # Quy đổi thời gian (giây) sang phút
        self.n_nodes = len(nodes)
        self.routes = [[0, i, 0] for i in range(1, self.n_nodes)]

    def _is_valid(self, route: List[int]) -> bool:
        if sum(self.nodes[n].demand for n in route) > self.fleet.max_capacity:
            return False

        current_time = 0.0 
        for i in range(len(route) - 1):
            curr_node = route[i]
            next_node = route[i+1]
            current_time += self.time_matrix[curr_node][next_node]
            waiting_time = 0.0

            if current_time < self.nodes[next_node].ready_time:
                waiting_time = self.nodes[next_node].ready_time - current_time
                current_time = self.nodes[next_node].ready_time

            if waiting_time > 60.0:  
                return False
            if current_time > self.nodes[next_node].due_date:
                return False
            current_time += self.nodes[next_node].service_time
        return True

    def run_optimization(self) -> List[List[int]]:
        savings = []
        for i in range(1, self.n_nodes):
            for j in range(1, self.n_nodes):
                if i != j:
                    val = self.dist_matrix[0][i] + self.dist_matrix[0][j] - self.dist_matrix[i][j]
                    if val > 0: savings.append((val, i, j))
        
        savings.sort(key=lambda x: x[0], reverse=True)

        for _, i, j in savings:
            r_i, r_j = -1, -1
            for idx, r in enumerate(self.routes):
                if r[-2] == i: r_i = idx
                if r[1] == j: r_j = idx
            
            if r_i != -1 and r_j != -1 and r_i != r_j:
                new_route = self.routes[r_i][:-1] + self.routes[r_j][1:]
                if self._is_valid(new_route):
                    self.routes[r_i] = new_route
                    self.routes.pop(r_j)
        return self.routes