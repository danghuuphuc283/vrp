import requests
import time
import numpy as np
import polyline
from typing import List, Tuple

class GoongServiceClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://rsapi.goong.io"
    
    # 1. API GEOCODE: Chuyển địa chỉ text thành tọa độ Lat, Lng
    def geocode(self, address: str) -> str:
        url = f"{self.base_url}/Geocode"
        params = {
            "address": address,
            "api_key": self.api_key
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get('results'):
                location = data['results'][0]['geometry']['location']
                return f"{location['lat']},{location['lng']}"
            return None
        except Exception as e:
            print(f"LỖI GEOCODE ({address}): {e}")
            return None

    # 2. API DISTANCE MATRIX: Lấy ma trận khoảng cách & thời gian cho Thuật toán Clarke-Wright
    def fetch_matrices(self, nodes: List) -> Tuple[np.ndarray, np.ndarray]:
        url = f"{self.base_url}/DistanceMatrix"
        num_nodes = len(nodes)
        
        dist_mat = np.zeros((num_nodes, num_nodes))
        time_mat = np.zeros((num_nodes, num_nodes))
        
        # Gom tất cả tọa độ làm đích đến chung (Destinations)
        destinations_str = "|".join([node.address.replace(" ", "") for node in nodes])
        
        for i in range(num_nodes):
            origin_str = nodes[i].address.replace(" ", "")
            
            params = {
                "origins": origin_str,
                "destinations": destinations_str,
                "vehicle": "car", # Đổi sang 'car' để tránh lỗi đường cấm tải
                "api_key": self.api_key
            }
            
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                rows = data.get('rows', [])
                if not rows:
                    continue
                    
                elements = rows[0].get('elements', [])
                for j in range(num_nodes):
                    if j < len(elements) and elements[j]['status'] == 'OK':
                        dist_mat[i][j] = elements[j]['distance']['value']
                        time_mat[i][j] = elements[j]['duration']['value']
                    else:
                        dist_mat[i][j] = 999999 # Phạt vô cực nếu không có đường đi
                        time_mat[i][j] = 999999
                        
                # Delay nghỉ nhịp 0.2s để tránh bị Goong chặn API do request quá nhanh (Lỗi 429)
                time.sleep(0.2)
                
            except Exception as e:
                print(f"LỖI MATRIX (Tại điểm gốc thứ {i}): {e}")
                return None, None
        return dist_mat, time_mat
    # 3. API DIRECTION: Lấy đường đi chi tiết để vẽ map (đưa cho Tâm)
    def fetch_route_geometry(self, origin_coords: str, dest_coords: str) -> List[List[float]]:
        url = f"{self.base_url}/Direction"
        params = {
            "origin": origin_coords.replace(" ", ""),
            "destination": dest_coords.replace(" ", ""),
            "vehicle": "truck",
            "api_key": self.api_key
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('routes'):
                # Lấy chuỗi polyline mã hóa từ Goong
                encoded_polyline = data['routes'][0]['overview_polyline']['points']
                # Dùng thư viện polyline để giải mã thành danh sách [lat, lng]
                decoded_coords = polyline.decode(encoded_polyline)
                # polyline.decode trả về tuple, ta cast sang list để xài cho Folium
                return [list(coord) for coord in decoded_coords]
            return []
        except Exception as e:
            print(f"LỖI DIRECTION: {e}")
            return []
