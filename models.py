from dataclasses import dataclass
from typing import List

@dataclass
class DeliveryNode:       # Điểm giao
    id: int               # 0 là Kho (Depot), >0 là khách hàng
    address: str          # Kinh độ,Vĩ độ
    demand: float         # Khối lượng (kg)
    ready_time: float     # Thời gian giao sớm nhất (phút) 
    due_date: float       # Thời gian giao trễ nhất (phút) 
    service_time: float   # Thời gian bốc hàng (phút)

class FleetConfiguration: # Thông số xe
    def __init__(self, total_vehicles: int, max_capacity: float):
        self.total_vehicles = total_vehicles
        self.max_capacity = max_capacity

class RouteKPI:
    routes: List[List[int]]
    total_distance_km: float
    total_time_hours: float
    total_vehicles: int
    total_cost: float