import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from models import DeliveryNode, FleetConfiguration
from solver import ClarkeWrightSolver
from api_client import OpenRouteServiceClient

#HIỆN TẠI XÀI ORS ĐỂ TÍNH KHOẢNG CÁCH, SẼ THAY THẾ BẰNG GOONG MAPS
ORS_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjNkODgwZDg5ZGI3MjQwZmQ4NTM3OWI3ZWIwNmU0NWFjIiwiaCI6Im11cm11cjY0In0="

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
    
# VẼ TẠM
def draw_route_map(nodes, optimized_routes):
    kho_lat, kho_lon = map(float, nodes[0].address.split(','))
    m = folium.Map(location=[kho_lat, kho_lon], zoom_start=13)

    # CHẤM ĐIỂM
    for node in nodes:
        lat, lon = map(float, node.address.split(','))
        if node.id == 0:
            folium.Marker([lat, lon], popup="KHO TỔNG", icon=folium.Icon(color="red", icon="star")).add_to(m)
        else:
            folium.Marker([lat, lon], popup=f"Đơn {node.id} ({node.demand}kg)", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

    # VẼ ĐƯỜNG
    colors = ['blue', 'green', 'purple', 'orange', 'darkred']
    for route_idx, route in enumerate(optimized_routes):
        route_coords = []
        for node_id in route:
            lat, lon = map(float, nodes[node_id].address.split(','))
            route_coords.append([lat, lon])
            
        folium.PolyLine(route_coords, color=colors[route_idx % len(colors)], weight=4, opacity=0.8, tooltip=f"Tuyến xe {route_idx + 1}").add_to(m)

    return m


def main():
    st.set_page_config(page_title="Hệ thống Tối ưu LMD", layout="wide")
    st.title("Hệ thống Tối ưu hóa Giao hàng Chặng cuối")
    
    st.sidebar.header("Cấu hình")
    max_cap = st.sidebar.number_input("Tải trọng tối đa/xe (kg)", value=100.0)
    btn_run = st.sidebar.button("BẮT ĐẦU TỐI ƯU")

    if 'is_optimized' not in st.session_state:
        st.session_state.is_optimized = False
    if btn_run:
        with st.spinner("Đang khởi tạo dữ liệu và gọi API ORS"):
            client = OpenRouteServiceClient(ORS_KEY)

            # NẠP DỮ LIỆU TỪ FILE EXCEL
            nodes = [DeliveryNode(0, "10.8507, 106.7724", 0, 0, 1440, 0)]
            try:
                df = pd.read_excel("data_hardcode.xlsx")
                for i, row in df.iterrows():
                    ready_time = parse_time(row.get('Sớm Nhất'), 0)
                    due_date = parse_time(row.get('Trễ Nhất'), 1440)
                    
                    # NẠP VÀO DANH SÁCH NODES
                    nodes.append(DeliveryNode(
                        id=i+1, 
                        address=str(row['Địa Chỉ']), 
                        demand=float(row['Khối Lượng']), 
                        ready_time=ready_time, 
                        due_date=due_date, 
                        service_time=10.0 #TIME BỐC HÀNG
                    ))
            except Exception as e:
                st.error(f"LỖI ĐỌC FILE: {e}")
                return

            # CHẠY API ĐỂ LẤY MA TRẬN KHOẢNG CÁCH VÀ THỜI GIAN
            dist_mat, time_mat = client.fetch_matrices(nodes)
            if dist_mat is not None:
                fleet = FleetConfiguration(total_vehicles=5, max_capacity=max_cap)
                solver = ClarkeWrightSolver(nodes, fleet, dist_mat, time_mat)
                
                st.session_state.result_routes = solver.run_optimization()
                st.session_state.nodes = nodes
                st.session_state.dist_mat = dist_mat
                st.session_state.is_optimized = True
            else:
                st.error("LỖI API ORS")

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
            # LẤY NODE VÀ TUYẾN ĐƯỜNG ĐỂ VẼ BẢN ĐỒ
            map_obj = draw_route_map(st.session_state.nodes, st.session_state.result_routes)
            st_folium(map_obj, width=700, height=500, returned_objects=[])

if __name__ == "__main__":
    main()