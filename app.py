import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from models import DeliveryNode, FleetConfiguration
from solver import ClarkeWrightSolver
from api_client import GoongServiceClient

GOONG_API_KEY = "Vysez1gwllfrmPx3NxZ1f4WF2OSPYUJaxnYtdFTF"

def parse_time(val, default_val): 
    if pd.isna(val) or str(val).strip() == "" or str(val).strip() == "NaT":
        return default_val
    try:
        if hasattr(val, 'hour') and hasattr(val, 'minute'):
            return val.hour * 60 + val.minute
        val_str = str(val).strip()
        if ":" in val_str:
            parts = val_str.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        return float(val)
    except:
        return default_val
    
def draw_route_map(nodes, optimized_routes, route_geometries):
    kho_lat, kho_lon = map(float, nodes[0].address.split(','))
    m = folium.Map(location=[kho_lat, kho_lon], zoom_start=13)
    for node in nodes:
        lat, lon = map(float, node.address.split(','))
        if node.id == 0:
            folium.Marker([lat, lon], popup="KHO TỔNG", icon=folium.Icon(color="red", icon="star")).add_to(m)
        else:
            folium.Marker([lat, lon], popup=f"Đơn {node.id} ({node.demand}kg)", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

    colors = ['blue', 'green', 'purple', 'orange', 'darkred']
    for idx, route_polyline in enumerate(route_geometries):
        folium.PolyLine(route_polyline, color=colors[idx % len(colors)], weight=4, opacity=0.8, tooltip=f"Tuyến xe {idx + 1}").add_to(m)
    return m

def is_coordinate(addr_str):
    try:
        parts = str(addr_str).split(',')
        if len(parts) == 2:
            float(parts[0].strip())
            float(parts[1].strip())
            return True
        return False
    except ValueError:
        return False

# === CÁC HÀM TÍNH TOÁN KPI ĐƯỢC ĐẶT TRỰC TIẾP Ở ĐÂY ===
def get_kpis(routes, dist_mat, time_mat):
    total_dist_m = 0
    total_time_sec = 0
    for r in routes:
        for k in range(len(r) - 1):
            total_dist_m += dist_mat[r[k]][r[k+1]]
            total_time_sec += time_mat[r[k]][r[k+1]]
    km = total_dist_m / 1000.0
    hours = total_time_sec / 3600.0 
    cost = (km / 100.0) * 10.0 * 24000.0  
    return km, cost, hours, len(routes)

def run_baseline(nodes, max_cap):
    routes = []
    current_route = [0]
    current_load = 0
    for i in range(1, len(nodes)):
        if current_load + nodes[i].demand > max_cap:
            current_route.append(0)
            routes.append(current_route)
            current_route = [0]
            current_load = 0
        current_route.append(i)
        current_load += nodes[i].demand
    if len(current_route) > 1:
        current_route.append(0)
        routes.append(current_route)
    return routes

def main():
    st.set_page_config(page_title="Hệ thống Tối ưu LMD", layout="wide")
    st.title("Hệ thống Tối ưu hóa Giao hàng Chặng cuối")
    
    st.sidebar.header("Cấu hình")
    max_cap = st.sidebar.number_input("Tải trọng tối đa/xe (kg)", value=100.0)
    btn_run = st.sidebar.button("BẮT ĐẦU TỐI ƯU")

    if 'is_optimized' not in st.session_state:
        st.session_state.is_optimized = False

    if btn_run:
        with st.spinner("Đang khởi tạo dữ liệu và gọi API Goong..."):
            client = GoongServiceClient(GOONG_API_KEY)
            nodes = [DeliveryNode(0, "10.8507, 106.7724", 0, 0, 1440, 0)] 
            try:
                df = pd.read_excel("data_hardcode.xlsx")
                for i, row in df.iterrows():
                    address_raw = str(row['Địa Chỉ'])
                    if not is_coordinate(address_raw):
                        coords = client.geocode(address_raw)
                        if coords: address_raw = coords 
                        else:
                            st.warning(f"Lỗi Geocode: Không tìm thấy tọa độ cho địa chỉ '{address_raw}'. Đang bỏ qua.")
                            continue 
                    ready_time = parse_time(row.get('Sớm Nhất'), 0)
                    due_date = parse_time(row.get('Trễ Nhất'), 1440)
                    nodes.append(DeliveryNode(id=i+1, address=address_raw, demand=float(row['Khối Lượng']), ready_time=ready_time, due_date=due_date, service_time=10.0))
            except Exception as e:
                st.error(f"LỖI ĐỌC FILE: {e}")
                return

            matrix_result = client.fetch_matrices(nodes)
            if matrix_result is not None and matrix_result[0] is not None:
                dist_mat, time_mat = matrix_result 
                fleet = FleetConfiguration(total_vehicles=5, max_capacity=max_cap)
                solver = ClarkeWrightSolver(nodes, fleet, dist_mat, time_mat)
                
                # --- CHẠY THUẬT TOÁN VÀ TÍNH TOÁN KPI ---
                result_routes = solver.run_optimization()
                baseline_routes = run_baseline(nodes, max_cap)
                
                opt_km, opt_cost, opt_hrs, opt_veh = get_kpis(result_routes, dist_mat, time_mat)
                base_km, base_cost, base_hrs, base_veh = get_kpis(baseline_routes, dist_mat, time_mat)
                
                st.session_state.opt_kpis = (opt_km, opt_cost, opt_hrs, opt_veh)
                st.session_state.base_kpis = (base_km, base_cost, base_hrs, base_veh)
                st.session_state.result_routes = result_routes
                st.session_state.nodes = nodes
                st.session_state.dist_mat = dist_mat

                route_geometries = []
                for route in result_routes:
                    full_route_coords = []
                    for k in range(len(route)-1):
                        origin = nodes[route[k]].address
                        destination = nodes[route[k+1]].address
                        segment_coords = client.fetch_route_geometry(origin, destination)
                        full_route_coords.extend(segment_coords)
                    route_geometries.append(full_route_coords)
                
                st.session_state.route_geometries = route_geometries
                st.session_state.is_optimized = True
            else:
                st.error("LỖI API Goong")

    # HIỂN THỊ
    if st.session_state.is_optimized:
        st.success("Tối ưu hóa thành công!")
        opt_km, opt_cost, opt_hrs, opt_veh = st.session_state.opt_kpis
        base_km, base_cost, base_hrs, base_veh = st.session_state.base_kpis

        st.subheader("📊 So sánh Hiệu suất Tối ưu (KPIs)")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1: st.metric("Tổng Quãng Đường", f"{opt_km:.1f} km", delta=f"-{base_km - opt_km:.1f} km so với gốc", delta_color="inverse")
        with kpi2: st.metric("Chi Phí Nhiên Liệu", f"{opt_cost:,.0f} đ", delta=f"-{base_cost - opt_cost:,.0f} đ", delta_color="inverse")
        with kpi3: st.metric("Tổng Thời Gian", f"{opt_hrs:.1f} giờ", delta=f"-{base_hrs - opt_hrs:.1f} giờ", delta_color="inverse")
        with kpi4: st.metric("Số Lượng Xe", f"{opt_veh} xe", delta=f"{opt_veh - base_veh} xe", delta_color="inverse")
            
        st.divider()
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("Báo cáo Lộ trình")
            for i, r in enumerate(st.session_state.result_routes):
                d = sum(st.session_state.dist_mat[r[k]][r[k+1]] for k in range(len(r)-1))
                st.markdown(f"**Tuyến {i+1}:** `{' -> '.join(['Kho' if n==0 else f'Đơn {n}' for n in r])}`")
                st.caption(f"{d/1000:.2f} km | {sum(st.session_state.nodes[n].demand for n in r)} kg")
                
        with col2:
            st.subheader("Bản đồ Trực quan")
            map_obj = draw_route_map(st.session_state.nodes, st.session_state.result_routes, st.session_state.route_geometries)
            st_folium(map_obj, width=700, height=500, returned_objects=[])

if __name__ == "__main__":
    main()