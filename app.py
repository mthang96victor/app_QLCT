import streamlit as st
import pandas as pd
from gspread import service_account_from_dict, authorize
from io import StringIO
from datetime import date, timedelta
import plotly.express as px

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

# --- HÀM TÍNH TOÁN NGÀY (MỚI) ---
def get_date_range(period):
    """Tính toán ngày bắt đầu và ngày kết thúc cho các chu kỳ tương đối."""
    today = date.today()
    
    if period == 'Hôm nay':
        return today, today
    elif period == 'Tuần này':
        start_of_week = today - timedelta(days=today.weekday())
        return start_of_week, today
    elif period == 'Tháng này':
        start_of_month = today.replace(day=1)
        return start_of_month, today
    elif period == 'Năm nay':
        start_of_year = today.replace(month=1, day=1)
        return start_of_year, today
    elif period == 'Tuần trước':
        start_of_last_week = today - timedelta(days=today.weekday() + 7)
        end_of_last_week = today - timedelta(days=today.weekday() + 1)
        return start_of_last_week, end_of_last_week
    elif period == 'Tháng trước':
        first_day_of_this_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_this_month - timedelta(days=1)
        first_day_of_last_month = last_day_of_last_month.replace(day=1)
        return first_day_of_last_month, last_day_of_last_month
    
    return None, None


# --- BẮT ĐẦU GIAO DIỆN STREAMLIT ---
st.set_page_config(page_title="App Quản Lý Chi Tiêu", layout="centered") 

# --- HIỂN THỊ NỘI DUNG CHÍNH ---

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

        submitted = st.form_submit_button("✅ UPDATE")

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

# --- TAB 2: DASHBOARD (Nâng cấp Bộ lọc) ---
with tab2:
    st.header("Bảng Điều Khiển Chi Tiêu")
    df = load_data()

    if df.empty:
        st.warning("Chưa có dữ liệu hoặc lỗi tải dữ liệu.")
    else:
        # --- BỘ LỌC PHẠM VI THỜI GIAN MỚI ---
        st.subheader("Lọc Dữ Liệu")
        filter_type = st.radio(
            "Chọn Phạm Vi Thời Gian:",
            ('Tương đối (Hôm nay/Tuần/Tháng/Năm)', 'Tùy chỉnh (Chọn ngày)'),
            index=0
        )
        
        df_filtered = df.copy()
        
        if filter_type == 'Tương đối (Hôm nay/Tuần/Tháng/Năm)':
            relative_period = st.selectbox(
                "Chọn chu kỳ:",
                ['Hôm nay', 'Tuần này', 'Tháng này', 'Năm nay', 'Tuần trước', 'Tháng trước'],
                index=2
            )
            start_date, end_date = get_date_range(relative_period)
            
            if start_date and end_date:
                st.info(f"Đang hiển thị dữ liệu từ **{start_date.strftime('%d-%m-%Y')}** đến **{end_date.strftime('%d-%m-%Y')}**")
                
                # Áp dụng bộ lọc cho DataFrame
                df_filtered = df[(df['Ngày'].dt.date >= start_date) & 
                                 (df['Ngày'].dt.date <= end_date)]
                
        else: # Tùy chỉnh (Chọn ngày)
            col_start, col_end = st.columns(2)
            with col_start:
                start_date = st.date_input("Ngày Bắt Đầu", df['Ngày'].min())
            with col_end:
                end_date = st.date_input("Ngày Kết Thúc", df['Ngày'].max())
            
            if start_date <= end_date:
                df_filtered = df[(df['Ngày'].dt.date >= start_date) & 
                                 (df['Ngày'].dt.date <= end_date)]
            else:
                st.error("Ngày Bắt Đầu phải nhỏ hơn hoặc bằng Ngày Kết Thúc.")
                df_filtered = pd.DataFrame()
        
        st.markdown("---")
        
        # --- HIỂN THỊ DASHBOARD ---
        
        if df_filtered.empty:
            st.warning("Không tìm thấy chi tiêu nào trong phạm vi thời gian đã chọn.")
        else:
            
            # 1. Các chỉ số KPI chính
            st.subheader("Tổng Quan Chi Tiêu")
            col1, col2 = st.columns(2)
            total_expense = df_filtered['Số Tiền'].sum()
            
            with col1:
                st.metric(label="Tổng Chi Tiêu 💰", value=f"{total_expense:,.0f} VND")
            
            avg_expense = df_filtered['Số Tiền'].mean()
            with col2:
                st.metric(label="Trung Bình/Giao Dịch ⚖️", value=f"{avg_expense:,.0f} VND")
            
            st.markdown("---")
            
            # 2. Bộ lọc Chu kỳ (Dùng cho biểu đồ cột chồng)
            frequency_map = {
                "Ngày": "D", "Tuần": "W", "Tháng": "M", "Quý": "Q", "Năm": "Y"
            }
            
            time_period = st.selectbox(
                "🔎 **Chọn Chu Kỳ Nhóm Dữ Liệu (Cho biểu đồ cột):**",
                options=list(frequency_map.keys()),
                index=2 # Mặc định là Tháng
            )
            st.markdown("---")

            # 3. Phân loại Chi Tiêu (Biểu đồ tròn - Vị trí 1)
            st.subheader("1. Phân Bổ Tổng Chi Tiêu")
            category_summary = df_filtered.groupby('Danh Mục')['Số Tiền'].sum().reset_index()

            fig_pie = px.pie(category_summary, 
                             values='Số Tiền', 
                             names='Danh Mục', 
                             title='Tỷ Lệ Chi Tiêu theo Danh Mục',
                             color_discrete_sequence=px.colors.sequential.Agsunset)
            fig_pie.update_traces(textinfo='percent+label', marker=dict(line=dict(color='#000000', width=1)))
            st.plotly_chart(fig_pie, use_container_width=True)
            
            st.markdown("---")
                
            # 4. Biểu đồ Lũy Kế (Biểu đồ đường - Vị trí 2)
            st.subheader("2. Xu Hướng Chi Tiêu Lũy Kế")
            df_daily = df_filtered.groupby('Ngày')['Số Tiền'].sum().reset_index()
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
            
            # 5. Biểu đồ Cơ cấu Chi tiêu Theo Thời gian (Stacked Bar Chart - Vị trí 3)
            
            df_filtered['Chu Kỳ'] = df_filtered['Ngày'].dt.to_period(frequency_map[time_period]).astype(str)
            
            time_series_summary = df_filtered.groupby(['Chu Kỳ', 'Danh Mục'])['Số Tiền'].sum().reset_index()

            fig_stack = px.bar(
                time_series_summary, 
                x='Chu Kỳ', 
                y='Số Tiền', 
                color='Danh Mục', 
                title=f'3. Cơ Cấu Chi Tiêu Chi Tiết Theo {time_period}',
                labels={'Số Tiền': 'Số Tiền (VND)', 'Chu Kỳ': time_period},
                height=450
            )
            fig_stack.update_layout(xaxis_title=time_period, yaxis_title="Số Tiền (VND)")
            st.plotly_chart(fig_stack, use_container_width=True)

            # Hiển thị dữ liệu thô (tùy chọn)
            st.markdown("---")
            st.subheader("Dữ Liệu Thô")
            st.dataframe(df_filtered.sort_values(by='Ngày', ascending=False), use_container_width=True)
