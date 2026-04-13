import streamlit as st
import pandas as pd
from datetime import datetime
import base64
import json
# Khởi tạo session state nếu chưa có
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = {'name': '', 'email': ''}
st.set_page_config(page_title="Hồ sơ cá nhân - GR4", layout="centered", initial_sidebar_state="collapsed")

# --- HÀM HỖ TRỢ LƯU DATABASE ---
def save_db(data):
    with open('users_db.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- HÀM TẠO POP-UP ĐỔI ẢNH (Phải đặt trước khi gọi) ---
@st.dialog("Cập nhật ảnh đại diện")
def avatar_upload_dialog():
    st.write("Vui lòng chọn ảnh mới từ máy tính của bạn:")
    new_avatar = st.file_uploader("Chọn ảnh", type=["png", "jpg", "jpeg"], label_visibility="collapsed")
    
    if st.button("Lưu thay đổi", type="primary"):
        if new_avatar is not None:
            # Chuyển ảnh thành chuỗi văn bản (base64) để lưu vào JSON
            bytes_data = new_avatar.getvalue()
            base64_str = base64.b64encode(bytes_data).decode()
            b64_image = f"data:{new_avatar.type};base64,{base64_str}"
            
            # Cập nhật vào Session State và gọi hàm lưu xuống ổ cứng
            user_email = st.session_state.get('current_email')
            st.session_state['user_db'][user_email]['avatar'] = b64_image
            save_db(st.session_state['user_db'])
            
            st.rerun()
        else:
            st.warning("Bạn chưa chọn ảnh nào!")

# ================= 0. KIỂM TRA ĐĂNG NHẬP =================
if not st.session_state.get('logged_in', False):
    st.warning("⚠️ Bạn chưa đăng nhập. Vui lòng đăng nhập để xem hồ sơ.")
    st.page_link("pages/login.py", label="Đi đến trang Đăng nhập", icon="🔐")
    st.stop()

# Lấy thông tin user hiện tại từ Database
user_email = st.session_state.get('current_email')
user_info = st.session_state['user_db'][user_email]

# Khởi tạo các trường dữ liệu nếu chưa có (dành cho user cũ)
if 'avatar' not in user_info:
    user_info['avatar'] = None
if 'history' not in user_info:
    user_info['history'] = []

st.markdown("<h1 style='text-align: center; color: #114B32;'> Hồ sơ cá nhân</h1>", unsafe_allow_html=True)
st.markdown("---")

# ================= 1. KHU VỰC THÔNG TIN CÁ NHÂN =================
col_img, col_info = st.columns([1, 2])

with col_img:
    # Hiện avatar: Ưu tiên ảnh tự tải lên, nếu không có thì dùng ảnh API mặc định
    if user_info['avatar']:
        st.image(user_info['avatar'], width=200, use_container_width=True)
    else:
        default_avatar = f"https://ui-avatars.com/api/?name={user_info['name']}&background=random&color=fff&size=200"
        st.image(default_avatar, width=200, use_container_width=True)
    
    # Nút gọi Pop-up tải ảnh lên (rất gọn gàng)
    if st.button("🔄 Đổi ảnh đại diện", use_container_width=True):
        avatar_upload_dialog()

with col_info:
    st.subheader("Thông tin tài khoản")
    
    # Dùng form để gộp thao tác đổi tên
    with st.form("update_profile"):
        new_name = st.text_input("Họ và tên", value=user_info['name'])
        st.text_input("Email đăng nhập", value=user_email, disabled=True) # Email KHÔNG được sửa
        
        submitted = st.form_submit_button(" Lưu thay đổi")
        if submitted:
            if new_name.strip() == "":
                st.error("Tên không được để trống!")
            else:
                # Cập nhật tên vào DB
                user_info['name'] = new_name
                st.session_state['user_name'] = new_name 
                save_db(st.session_state['user_db']) # <-- MỚI THÊM: Lưu vào ổ cứng để không bị mất!
                
                st.success("Đã lưu thông tin!")
                st.rerun()
    
    st.write("") 
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button(" VỀ TRANG CHỦ", use_container_width=True):
            st.switch_page("userapp.py")
    with col_btn2:
        if st.button(" ĐĂNG XUẤT", type="primary", use_container_width=True):
            st.session_state['logged_in'] = False
            st.switch_page("pages/login.py")

# ================= 2. KHU VỰC LỊCH SỬ TỐI ƯU =================
st.markdown("---")
st.subheader("Lịch sử Tối ưu Last-Mile Delivery")

total_opt = len(user_info['history'])
st.info(f"Tổng số lần bạn đã chạy tối ưu: **{total_opt}** lần")

# HIỂN THỊ BẢNG LỊCH SỬ
if total_opt > 0:
    # Dùng pandas để tạo bảng đẹp
    df_history = pd.DataFrame(user_info['history'])
    # Chỉnh lại tên cột cho tiếng Việt
    df_history.rename(columns={
        "time": "Thời gian", 
        "locations": "Số điểm giao", 
        "distance": "Tổng quãng đường (km)", 
        "cost": "Chi phí ước tính (VNĐ)"
    }, inplace=True)
    
    st.dataframe(df_history, use_container_width=True, hide_index=True)
else:
    st.write("*Bạn chưa có lịch sử tối ưu nào. Hãy ra Trang chủ và chạy thuật toán nhé!*")

