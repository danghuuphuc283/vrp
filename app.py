import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from models import DeliveryNode, FleetConfiguration
from solver import ClarkeWrightSolver
from api_client import GoongServiceClient

#HIỆN TẠI XÀI ORS ĐỂ TÍNH KHOẢNG CÁCH, SẼ THAY THẾ BẰNG GOONG MAPS
GOONG_API_KEY = "Vysez1gwllfrmPx3NxZ1f4WF2OSPYUJaxnYtdFTF"

def parse_time(val, default_val): # ĐỌC THỜI GIAN, ĐỂ TRỐNG THÌ MẶC ĐỊNH 0 (00:00) VÀ 1440 (24:00)
    if pd.isna(val) or str(val).strip() == "" or str(val).strip() == "NaT":
        return default_val
    try:
        if hasattr(val, 'hour') and hasattr(val, 'minute'):
            return val.hour * 60 + val.minute
        val_str = str(val).strip()
        if ":" in val_str:
            parts = val_str.split(":")
            h = int(parts[0])
            m = int(parts[1])
            return h * 60 + m
        else:
            return float(val)
    except Exception as e:
        print(f"LỖI ĐỌC GIỜ: {val}")
        return default_val
    
# VẼ TẠM, TÂM SỬA LẠI CHO HỢP GIAO DIỆN
def draw_route_map(nodes, optimized_routes, route_geometries):
    kho_lat, kho_lon = map(float, nodes[0].address.split(','))
    # Bản đồ mặc định của Folium là OpenStreetMap. Tâm có thể custom tileset của Goong ở đây nếu cần.
    m = folium.Map(location=[kho_lat, kho_lon], zoom_start=13)

    # CHẤM ĐIỂM (Không đổi)
    for node in nodes:
        lat, lon = map(float, node.address.split(','))
        if node.id == 0:
            folium.Marker([lat, lon], popup="KHO TỔNG", icon=folium.Icon(color="red", icon="star")).add_to(m)
        else:
            folium.Marker([lat, lon], popup=f"Đơn {node.id} ({node.demand}kg)", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

    # VẼ ĐƯỜNG: Thay vì vẽ đường chim bay bằng tọa độ nodes, Tâm sẽ dùng route_geometries do Backend (Phúc) truyền sang
    colors = ['blue', 'green', 'purple', 'orange', 'darkred']
    for route_idx, route_polyline in enumerate(route_geometries):
        folium.PolyLine(
            route_polyline, 
            color=colors[route_idx % len(colors)], 
            weight=4, 
            opacity=0.8, 
            tooltip=f"Tuyến xe {route_idx + 1}"
        ).add_to(m)

    return m

def is_coordinate(addr_str):
    """Kiểm tra xem chuỗi có đúng chuẩn 'Lat, Lng' là các con số hay không"""
    try:
        parts = str(addr_str).split(',')
        if len(parts) == 2:
            float(parts[0].strip())
            float(parts[1].strip())
            return True
        return False
    except ValueError:
        return False
    
def main():
    st.set_page_config(page_title="Hệ thống Tối ưu LMD", layout="wide")
    st.title("Hệ thống Tối ưu hóa Giao hàng Chặng cuối")
    
    st.sidebar.header("Cấu hình")
    max_cap = st.sidebar.number_input("Tải trọng tối đa/xe (kg)", value=100.0)
    btn_run = st.sidebar.button("BẮT ĐẦU TỐI ƯU")

    if 'is_optimized' not in st.session_state:
        st.session_state.is_optimized = False
    if btn_run:
        with st.spinner("Đang khởi tạo dữ liệu và gọi API Goong"):
            client = GoongServiceClient(GOONG_API_KEY)

            # NẠP DỮ LIỆU TỪ FILE EXCEL & GEOCODING
            nodes = [DeliveryNode(0, "10.8507, 106.7724", 0, 0, 1440, 0)] # Kho
            try:
                df = pd.read_excel("data_hardcode.xlsx")
                for i, row in df.iterrows():
                    address_raw = str(row['Địa Chỉ'])
                    
                    # KIỂM TRA CHẶT CHẼ: Nếu không phải tọa độ số thì bắt buộc gọi Geocode
                    if not is_coordinate(address_raw):
                        coords = client.geocode(address_raw)
                        if coords:
                            address_raw = coords # Cập nhật thành tọa độ "Lat, Lng"
                        else:
                            st.warning(f"Lỗi Geocode: Không tìm thấy tọa độ cho địa chỉ '{address_raw}'. Đang bỏ qua đơn hàng này.")
                            continue # Bỏ qua điểm này để không làm chết API Matrix

                    ready_time = parse_time(row.get('Sớm Nhất'), 0)
                    due_date = parse_time(row.get('Trễ Nhất'), 1440)
                    
                    nodes.append(DeliveryNode(
                        id=i+1, 
                        address=address_raw, 
                        demand=float(row['Khối Lượng']), 
                        ready_time=ready_time, 
                        due_date=due_date, 
                        service_time=10.0 
                    ))
            except Exception as e:
                st.error(f"LỖI ĐỌC FILE: {e}")
                return

            # CHẠY API ĐỂ LẤY MA TRẬN KHOẢNG CÁCH VÀ THỜI GIAN
            matrix_result = client.fetch_matrices(nodes)
            
            # Kiểm tra an toàn trước khi bóc tách (unpack) dữ liệu
            if matrix_result is not None and matrix_result[0] is not None:
                dist_mat, time_mat = matrix_result # Giải nén dữ liệu an toàn
                fleet = FleetConfiguration(total_vehicles=5, max_capacity=max_cap)
                solver = ClarkeWrightSolver(nodes, fleet, dist_mat, time_mat)
                
                result_routes = solver.run_optimization()
                st.session_state.result_routes = result_routes
                st.session_state.nodes = nodes
                st.session_state.dist_mat = dist_mat

                #Lấy geometry chi tiết cho từng tuyến để vẽ map
                route_geometries = []
                for route in result_routes:
                    full_route_coords = []
                    # Lặp qua từng chặng trong 1 tuyến (VD: 0 -> 2 -> 5 -> 0)
                    for k in range(len(route)-1):
                        origin = nodes[route[k]].address
                        destination = nodes[route[k+1]].address
                        # Gọi Direction API
                        segment_coords = client.fetch_route_geometry(origin, destination)
                        full_route_coords.extend(segment_coords)
                    route_geometries.append(full_route_coords)
                
                st.session_state.route_geometries = route_geometries
                st.session_state.is_optimized = True
            else:
                st.error("LỖI API Goong")
            

    # HIỂN THỊ
    if st.session_state.is_optimized:
        st.success("Tối ưu hóa thành công")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Báo cáo Lộ trình")
            total_km = 0
            for i, r in enumerate(st.session_state.result_routes):
                d = sum(st.session_state.dist_mat[r[k]][r[k+1]] for k in range(len(r)-1))
                total_km += d
                
                st.markdown(f"**Tuyến {i+1}:** `{' -> '.join(['Kho' if n==0 else f'Đơn {n}' for n in r])}`")
                st.caption(f"{d/1000:.2f} km | {sum(st.session_state.nodes[n].demand for n in r)} kg")
                
            st.info(f"**TỔNG QUÃNG ĐƯỜNG: {total_km/1000:.2f} km**")

        with col2:
            st.subheader("Bản đồ Trực quan")
            # Truyền mảng tọa độ đã giải mã cho hàm vẽ của Tâm
            map_obj = draw_route_map(
                st.session_state.nodes, 
                st.session_state.result_routes,
                st.session_state.route_geometries
            )
            st_folium(map_obj, width=700, height=500, returned_objects=[])

if __name__ == "__main__":
    main()