import streamlit as st
import pandas as pd
from gspread import service_account_from_dict, authorize
from io import StringIO
from datetime import date
import plotly.express as px
# Đã gỡ bỏ: from streamlit_authenticator import Authenticate

# --- THIẾT LẬP KẾT NỐI VỚI GOOGLE SHEETS ---
# Mã này đọc 11 Secret riêng lẻ mà bạn đã tạo trong Streamlit Cloud
def get_gspread_credentials():
    """Tạo đối tượng credentials từ Streamlit Secrets (11 trường riêng lẻ)."""
    creds = st.secrets
    required_keys = [
        "type", "project_id", "private_key_id", "private_key", 
        "client_email", "client_id", "auth_uri", "token_uri", 
        "auth_provider_x509_cert_url", "client_x509_cert_url", "universe_domain"
    ]
    
    # Kiểm tra xem tất cả các key cần thiết có tồn tại không
    if not all(key in creds for key in required_keys):
        st.error("Lỗi cấu hình Secret: Vui lòng kiểm tra lại 11 trường Secret (type, project_id, etc.)")
        st.stop()
        return None

    # Trả về dictionary credentials
    return {key: creds[key] for key in required_keys}

try:
    gspread_credentials = get_gspread_credentials()
    gc = service_account_from_dict(gspread_credentials)
except Exception as e:
    st.error(f"Lỗi: Không thể khởi tạo kết nối GSpread. Chi tiết: Vui lòng kiểm tra lại định dạng 11 Secret. Lỗi: {e}")
    st.stop()

# ĐÃ THAY THẾ BẰNG ID GOOGLE SHEET CỦA BẠN!
SHEET_ID = "1EUD9CKeFI1deKTPWFmL-RrIbQXmNMWYmNYgKZ5jC3o4" 
SHEET_NAME = "Note chi tiêu" 

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
@st.cache_data(ttl=60) 
def load_data():
    """Đọc toàn bộ dữ liệu từ Google Sheet, làm sạch và tính toán cơ bản."""
    try:
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        required_cols = ['Ngày', 'Danh Mục', 'Số Tiền', 'Ghi Chú']
        if not all(col in df.columns for col in required_cols): 
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
# ĐÃ SỬA LỖI: CHỈ DÙNG EMOJI LÀM FAVICON ĐỂ TRÁNH LỖI FILE
st.set_page_config(page_title="App Quản Lý Chi Tiêu", layout="centered", favicon="$") 

# --- HIỂN THỊ NỘI DUNG CHÍNH (Đã loại bỏ đăng nhập) ---

st.title("Onion's Chi Tiêu")

# Navigation Tabs
tab1, tab2 = st.tabs(["**NHẬP LIỆU**", "**DASHBOARD**"])

# --- TAB 1: NHẬP LIỆU ---
with tab1:
    st.header("Thêm Chi Tiêu Mới")
    
    CATEGORIES = ['Ăn uống', 'Giải trí', 'Tiền nhà', 'Đi lại', 'Mua sắm', 'Du lịch', 'Y tế', 'Phong bì']

    with st.form("Chi_tieu_form", clear_on_submit=True):
        
        date_input = st.date_input("🗓️ **Ngày**", pd.to_datetime('today'))
        category_input = st.selectbox("📝 **Danh Mục**", options=CATEGORIES)
        amount_input = st.number_input("💰 **Số Tiền (VND)**", min_value=1000, step=1000, format="%d")
        note_input = st.text_area("🗒️ **Ghi Chú** (tùy chọn)")

        submitted = st.form_submit_button("UPDATE")

        if submitted:
            if amount_input <= 0:
                st.warning("Vui lòng nhập số tiền lớn hơn 0.")
            else:
                data_to_add = [
                    date_input.strftime('%Y-%m-%d'), 
                    category_input,
                    amount_input,
                    note_input
                ]
                
                ws.append_row(data_to_add)
                
                st.cache_data.clear() 
                st.success("🎉 Dữ liệu đã được ghi thành công! Vui lòng kiểm tra Dashboard.")

# --- TAB 2: DASHBOARD (Sắp xếp lại theo yêu cầu) ---
with tab2:
    st.header("Bảng Điều Khiển Chi Tiêu")
    df = load_data()

    if df.empty:
        st.warning("Chưa có dữ liệu hoặc lỗi tải dữ liệu.")
    else:
        # 1. Các chỉ số KPI chính
        st.subheader("Tổng Quan Chi Tiêu")
        col1, col2 = st.columns(2)
        total_expense = df['Số Tiền'].sum()
        
        with col1:
            st.metric(label="Tổng Chi Tiêu 💰", value=f"{total_expense:,.0f} VND")
        
        avg_expense = df['Số Tiền'].mean()
        with col2:
            st.metric(label="Trung Bình/Giao Dịch ⚖️", value=f"{avg_expense:,.0f} VND")
        
        st.markdown("---")
        
        # 2. Phân loại Chi Tiêu (Biểu đồ tròn - Vị trí MỚI: 1)
        st.subheader("1. Phân Bổ Tổng Chi Tiêu")
        category_summary = df.groupby('Danh Mục')['Số Tiền'].sum().reset_index()

        fig_pie = px.pie(category_summary, 
                         values='Số Tiền', 
                         names='Danh Mục', 
                         title='Tỷ Lệ Chi Tiêu theo Danh Mục',
                         color_discrete_sequence=px.colors.sequential.Agsunset)
        fig_pie.update_traces(textinfo='percent+label', marker=dict(line=dict(color='#000000', width=1)))
        st.plotly_chart(fig_pie, use_container_width=True)
        
        st.markdown("---")
            
        # 3. Biểu đồ Lũy Kế (Biểu đồ đường - Vị trí MỚI: 2)
        st.subheader("2. Xu Hướng Chi Tiêu Lũy Kế")
        df_daily = df.groupby('Ngày')['Số Tiền'].sum().reset_index()
        df_daily['Chi Tiêu Lũy Kế'] = df_daily['Số Tiền'].cumsum()

        fig_cumulative = px.line(
            df_daily, 
            x='Ngày', 
            y='Chi Tiêu Lũy Kế', 
            title='Chi Tiêu Tích Lũy Theo Thời Gian',
            labels={'Chi Tiêu Lũy Kế': 'Tổng Chi Tiêu Lũy Kế (VND)', 'Ngày': 'Ngày'},
            line_shape='spline',
            height=400
        )
        st.plotly_chart(fig_cumulative, use_container_width=True)

        st.markdown("---")
        
        # 4. Bộ lọc Thời gian
        frequency_map = {
            "Ngày": "D",
            "Tuần": "W",
            "Tháng": "M",
            "Quý": "Q",
            "Năm": "Y"
        }
        
        time_period = st.selectbox(
            "🔎 **3. Xem Cơ Cấu Chi Tiêu theo chu kỳ:**",
            options=list(frequency_map.keys()),
            index=2 # Mặc định là Tháng
        )
        
        # 5. Biểu đồ Cơ cấu Chi tiêu Theo Thời gian (Stacked Bar Chart - Vị trí MỚI: 3)
        
        df['Chu Kỳ'] = df['Ngày'].dt.to_period(frequency_map[time_period]).astype(str)
        
        time_series_summary = df.groupby(['Chu Kỳ', 'Danh Mục'])['Số Tiền'].sum().reset_index()

        fig_stack = px.bar(
            time_series_summary, 
            x='Chu Kỳ', 
            y='Số Tiền', 
            color='Danh Mục', 
            title=f'Cơ Cấu Chi Tiêu Chi Tiết Theo {time_period}',
            labels={'Số Tiền': 'Số Tiền (VND)', 'Chu Kỳ': time_period},
            height=450
        )
        fig_stack.update_layout(xaxis_title=time_period, yaxis_title="Số Tiền (VND)")
        st.plotly_chart(fig_stack, use_container_width=True)

        # Hiển thị dữ liệu thô (tùy chọn)
        st.markdown("---")
        st.subheader("Dữ Liệu Thô")
        st.dataframe(df.sort_values(by='Ngày', ascending=False), use_container_width=True)


