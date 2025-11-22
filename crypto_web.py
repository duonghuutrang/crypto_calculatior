import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Crypto Commander Web",
    page_icon="📈",
    layout="wide"
)

# --- 1. LOGIC TÍNH TOÁN (GIỮ NGUYÊN TỪ CODE CŨ) ---
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
    # A. Nhận định xu hướng
    action = "QUAN SÁT"
    color = "gray" # Web dùng tên màu tiếng Anh
    reason = "Thị trường đi ngang (Sideway)."
    
    if rsi_15m < 30:
        action = "MUA (Bắt đáy)"
        color = "green"
        reason = f"RSI 15m thấp ({rsi_15m:.1f}). Giá đang quá bán."
    elif rsi_15m > 70:
        action = "BÁN (Chốt lời)"
        color = "red"
        reason = f"RSI 15m cao ({rsi_15m:.1f}). Giá đang quá mua."
    
    # B. Entry/SL/TP
    entry_price = price
    if action == "QUAN SÁT": 
        entry_price = price * 0.99
        
    sl_price = low_24h * 0.99
    if entry_price <= sl_price: sl_price = entry_price * 0.95
    
    tp_price = entry_price + (entry_price - sl_price) * 1.5
    if tp_price > high_24h: tp_price = high_24h

    # C. Limit & Trailing
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

# --- 2. GIAO DIỆN STREAMLIT ---

# Sidebar: Cấu hình đầu vào
st.sidebar.title("⚙️ Cấu hình")
symbol = st.sidebar.text_input("Mã Coin (Ví dụ: ETH)", value="ETH").upper()
von_input = st.sidebar.number_input("Vốn đầu tư (VND)", value=10000000, step=500000)

# Nút cập nhật tỷ giá USDT
col_tg1, col_tg2 = st.sidebar.columns([3, 1])
with col_tg1:
    ty_gia_default = 26700.0
    if 'usdt_rate' not in st.session_state:
        st.session_state['usdt_rate'] = ty_gia_default
    
    ty_gia = st.number_input("Tỷ giá USDT", value=st.session_state['usdt_rate'], step=100.0)
with col_tg2:
    st.write("")
    st.write("")
    if st.button("🌐"):
        st.session_state['usdt_rate'] = fetch_usdt_rate()
        st.rerun()

# Hiển thị tiêu đề chính
st.title(f"🚀 Crypto Commander: {symbol}")

# Nút Phân Tích (Core Feature)
col_btn, col_auto = st.columns([1, 3])
with col_btn:
    btn_analyze = st.button("🔍 PHÂN TÍCH NGAY", type="primary")

# Logic lấy dữ liệu
pair = symbol if "-" in symbol else f"{symbol}-USDT"
data_analysis = None
current_price = 0
rsi_15 = 0
rsi_4h = 0

if btn_analyze:
    with st.spinner('Đang kết nối OKX...'):
        try:
            # Lấy dữ liệu
            tick = requests.get(f"https://www.okx.com/api/v5/market/ticker?instId={pair}", timeout=5).json()['data'][0]
            last = float(tick['last']); low = float(tick['low24h']); high = float(tick['high24h'])
            
            c15 = requests.get(f"https://www.okx.com/api/v5/market/candles?instId={pair}&bar=15m&limit=25", timeout=5).json()['data']
            rsi_15 = calculate_rsi([float(c[4]) for c in c15][::-1])
            
            c4h = requests.get(f"https://www.okx.com/api/v5/market/candles?instId={pair}&bar=4H&limit=25", timeout=5).json()['data']
            rsi_4h = calculate_rsi([float(c[4]) for c in c4h][::-1])
            
            # Phân tích
            data_analysis = analyze_market_data(last, low, high, rsi_15, rsi_4h)
            current_price = last
            
            # Lưu vào session để không bị mất khi reload nhẹ
            st.session_state['last_analysis'] = {
                'data': data_analysis,
                'price': current_price,
                'rsi15': rsi_15,
                'rsi4h': rsi_4h,
                'time': datetime.now().strftime("%H:%M:%S")
            }
            
        except Exception as e:
            st.error(f"Lỗi kết nối: {e}")

# --- HIỂN THỊ KẾT QUẢ ---
if 'last_analysis' in st.session_state:
    res = st.session_state['last_analysis']
    d = res['data']
    
    # 1. HEADER INFO
    c1, c2, c3 = st.columns(3)
    c1.metric("Giá hiện tại", f"{res['price']}", f"Cập nhật: {res['time']}")
    c2.metric("RSI 15m", f"{res['rsi15']:.1f}")
    c3.metric("RSI 4H", f"{res['rsi4h']:.1f}")
    
    # Thông báo Action
    if d['action'].startswith("MUA"):
        st.success(f"## {d['action']}")
    elif d['action'].startswith("BÁN"):
        st.error(f"## {d['action']}")
    else:
        st.warning(f"## {d['action']}")
    
    st.info(f"💡 Lý do: {d['reason']}")

    # TABS GIAO DIỆN
    tab1, tab2 = st.tabs(["📊 Tính Lời/Lỗ", "💡 Chiến Thuật Lệnh"])

    with tab1:
        st.subheader("Dự tính Lợi nhuận")
        
        c_mua, c_ban = st.columns(2)
        with c_mua:
            gia_mua = st.number_input("Giá Mua (USDT)", value=d['entry'], format="%.4f")
        with c_ban:
            gia_ban = st.number_input("Giá Bán (USDT)", value=d['tp'], format="%.4f")
            
        # Tính toán Realtime
        von_usd = (von_input * 0.999) / ty_gia
        coin_amount = von_usd / gia_mua
        thu_vnd = (coin_amount * gia_ban * ty_gia) * 0.999
        lai_lo = thu_vnd - von_input
        phantram = (lai_lo / von_input) * 100
        
        st.divider()
        col_kq1, col_kq2, col_kq3 = st.columns(3)
        col_kq1.metric("Tiền về (VND)", f"{thu_vnd:,.0f}")
        col_kq2.metric("Lãi/Lỗ (VND)", f"{lai_lo:,.0f}", delta_color="normal" if lai_lo > 0 else "inverse")
        col_kq3.metric("% Lợi nhuận", f"{phantram:.2f}%")

    with tab2:
        st.subheader("Thông số đặt lệnh (Copy vào sàn)")
        
        col_strat1, col_strat2 = st.columns(2)
        with col_strat1:
            st.markdown("### 🛑 Stop Loss / Entry")
            st.write(f"**Entry:** `{d['entry']:.4f}`")
            st.write(f"**Stop Loss:** `{d['sl']:.4f}` (Cắt lỗ)")
            st.write(f"**Take Profit:** `{d['tp']:.4f}` (Chốt lời)")
        
        with col_strat2:
            st.markdown("### 📉 Limit & Trailing")
            st.write(f"**Limit Buy:** `{d['limit_buy']:.4f}`")
            st.write(f"**Limit Sell:** `{d['limit_sell']:.4f}`")
            st.markdown("---")
            st.write(f"**Trailing Activation:** `{d['act_price']:.4f}`")
            st.write(f"**Callback:** `{d['callback']}%`")

else:
    st.info("👈 Nhấn 'PHÂN TÍCH NGAY' để bắt đầu.")

# Footer
st.divider()
st.caption("Crypto Commander Web Edition - Deploy on Localhost")
