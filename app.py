import streamlit as st
import pandas as pd
from gspread import service_account_from_dict, authorize
from io import StringIO
from datetime import date
import plotly.express as px

# --- THIẾT LẬP KẾT NỐI VỚI GOOGLE SHEETS ---

# Hàm chuyển đổi Streamlit Secrets thành JSON Credential Dictionary
def get_gspread_credentials():
    """Tạo đối tượng credentials từ Streamlit Secrets (TOML format)."""
    # Lấy toàn bộ secrets ra
    creds = st.secrets

    # Kiểm tra và tạo dictionary credentials từ các key riêng lẻ
    required_keys = ["type", "project_id", "private_key_id", "private_key", "client_email", "client_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url", "client_x509_cert_url", "universe_domain"]
    
    # Đảm bảo tất cả các key JSON cần thiết đều tồn tại trong st.secrets
    if not all(key in creds for key in required_keys):
        st.error("Lỗi cấu hình Secret: Vui lòng kiểm tra lại 11 trường trong Secret.")
        st.stop()
        return None

    # Trả về dictionary credentials
    return {key: creds[key] for key in required_keys}

try:
    # Lấy credentials dictionary
    gspread_credentials = get_gspread_credentials()
    # Khởi tạo client gspread
    gc = service_account_from_dict(gspread_credentials)
except Exception as e:
    st.error(f"Lỗi: Không thể khởi tạo kết nối GSpread. Vui lòng kiểm tra cấu trúc Secret. Chi tiết: {e}")
    st.stop()

# ĐÃ THAY THẾ BẰNG ID GOOGLE SHEET CỦA BẠN!
SHEET_ID = "1EUD9CKeFI1deKTPWFmL-RrIbQXmNMWYmNYgKZ5jC3o4" 
SHEET_NAME = "Sheet1" 

@st.cache_resource
def get_sheet_connection():
    """Mở Google Sheet và trả về worksheet."""
    try:
        sh = gc.open_by_key(SHEET_ID)
        return sh.worksheet(SHEET_NAME)
    except Exception as e:
        st.error(f"Không thể mở Sheet. Vui lòng kiểm tra ID Sheet và quyền Editor của Service Account.")
        st.stop()
        return None

ws = get_sheet_connection()

# --- HÀM TẢI DỮ LIỆU ---
@st.cache_data(ttl=60) # Tải lại dữ liệu sau 60 giây
def load_data():
    """Đọc toàn bộ dữ liệu từ Google Sheet, làm sạch và tính toán cơ bản."""
    try:
        # Code tải dữ liệu giữ nguyên... (các phần còn lại của app.py)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        # Đảm bảo các cột cần thiết tồn tại và làm sạch dữ liệu
        if not all(col in df.columns for col in ['Ngày', 'Danh Mục', 'Số Tiền', 'Ghi Chú']): # Thêm Ghi Chú vào kiểm tra
            st.error("Cấu trúc Sheet không đúng. Cần có các cột: Ngày, Danh Mục, Số Tiền, Ghi Chú.")
            return pd.DataFrame()
            
        df['Ngày'] = pd.to_datetime(df['Ngày'], errors='coerce')
        df['Số Tiền'] = pd.to_numeric(df['Số Tiền'], errors='coerce')
        df.dropna(subset=['Số Tiền', 'Ngày'], inplace=True)
        
        return df
    except Exception as e:
        st.error(f"Không thể tải dữ liệu. Lỗi có thể do dữ liệu không hợp lệ. Chi tiết: {e}")
        return pd.DataFrame()

# --- BẮT ĐẦU GIAO DIỆN STREAMLIT ---
st.set_page_config(page_title="App Quản Lý Chi Tiêu", layout="centered")
st.title("💸 Ứng dụng Quản Lý Chi Tiêu Cá Nhân")

# Navigation Tabs
tab1, tab2 = st.tabs(["**NHẬP LIỆU**", "**DASHBOARD**"])

# --- TAB 1: NHẬP LIỆU ---
with tab1:
    st.header("Thêm Chi Tiêu Mới")
    
    # Danh mục cố định theo yêu cầu của bạn
    CATEGORIES = ['Ăn uống', 'Giải trí', 'Tiền nhà', 'Đi lại', 'Mua sắm', 'Du lịch', 'Y tế', 'Phong bì']

    with st.form("Chi_tieu_form", clear_on_submit=True):
        
        # 1. Ngày
        date_input = st.date_input("🗓️ **Ngày**", pd.to_datetime('today'))
        
        # 2. Danh Mục
        category_input = st.selectbox("📝 **Danh Mục**", options=CATEGORIES)

        # 3. Số Tiền
        amount_input = st.number_input("💰 **Số Tiền (VND)**", min_value=1000, step=1000, format="%d")

        # 4. Ghi Chú
        note_input = st.text_area("🗒️ **Ghi Chú** (tùy chọn)")

        # Nút Ghi Dữ Liệu
        submitted = st.form_submit_button("✅ GHI DỮ LIỆU")

        if submitted:
            if amount_input <= 0:
                st.warning("Vui lòng nhập số tiền lớn hơn 0.")
            else:
                # Chuẩn bị dữ liệu để ghi
                data_to_add = [
                    date_input.strftime('%Y-%m-%d'), 
                    category_input,
                    amount_input,
                    note_input
                ]
                
                # Ghi dữ liệu vào hàng cuối cùng của Sheet
                ws.append_row(data_to_add)
                
                # Xóa cache để Dashboard cập nhật
                st.cache_data.clear() 
                st.success("🎉 Dữ liệu đã được ghi thành công!")

# --- TAB 2: DASHBOARD ---
with tab2:
    st.header("Bảng Điều Khiển Chi Tiêu")
    df = load_data()

    if df.empty:
        st.warning("Chưa có dữ liệu hoặc lỗi tải dữ liệu. Vui lòng kiểm tra kết nối Sheet.")
    else:
        # 1. Các chỉ số KPI chính
        st.subheader("Tổng Quan")
        col1, col2 = st.columns(2)
        total_expense = df['Số Tiền'].sum()
        
        with col1:
            st.metric(label="Tổng Chi Tiêu 💰", value=f"{total_expense:,.0f} VND")
        
        # Tính chi tiêu trung bình
        avg_expense = df['Số Tiền'].mean()
        with col2:
            st.metric(label="Trung Bình/Giao Dịch ⚖️", value=f"{avg_expense:,.0f} VND")
        
        st.markdown("---")
        
        # 2. Phân loại Chi Tiêu (Biểu đồ tròn)
        st.subheader("Phân Loại Chi Tiêu")
        category_summary = df.groupby('Danh Mục')['Số Tiền'].sum().reset_index()

        fig_pie = px.pie(category_summary, 
                         values='Số Tiền', 
                         names='Danh Mục', 
                         title='Tỷ Lệ Chi Tiêu theo Danh Mục',
                         color_discrete_sequence=px.colors.sequential.Agsunset)
        fig_pie.update_traces(textinfo='percent+label', marker=dict(line=dict(color='#000000', width=1)))
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")

        # 3. Xu hướng Chi Tiêu theo Thời gian (Biểu đồ cột)
        st.subheader("Xu Hướng Chi Tiêu Hàng Tháng")
        df['Tháng'] = df['Ngày'].dt.to_period('M')
        monthly_expense = df.groupby('Tháng')['Số Tiền'].sum().reset_index()
        monthly_expense['Tháng'] = monthly_expense['Tháng'].astype(str) 
        
        fig_line = px.bar(monthly_expense, 
                          x='Tháng', 
                          y='Số Tiền', 
                          title='Tổng Chi Tiêu theo Tháng',
                          labels={'Số Tiền': 'Số Tiền (VND)', 'Tháng': 'Tháng'},
                          color_discrete_sequence=['#4CAF50'])
        st.plotly_chart(fig_line, use_container_width=True)

        st.markdown("---")

        # Hiển thị dữ liệu thô (tùy chọn)
        st.subheader("Dữ Liệu Thô")
        st.dataframe(df.sort_values(by='Ngày', ascending=False), use_container_width=True)
