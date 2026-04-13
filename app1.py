import streamlit as st
import pandas as pd
import folium
import json
import os
from streamlit_folium import st_folium
from datetime import datetime

# Khởi tạo session state nếu chưa có
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = {'name': '', 'email': ''}

# --- IMPORT TỪ CÁC FILE MODULE CỦA BẠN ---
from models import DeliveryNode, FleetConfiguration
from solver import ClarkeWrightSolver
from api_client import GoongServiceClient

GOONG_API_KEY = "ki7BtvlEUGwc4tpa4U7qKkPfOuFv29AXnNBx7OUX" 
DB_FILE = 'users_db.json'

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Khởi tạo DB nếu người dùng vào thẳng trang chủ
if 'user_db' not in st.session_state:
    st.session_state['user_db'] = load_db()

# --- HÀM LOAD CSS ---
def load_local_css(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"Không tìm thấy file {file_name}")

# --- CÁC HÀM XỬ LÝ VÀ TÍNH TOÁN KPI ---
def parse_time(val, default_val):
    if pd.isna(val) or str(val).strip() == "" or str(val).strip() == "NaT": 
        return default_val
    try:
        if hasattr(val, 'hour') and hasattr(val, 'minute'): 
            return val.hour * 60 + val.minute
        if ":" in str(val):
            parts = str(val).split(":")
            return int(parts[0]) * 60 + int(parts[1])
        return float(val)
    except: 
        return default_val

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

def render_delta_badge(delta_val, format_str, unit, suffix=""):
    if delta_val == 0: return ""
    val_str = format_str.format(delta_val)
    if delta_val < 0:
        return f'<div style="font-size: 12px; font-weight: 500; display: inline-block; padding: 3px 8px; border-radius: 12px; margin-top: 5px; background-color: #e6f4ea; color: #1e8e3e;">↓ {val_str} {unit} {suffix}</div>'
    else:
        return f'<div style="font-size: 12px; font-weight: 500; display: inline-block; padding: 3px 8px; border-radius: 12px; margin-top: 5px; background-color: #fce8e6; color: #d93025;">↑ {val_str} {unit} {suffix}</div>'

# --- HÀM VẼ BẢN ĐỒ ---
def draw_route_map(nodes, route_geometries):
    kho_lat, kho_lon = map(float, nodes[0].address.split(','))
    m = folium.Map(location=[kho_lat, kho_lon], zoom_start=13)
    
    for node in nodes:
        lat, lon = map(float, node.address.split(','))
        if node.id == 0:
            folium.Marker([lat, lon], popup="KHO TỔNG", icon=folium.Icon(color="red", icon="home")).add_to(m)
        else:
            folium.Marker([lat, lon], popup=f"Đơn {node.id} ({node.demand}kg)", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)
    
    colors = ['blue', 'green', 'purple', 'orange', 'darkred', 'cadetblue', 'pink', 'gray', 'black']
    for idx, route_polyline in enumerate(route_geometries):
        if route_polyline: 
            folium.PolyLine(
                route_polyline, 
                color=colors[idx % len(colors)], 
                weight=5, 
                opacity=0.8,
                tooltip=f"Tuyến xe {idx + 1}"
            ).add_to(m)
            
    return m

# --- GIAO DIỆN CHÍNH (STREAMLIT) ---
def main():
    st.set_page_config(page_title="GR4 - Last-Mile Delivery", layout="wide", initial_sidebar_state="collapsed")
    
    # 1. GỌI FILE CSS
    load_local_css("style.css")

    if 'is_optimized' not in st.session_state:
        st.session_state.update({
            'is_optimized': False, 
            'result_routes': [], 
            'route_geometries': [],
            'nodes': [], 
            'dist_mat': None, 
            'time_mat': None,
            'opt_kpis': None,
            'base_kpis': None
        })

    # ==========================================
    # LOGIC XỬ LÝ HEADER ĐỘNG
    # ==========================================
    is_logged_in = st.session_state.get('logged_in', False)
    user_email = st.session_state.get('current_email', '')

    # Mặc định lúc chưa đăng nhập
    avatar_src = "https://ui-avatars.com/api/?name=Guest&background=cccccc&color=fff"
    user_name = "Khách"

    # Nếu đã đăng nhập thì lấy thông tin
    if is_logged_in and 'user_db' in st.session_state and user_email in st.session_state['user_db']:
        user_info = st.session_state['user_db'][user_email]
        user_name = user_info.get('name', 'Hồ sơ')
        
        if user_info.get('avatar'):
            avatar_src = user_info['avatar']
        else:
            avatar_src = f"https://ui-avatars.com/api/?name={user_name}&background=random&color=fff"

    # ==========================================
    # RENDER HEADER (BẢN CHUẨN - AN TOÀN)
    # ==========================================
    col_logo, col_space, col_avatar, col_btn = st.columns([5, 3, 0.8, 1.5], vertical_alignment="center")

    with col_logo:
        st.markdown("<h2 style='color: #114B32; margin: 0; padding-top: 5px;'>Gr4 - Last-Mile Delivery</h2>", unsafe_allow_html=True)

    with col_avatar:
        st.markdown(f'''
            <div style="display: flex; justify-content: flex-end; margin-top: 8px;">
                <img src="{avatar_src}" style="width: 40px; height: 40px; border-radius: 50%; border: 2px solid #114B32; object-fit: cover;">
            </div>
        ''', unsafe_allow_html=True)

    with col_btn:
        if is_logged_in:
            if st.button(f"{user_name}", use_container_width=True):
                st.switch_page("pages/profile.py")
        else:
            if st.button("Đăng nhập", use_container_width=True):
                st.switch_page("pages/login.py")

    # Đường kẻ ngang
    st.markdown("<hr style='margin-top: 5px; margin-bottom: 20px; border-color: #e0e0e0;'>", unsafe_allow_html=True)

    # 3. NỘI DUNG BÊN DƯỚI (Chia cột)
    col_input, col_map, col_routes = st.columns([1.2, 2.5, 1.3])

    with col_input:
        st.subheader("NHẬP DỮ LIỆU")
        with st.expander("1. Điểm giao hàng", expanded=True):
            uploaded_file = st.file_uploader("Tải Excel đơn hàng", type=["xlsx", "xls"])
            
        with st.expander("2. Thông số xe", expanded=True):
            max_cap = st.number_input("Tải trọng tối đa/xe (kg):", value=100.0)
            
        btn_run = st.button(" BẮT ĐẦU TỐI ƯU")

    if btn_run:
        if uploaded_file is None:
            st.error("Vui lòng tải lên file Excel dữ liệu đơn hàng!")
        else:
            with st.spinner("Đang khởi tạo dữ liệu và gọi API Goong..."):
                client = GoongServiceClient(GOONG_API_KEY)
                nodes = [DeliveryNode(0, "10.8507, 106.7724", 0, 0, 1440, 0)] 
                
                try:
                    df = pd.read_excel(uploaded_file)
                    for i, row in df.iterrows():
                        address_raw = str(row['Địa Chỉ'])
                        if not is_coordinate(address_raw):
                            coords = client.geocode(address_raw)
                            if coords: 
                                address_raw = coords 
                            else:
                                st.warning(f"Lỗi Geocode: Bỏ qua địa chỉ '{address_raw}'.")
                                continue 
                                
                        nodes.append(DeliveryNode(
                            id=i+1, 
                            address=address_raw, 
                            demand=float(row['Khối Lượng']),
                            ready_time=parse_time(row.get('Sớm Nhất'), 0), 
                            due_date=parse_time(row.get('Trễ Nhất'), 1440), 
                            service_time=10.0
                        ))
                except Exception as e:
                    st.error(f"Lỗi đọc file Excel: {e}")
                    st.stop()
                
                matrix_result = client.fetch_matrices(nodes)
                if matrix_result is not None and matrix_result[0] is not None:
                    dist_mat, time_mat = matrix_result 
                    
                    fleet = FleetConfiguration(total_vehicles=999, max_capacity=max_cap)
                    solver = ClarkeWrightSolver(nodes, fleet, dist_mat, time_mat)
                    final_routes = solver.run_optimization()
                    
                    baseline_routes = run_baseline(nodes, max_cap)
                    
                    opt_km, opt_cost, opt_hrs, opt_veh = get_kpis(final_routes, dist_mat, time_mat)
                    base_km, base_cost, base_hrs, base_veh = get_kpis(baseline_routes, dist_mat, time_mat)
                    
                    # ====== LƯU LỊCH SỬ TỐI ƯU VÀO HỒ SƠ ======
                    if st.session_state.get('logged_in', False):
                        current_email = st.session_state.get('current_email')
                        if current_email and 'user_db' in st.session_state and current_email in st.session_state['user_db']:
                            if 'history' not in st.session_state['user_db'][current_email]:
                                st.session_state['user_db'][current_email]['history'] = []
                                
                            new_opt_record = {
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "locations": len(nodes) - 1, 
                                "distance": round(opt_km, 2),
                                "cost": f"{opt_cost:,.0f} đ"
                            }
                            st.session_state['user_db'][current_email]['history'].append(new_opt_record)
                            save_db(st.session_state['user_db'])

                    route_geometries = []
                    for route in final_routes:
                        full_route_coords = []
                        for k in range(len(route)-1):
                            origin = nodes[route[k]].address
                            destination = nodes[route[k+1]].address
                            segment_coords = client.fetch_route_geometry(origin, destination)
                            if segment_coords:
                                full_route_coords.extend(segment_coords)
                        route_geometries.append(full_route_coords)

                    st.session_state.update({
                        'result_routes': final_routes, 
                        'route_geometries': route_geometries,
                        'nodes': nodes, 
                        'dist_mat': dist_mat, 
                        'time_mat': time_mat,
                        'max_cap': max_cap,
                        'opt_kpis': (opt_km, opt_cost, opt_hrs, opt_veh),
                        'base_kpis': (base_km, base_cost, base_hrs, base_veh),
                        'is_optimized': True
                    })
                else:
                    st.error("Lỗi lấy dữ liệu bản đồ. Vui lòng kiểm tra API Key.")

    with col_map:
        st.subheader(" BẢN ĐỒ LỘ TRÌNH THỰC TẾ")
        if st.session_state.is_optimized:
            map_fig = draw_route_map(st.session_state.nodes, st.session_state.route_geometries)
            st_folium(map_fig, width="100%", height=500, returned_objects=[])
        else: 
            st.info("Bản đồ sẽ hiển thị ở đây sau khi chạy tối ưu.")

    with col_routes:
        st.subheader(" LỘ TRÌNH CÁC XE")
        if st.session_state.is_optimized:
            for i, r in enumerate(st.session_state.result_routes):
                load = sum(st.session_state.nodes[n].demand for n in r)
                dist_m = sum(st.session_state.dist_mat[r[k]][r[k+1]] for k in range(len(r)-1))
                dist_km = dist_m / 1000
                path_str = ' ➔ '.join(['Kho' if n==0 else f'Đơn {n}' for n in r])
                
                st.markdown(f"""
                <div class="route-card">
                    <h4 style='margin-top:0; color:#114B32;'>Xe {i+1}</h4>
                    <b>Lộ trình:</b> {path_str}<br>
                    <b>Tải trọng:</b> {load} / {st.session_state.max_cap} kg<br>
                    <b>Quãng đường:</b> {dist_km:.2f} km
                </div>
                """, unsafe_allow_html=True)
        else: 
            st.write("Chưa có dữ liệu phân tuyến.")

    # 4. BẢNG KPI
    if st.session_state.is_optimized:
        opt_km, opt_cost, opt_hrs, opt_veh = st.session_state.opt_kpis
        base_km, base_cost, base_hrs, base_veh = st.session_state.base_kpis
        
        delta_km = opt_km - base_km
        delta_cost = opt_cost - base_cost
        delta_hrs = opt_hrs - base_hrs
        delta_veh = opt_veh - base_veh

        badge_km = render_delta_badge(delta_km, "{:.1f}", "km", "so với gốc")
        badge_cost = render_delta_badge(delta_cost, "{:,.0f}", "đ")
        badge_hrs = render_delta_badge(delta_hrs, "{:.1f}", "giờ")
        badge_veh = render_delta_badge(delta_veh, "{:g}", "xe")

        st.markdown(f"""<div style="background-color: #114B32; padding: 25px; border-radius: 12px; margin-top: 30px;">
<h4 style="color: white; margin-top: 0; margin-bottom: 20px; font-family: sans-serif;">HIỆU SUẤT VÀ CHI PHÍ</h4>
<div style="display: flex; gap: 20px; justify-content: space-between; flex-wrap: wrap;">
<div style="background-color: white; padding: 15px; border-radius: 15px; flex: 1; min-width: 220px; box-shadow: 2px 2px 10px rgba(0,0,0,0.2); display: flex; align-items: center;">
<div style="font-size: 45px; margin-right: 15px; background: #f0f4f8; border-radius: 10px; padding: 5px 10px;">🛣️</div>
<div>
<div style="font-weight: bold; font-size: 15px; color: #555; margin-bottom: 3px;">Tổng Quãng Đường</div>
<div style="font-size: 24px; font-weight: 900; color: #000;">{opt_km:.1f} km</div>
{badge_km}
</div>
</div>
<div style="background-color: white; padding: 15px; border-radius: 15px; flex: 1; min-width: 220px; box-shadow: 2px 2px 10px rgba(0,0,0,0.2); display: flex; align-items: center;">
<div style="font-size: 45px; margin-right: 15px; background: #fdf5e6; border-radius: 10px; padding: 5px 10px;">⛽</div>
<div>
<div style="font-weight: bold; font-size: 15px; color: #555; margin-bottom: 3px;">Chi Phí Nhiên Liệu</div>
<div style="font-size: 24px; font-weight: 900; color: #000;">{opt_cost:,.0f} đ</div>
{badge_cost}
</div>
</div>
<div style="background-color: white; padding: 15px; border-radius: 15px; flex: 1; min-width: 220px; box-shadow: 2px 2px 10px rgba(0,0,0,0.2); display: flex; align-items: center;">
<div style="font-size: 45px; margin-right: 15px; background: #e6f7ff; border-radius: 10px; padding: 5px 10px;">⏱️</div>
<div>
<div style="font-weight: bold; font-size: 15px; color: #555; margin-bottom: 3px;">Tổng Thời Gian</div>
<div style="font-size: 24px; font-weight: 900; color: #000;">{opt_hrs:.1f} giờ</div>
{badge_hrs}
</div>
</div>
<div style="background-color: white; padding: 15px; border-radius: 15px; flex: 1; min-width: 220px; box-shadow: 2px 2px 10px rgba(0,0,0,0.2); display: flex; align-items: center;">
<div style="font-size: 45px; margin-right: 15px; background: #f9f0ff; border-radius: 10px; padding: 5px 10px;">🚚</div>
<div>
<div style="font-weight: bold; font-size: 15px; color: #555; margin-bottom: 3px;">Số Lượng Xe</div>
<div style="font-size: 24px; font-weight: 900; color: #000;">{opt_veh} xe</div>
{badge_veh}
</div>
</div>
</div>
</div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()