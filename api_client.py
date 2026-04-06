import requests
import numpy as np
from typing import List, Tuple

class OpenRouteServiceClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.endpoint_url = "https://api.openrouteservice.org/v2/matrix/driving-car"
    
    def fetch_matrices(self, nodes: List) -> Tuple[np.ndarray, np.ndarray]:
        num_nodes = len(nodes)
        locations = []
        for node in nodes:
            lat, lon = map(float, node.address.split(','))
            locations.append([lon, lat])
            
        headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json'
        }
        
        payload = {"locations": locations, "metrics": ["distance", "duration"], "units": "m"}
        
        try:
            response = requests.post(self.endpoint_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return np.array(data['distances']), np.array(data['durations'])
        except Exception as e:
            print(f"LỖI MATRIX: {e}")
            return None, None