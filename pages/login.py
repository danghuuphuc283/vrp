import streamlit as st
import os
import json
import time

# 1. HÀM NÀY BẮT BUỘC PHẢI ĐẶT LÊN ĐẦU TIÊN (Trước cả session_state)
st.set_page_config(page_title="Đăng nhập / Hồ sơ - GR4", layout="wide", initial_sidebar_state="collapsed")

# Khởi tạo session state nếu chưa có
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = {'name': '', 'email': ''}
if 'current_email' not in st.session_state:
    st.session_state['current_email'] = ""

DB_FILE = 'users_db.json'

def load_db():
    """Hàm tải dữ liệu từ file JSON. Nếu file chưa có thì trả về thư mục rỗng {}"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_db(data):
    """Hàm lưu dữ liệu vào file JSON"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- KHỞI TẠO DB TỪ FILE JSON ---
if 'user_db' not in st.session_state:
    st.session_state['user_db'] = load_db()

# --- HÀM GỌI CSS ---
def load_local_css(file_name):
    css_path = os.path.join(os.path.dirname(__file__), '..', file_name)
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass
load_local_css("style.css")

# --- GIAO DIỆN HEADER ---
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("<h1 style='text-align: center; color: #114B32; font-family: serif; font-size: 48px; margin-bottom: 0px;'>GR4</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray; margin-bottom: 30px;'>Hệ thống tối ưu Last-Mile Delivery</p>", unsafe_allow_html=True)

col_left, col_main, col_right = st.columns([1, 1.5, 1])

with col_main:
    # 2. NẾU ĐÃ ĐĂNG NHẬP RỒI MÀ LẠC VÀO ĐÂY -> ĐẨY VỀ PROFILE NGAY
    if st.session_state.get('logged_in', False):
        st.success(f"Bạn đã đăng nhập với tên **{st.session_state['user_info']['name']}**!")
        st.switch_page("pages/profile.py") 
            
    else:
        # NẾU CHƯA ĐĂNG NHẬP: HIỆN FORM
        tab1, tab2 = st.tabs([" Đăng nhập", " Đăng ký"])

        with tab1:
            login_email = st.text_input("Email", placeholder="Nhập email của bạn...", key="login_email")
            login_pass = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu...", key="login_pass")
            
            if st.button("ĐĂNG NHẬP", type="primary", use_container_width=True, key="btn_login"):
                if login_email and login_pass:
                    if login_email in st.session_state['user_db']:
                        if login_pass == st.session_state['user_db'][login_email]['password']:
                            # LƯU TRẠNG THÁI
                            st.session_state['logged_in'] = True
                            st.session_state['current_email'] = login_email 
                            st.session_state['user_info'] = {
                                'name': st.session_state['user_db'][login_email]['name'],
                                'email': login_email
                            }
                            st.success(f"Đăng nhập thành công! Đang đưa bạn đến Hồ sơ...")
                            time.sleep(1.5)
                            st.switch_page("pages/profile.py")
                        else:
                            st.error("❌ Mật khẩu không chính xác!")
                    else:
                        st.error("❌ Tài khoản này chưa được đăng ký!")
                else:
                    st.warning("⚠️ Vui lòng nhập đầy đủ Email và Mật khẩu!")

        with tab2:
            reg_name = st.text_input("Họ và tên", placeholder="Nhập tên của bạn...", key="reg_name")
            reg_email = st.text_input("Email", placeholder="Nhập email...", key="reg_email")
            reg_pass = st.text_input("Tạo mật khẩu", type="password", key="reg_pass")
            reg_confirm = st.text_input("Xác nhận lại mật khẩu", type="password", key="reg_confirm")
            
            if st.button("ĐĂNG KÝ TÀI KHOẢN", type="primary", use_container_width=True, key="btn_reg"):
                if reg_name and reg_email and reg_pass and reg_confirm:
                    if reg_pass != reg_confirm:
                        st.error("❌ Mật khẩu xác nhận không khớp!")
                    elif reg_email in st.session_state['user_db']:
                        st.error("❌ Email này đã tồn tại!")
                    else:
                        # Tạo data user mới
                        st.session_state['user_db'][reg_email] = {
                            'name': reg_name, 
                            'password': reg_pass,
                            'avatar': None,
                            'history': []
                        }
                        
                        # GỌI HÀM LƯU VÀO FILE JSON NGAY LẬP TỨC
                        save_db(st.session_state['user_db'])
                        
                        st.success(" Đăng ký thành công! Hãy chuyển sang tab 'Đăng nhập'.")
                else:
                    st.warning(" Vui lòng điền đầy đủ thông tin!")

    # 3. ĐÃ SỬA THÀNH USERAPP.PY
    st.divider()
    st.page_link("userapp.py", label="Về Trang chủ Hệ thống")