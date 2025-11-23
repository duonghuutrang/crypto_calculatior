import streamlit as st
import requests
import time
import pandas as pd
import pytz  # Thư viện xử lý múi giờ
from datetime import datetime

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Crypto Commander Pro VN",
    page_icon="🇻🇳",
    layout="wide"
)

# --- HÀM XỬ LÝ GIỜ VIỆT NAM ---
def get_vn_time():
    """Lấy thời gian hiện tại theo múi giờ Việt Nam"""
    tz_vn = pytz.timezone('Asia/Ho_Chi_Minh')
    return datetime.now(tz_vn).strftime("%H:%M:%S")

# --- 1. LOGIC TÍNH TOÁN ---

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        if delta > 0: gains.append(delta); losses.append(0)
        else: gains.append(0); losses.append(abs(delta))
    avg_gain = sum(gains[:period])/period
    avg_loss = sum(losses[:period])/period
    for i in range(period, len(prices)-1):
        avg_gain = (avg_gain*(period-1)+gains[i])/period
        avg_loss = (avg_loss*(period-1)+losses[i])/period
    if avg_loss == 0: return 100.0
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def analyze_market_data(price, low_24h, high_24h, rsi_15m, rsi_4h):
    result = {}
    action = "QUAN SÁT"
    color = "gray" 
    reason = "Thị trường đi ngang (Sideway)."
    
    if rsi_15m < 30:
        action = "MUA (Bắt đáy)"
        color = "green"
        reason = f"RSI 15m thấp ({rsi_15m:.1f}). Giá đang quá bán."
    elif rsi_15m > 70:
        action = "BÁN (Chốt lời)"
        color = "red"
        reason = f"RSI 15m cao ({rsi_15m:.1f}). Giá đang quá mua."
    
    entry_price = price
    if action == "QUAN SÁT": 
        entry_price = price * 0.99
        
    sl_price = low_24h * 0.99
    if entry_price <= sl_price: sl_price = entry_price * 0.95
    
    tp_price = entry_price + (entry_price - sl_price) * 1.5
    if tp_price > high_24h: tp_price = high_24h

    limit_buy = low_24h * 1.005
    limit_sell = high_24h * 0.995
    activation_price = price * 1.01
    
    result.update({
        'action': action, 'color': color, 'reason': reason,
        'entry': entry_price, 'sl': sl_price, 'tp': tp_price,
        'limit_buy': limit_buy, 'limit_sell': limit_sell,
        'act_price': activation_price, 'callback': 2.0
    })
    return result

def fetch_usdt_rate():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=vnd"
        res = requests.get(url, timeout=5).json()
        return float(res['tether']['vnd'])
    except:
        return 26700.0

def run_analysis_logic(symbol):
    """Hàm chạy chính để lấy dữ liệu và phân tích"""
    pair = symbol if "-" in symbol else f"{symbol}-USDT"
    try:
        # Lấy dữ liệu OKX
        tick = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={pair}", timeout=5).json()['data'][0]
        last = float(tick['last']); low = float(tick['low24h']); high = float(tick['high24h'])
        
        c15 = requests.get(f"https://www.okx.com/api/v5/market/candles?instId={pair}&bar=15m&limit=25", timeout=5).json()['data']
        rsi_15 = calculate_rsi([float(c[4]) for c in c15][::-1])
        
        c4h = requests.get(f"https://www.okx.com/api/v5/market/candles?instId={pair}&bar=4H&limit=25", timeout=5).json()['data']
        rsi_4h = calculate_rsi([float(c[4]) for c in c4h][::-1])
        
        # Phân tích
        data_analysis = analyze_market_data(last, low, high, rsi_15, rsi_4h)
        
        # --- SỬ DỤNG GIỜ VIỆT NAM ---
        vn_time = get_vn_time()

        # Lưu vào Session State hiện tại
        st.session_state['last_analysis'] = {
            'data': data_analysis,
            'price': last,
            'rsi15': rsi_15,
            'rsi4h': rsi_4h,
            'time': vn_time # Lưu giờ VN
        }

        # --- LƯU VÀO NHẬT KÝ (LOGS) ---
        if 'history_log' not in st.session_state:
            st.session_state['history_log'] = []
        
        new_log = {
            "Giờ (VN)": vn_time, # Tiêu đề cột rõ ràng
            "Giá": last,
            "RSI 15m": round(rsi_15, 2),
            "Hành động": data_analysis['action'],
            "Lý do": data_analysis['reason']
        }
        st.session_state['history_log'].insert(0, new_log)
        
        # Giới hạn 50 bản ghi
        if len(st.session_state['history_log']) > 50:
            st.session_state['history_log'] = st.session_state['history_log'][:50]

        return True
    except Exception as e:
        # Nếu lỗi cũng in giờ VN để dễ debug
        st.error(f"[{get_vn_time()}] Lỗi kết nối OKX: {e}")
        return False

# --- 2. GIAO DIỆN STREAMLIT ---

if 'history_log' not in st.session_state:
    st.session_state['history_log'] = []

# Sidebar
st.sidebar.title("⚙️ Cấu hình")
symbol = st.sidebar.text_input("Mã Coin", value="ETH").upper()
von_input = st.sidebar.number_input("Vốn (VND)", value=10000000, step=500000)

st.sidebar.divider()
st.sidebar.subheader("🔄 Tự động")
auto_update = st.sidebar.checkbox("Bật tự động (30s)", value=False)

col_tg1, col_tg2 = st.sidebar.columns([3, 1])
with col_tg1:
    if 'usdt_rate' not in st.session_state:
        st.session_state['usdt_rate'] = 26700.0
    ty_gia = st.number_input("Tỷ giá USDT", value=st.session_state['usdt_rate'], step=100.0)
with col_tg2:
    st.write("")
    st.write("")
    if st.button("🌐"):
        st.session_state['usdt_rate'] = fetch_usdt_rate()
        st.rerun()

st.title(f"🚀 Crypto Commander: {symbol}")

# Nút Phân Tích
if not auto_update:
    if st.button("🔍 PHÂN TÍCH NGAY", type="primary"):
        with st.spinner('Đang phân tích...'):
            run_analysis_logic(symbol)
else:
    # Hiển thị giờ VN đang chạy
    st.info(f"⚡ Auto Update ON - Giờ Server (VN): {get_vn_time()}")

# Xử lý Auto Update
if auto_update:
    if 'last_analysis' not in st.session_state:
        run_analysis_logic(symbol)

# --- HIỂN THỊ KẾT QUẢ ---
if 'last_analysis' in st.session_state:
    res = st.session_state['last_analysis']
    d = res['data']
    
    # Header Info
    c1, c2, c3 = st.columns(3)
    c1.metric("Giá hiện tại", f"{res['price']}", f"Cập nhật: {res['time']}")
    c2.metric("RSI 15m", f"{res['rsi15']:.1f}")
    c3.metric("RSI 4H", f"{res['rsi4h']:.1f}")
    
    if d['action'].startswith("MUA"):
        st.success(f"## {d['action']}")
    elif d['action'].startswith("BÁN"):
        st.error(f"## {d['action']}")
    else:
        st.warning(f"## {d['action']}")
    
    st.info(f"💡 Lý do: {d['reason']}")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Lời/Lỗ", "💡 Chiến Thuật", "📜 Nhật ký (VN)"])

    with tab1:
        st.subheader("Dự tính Lợi nhuận")
        c_mua, c_ban = st.columns(2)
        with c_mua: gia_mua = st.number_input("Giá Mua", value=d['entry'], format="%.4f")
        with c_ban: gia_ban = st.number_input("Giá Bán", value=d['tp'], format="%.4f")
            
        von_usd = (von_input * 0.999) / ty_gia
        coin_amount = von_usd / gia_mua
        thu_vnd = (coin_amount * gia_ban * ty_gia) * 0.999
        lai_lo = thu_vnd - von_input
        phantram = (lai_lo / von_input) * 100
        
        st.divider()
        col_kq1, col_kq2, col_kq3 = st.columns(3)
        col_kq1.metric("Tiền về", f"{thu_vnd:,.0f} đ")
        col_kq2.metric("Lãi/Lỗ", f"{lai_lo:,.0f} đ", delta_color="normal" if lai_lo > 0 else "inverse")
        col_kq3.metric("% Lãi", f"{phantram:.2f}%")

    with tab2:
        col_strat1, col_strat2 = st.columns(2)
        with col_strat1:
            st.markdown("### 🛑 Entry / Stop Loss")
            st.write(f"**Entry:** `{d['entry']:.4f}`")
            st.write(f"**Stop Loss:** `{d['sl']:.4f}`")
            st.write(f"**Take Profit:** `{d['tp']:.4f}`")
        with col_strat2:
            st.markdown("### 📉 Limit / Trailing")
            st.write(f"**Limit Buy:** `{d['limit_buy']:.4f}`")
            st.write(f"**Act Price:** `{d['act_price']:.4f}`")

    with tab3:
        st.subheader("Nhật ký hoạt động (Giờ VN)")
        if st.session_state['history_log']:
            df_log = pd.DataFrame(st.session_state['history_log'])
            st.line_chart(df_log, x="Giờ (VN)", y="Giá", color="#00FF00")
            st.dataframe(df_log, use_container_width=True)
            if st.button("Xóa nhật ký"):
                st.session_state['history_log'] = []
                st.rerun()
        else:
            st.text("Chưa có dữ liệu.")

else:
    st.info("👈 Bấm 'PHÂN TÍCH NGAY' hoặc bật 'Tự động' để bắt đầu.")

# Auto Update Trigger
if auto_update:
    time.sleep(30)
    run_analysis_logic(symbol)
    st.rerun()

st.divider()
st.caption("Crypto Commander Cloud Ver - Server Timezone: Asia/Ho_Chi_Minh")
