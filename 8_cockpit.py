import streamlit as st
import ccxt
import time
import pandas as pd # 用于处理表格数据
from datetime import datetime

# === 页面配置 ===
st.set_page_config(page_title="自动化套利驾驶舱", layout="wide", page_icon="🛸")

# === 1. 初始化交易所 (缓存) ===
@st.cache_resource
def init_exchanges():
    return ccxt.backpack(), ccxt.hyperliquid()

backpack, hyperliquid = init_exchanges()

# === 2. 初始化机器人的记忆 (Session State) ===
if 'balance' not in st.session_state:
    st.session_state.balance = 10000.0  # 初始资金 $10,000
if 'in_position' not in st.session_state:
    st.session_state.in_position = False # 当前是否持仓
if 'position_info' not in st.session_state:
    st.session_state.position_info = {} # 持仓详情
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = [] # 交易记录

# === 侧边栏：策略控制台 ===
st.sidebar.title("🎮 策略参数控制")
st.sidebar.markdown("这是您的 PRD 3.2 交易参数配置")
OPEN_THRESHOLD = st.sidebar.slider("开仓阈值 (Open %)", 0.01, 1.0, 0.05) # 默认 0.05%
CLOSE_THRESHOLD = st.sidebar.slider("平仓阈值 (Close %)", 0.00, 0.5, 0.01) # 默认 0.01%
TRADE_SIZE = st.sidebar.number_input("单笔交易额 (USD)", value=1000)

st.sidebar.markdown("---")
if st.sidebar.button("🔴 重置模拟账户"):
    st.session_state.balance = 10000.0
    st.session_state.trade_history = []
    st.session_state.in_position = False
    st.experimental_rerun()

# === 主界面 ===
st.title("🛸 自动化套利驾驶舱 (Simulation Mode)")

# 布局：分为 3 行
# Row 1: 核心指标
col1, col2, col3, col4 = st.columns(4)
metric_bp = col1.empty()
metric_hl = col2.empty()
metric_diff = col3.empty()
metric_pnl = col4.empty()

# Row 2: 当前持仓状态
st.markdown("### 🏦 当前持仓 (Current Position)")
position_container = st.empty()

# Row 3: 历史记录 & 图表
col_chart, col_log = st.columns([2, 1])
with col_chart:
    st.markdown("### 📊 资金曲线")
    chart_place = st.empty()
with col_log:
    st.markdown("### 📝 交易日志")
    log_place = st.empty()

# === 核心循环逻辑 ===
# 为了让 Slider 能实时生效，这里我们不使用 while True 死循环，
# 而是利用 Streamlit 的 rerun 机制。但这需要一点 trick。
# 为简单起见，我们还是用 while True，但在显示端做优化。

spread_history = []

def run_strategy():
    while True:
        try:
            # --- A. 获取数据 ---
            tick_bp = backpack.fetch_ticker('BTC/USDC')
            tick_hl = hyperliquid.fetch_ticker('BTC/USDC')
            
            p_bp = tick_bp['last']
            p_hl = tick_hl['last']
            
            # 计算价差
            diff = p_bp - p_hl
            diff_pct = (abs(diff) / p_bp) * 100
            now_str = datetime.now().strftime("%H:%M:%S")

            # --- B. 策略判定 (Brain) ---
            
            # 1. 开仓逻辑
            if not st.session_state.in_position:
                if diff_pct > OPEN_THRESHOLD:
                    # 记录开仓
                    st.session_state.in_position = True
                    direction = "做空BP / 做多HL" if diff > 0 else "做空HL / 做多BP"
                    st.session_state.position_info = {
                        "time": now_str,
                        "entry_bp": p_bp,
                        "entry_hl": p_hl,
                        "direction": direction,
                        "size": TRADE_SIZE
                    }
                    # 写入一条日志
                    st.toast(f"⚡ 触发开仓！{direction}", icon="🚀")

            # 2. 平仓逻辑
            elif st.session_state.in_position:
                entry = st.session_state.position_info
                # 计算浮动盈亏 (简化算法)
                # 利润 ≈ (开仓价差 - 当前价差) * 仓位 / 价格
                open_spread = abs(entry['entry_bp'] - entry['entry_hl'])
                current_spread = abs(diff)
                profit = ((open_spread - current_spread) / p_bp) * TRADE_SIZE
                
                # 更新持仓显示的盈亏
                st.session_state.position_info['floating_pnl'] = profit

                if diff_pct < CLOSE_THRESHOLD:
                    # 执行平仓
                    st.session_state.balance += profit
                    st.session_state.in_position = False
                    
                    # 记录历史
                    st.session_state.trade_history.append({
                        "Time": now_str,
                        "Type": "Close",
                        "Profit": profit,
                        "Balance": st.session_state.balance
                    })
                    st.toast(f"💰 平仓完成！盈利 ${profit:.2f}", icon="✅")

            # --- C. 刷新 UI ---
            
            # 1. 更新顶部指标
            metric_bp.metric("🎒 Backpack", f"${p_bp:,.2f}")
            metric_hl.metric("💧 Hyperliquid", f"${p_hl:,.2f}")
            metric_diff.metric("价差", f"${abs(diff):.2f}", f"{diff_pct:.4f}%", delta_color="off")
            metric_pnl.metric("虚拟账户净值", f"${st.session_state.balance:,.2f}")

            # 2. 更新持仓卡片
            if st.session_state.in_position:
                info = st.session_state.position_info
                pnl = info.get('floating_pnl', 0)
                color = "green" if pnl >= 0 else "red"
                position_container.markdown(
                    f"""
                    <div style="padding: 20px; border: 2px solid {color}; border-radius: 10px;">
                        <h4>🟢 持仓中 ({info['direction']})</h4>
                        <p>开仓时间: {info['time']} | 仓位大小: ${info['size']}</p>
                        <p>开仓价差: ${abs(info['entry_bp'] - info['entry_hl']):.2f} -> 当前价差: ${abs(diff):.2f}</p>
                        <h3 style="color: {color};">浮动盈亏: ${pnl:.4f}</h3>
                    </div>
                    """, unsafe_allow_html=True
                )
            else:
                position_container.info("💤 当前空仓，正在扫描市场机会...")

            # 3. 更新图表和日志
            if len(st.session_state.trade_history) > 0:
                df = pd.DataFrame(st.session_state.trade_history)
                log_place.dataframe(df.iloc[::-1].head(10), height=200) # 显示最近10条
            
            # 4. 休息
            time.sleep(2)
            
        except Exception as e:
            st.error(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_strategy()