import numpy as np
import json
from models import DeliveryNode, FleetConfiguration
from solver import ClarkeWrightSolver

def run_system_mock_test():
    print("="*50)
    print(" KHỞI ĐỘNG HỆ THỐNG MÔ PHỎNG ĐỊNH TUYẾN GIAO HÀNG")
    print("="*50)
    
    print("\n[1/3] Đang nạp dữ liệu mạng lưới điểm giao")
    nodes = [
        DeliveryNode(id=0, address="106.7724,10.8507", demand=0, ready_time=0, due_date=1440, service_time=0),
        
        DeliveryNode(id=1, address="106.7621,10.8524", demand=20, ready_time=0, due_date=120, service_time=10),
        
        DeliveryNode(id=2, address="106.8028,10.8631", demand=30, ready_time=60, due_date=300, service_time=15),
        
        DeliveryNode(id=3, address="106.7999,10.8752", demand=25, ready_time=0, due_date=240, service_time=10),
        
        DeliveryNode(id=4, address="106.7589,10.8351", demand=15, ready_time=30, due_date=180, service_time=5)
    ]
    

    fleet = FleetConfiguration(total_vehicles=5, max_capacity=50.0) 
    print(f" Đã nạp 1 Kho trung tâm và {len(nodes)-1} điểm giao.")
    print(f" cấu hình: Ràng buộc sức chứa tối đa {fleet.max_capacity}kg/xe.")

    # GIẢ LẬP MA TRẬN API TRẢ VỀ TỪ OPENROUTESERVICE
    print("\n[2/3] Đang trích xuất ma trận khoảng cách & thời gian...")
    dist_matrix = np.array([
        [0,    1200, 3500, 4000, 2500],
        [1200, 0,    4200, 4800, 1800],
        [3500, 4200, 0,    1500, 5000],
        [4000, 4800, 1500, 0,    6000],
        [2500, 1800, 5000, 6000, 0   ]
    ], dtype=float)
    

    time_matrix = dist_matrix / 10.0
    print("Đã giả lập dữ liệu trả về từ OpenRouteService thành công")


    print("\n[3/3] Kích hoạt động cơ tối ưu hóa Clarke-Wright Savings")
    try:
        solver = ClarkeWrightSolver(nodes, fleet, dist_matrix, time_matrix)
        optimized_routes = solver.run_optimization()
        
        print("\n" + "="*50)
        print(" BÁO CÁO LỘ TRÌNH ĐÃ TỐI ƯU")
        print("="*50)
        

        for i, route in enumerate(optimized_routes):

            route_demand = sum([nodes[node_id].demand for node_id in route if node_id != 0])
            

            route_dist = sum([dist_matrix[route[idx]][route[idx+1]] for idx in range(len(route)-1)])
            
            print(f"Xe {i+1} | Tải trọng: {route_demand}/{fleet.max_capacity}kg | Cự ly: {route_dist/1000}km")
            

            route_str = " -> ".join([f"Khách {n}" if n != 0 else "Kho" for n in route])
            print(f"   Lộ trình: {route_str}\n")
            
    except Exception as e:
        print(f"\nLỗi thuật toán: {e}")


if __name__ == "__main__":
    run_system_mock_test()