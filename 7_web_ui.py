import streamlit as st
import ccxt
import time
from datetime import datetime

# === 网页基本配置 ===
st.set_page_config(
    page_title="双端套利监控台",
    page_icon="⚡",
    layout="wide" # 宽屏模式
)

# === 标题栏 ===
st.title("⚡ Backpack vs Hyperliquid 套利雷达")
st.markdown("---") # 分割线

# === 初始化连接 (使用缓存，避免每次刷新都重连) ===
@st.cache_resource
def init_exchanges():
    return ccxt.backpack(), ccxt.hyperliquid()

backpack, hyperliquid = init_exchanges()

# === 创建占位符 (用于动态刷新内容) ===
# 这一步很关键，我们在网页上挖几个坑，稍后不断往里填新数据
metrics_container = st.empty()
chart_container = st.empty()
log_container = st.container()

# === 主循环逻辑 ===
def run_dashboard():
    # 创建两个空列表，用于记录历史价差，画图用
    spread_history = []
    
    while True:
        try:
            # 1. 获取数据
            ticker_bp = backpack.fetch_ticker('BTC/USDC')
            ticker_hl = hyperliquid.fetch_ticker('BTC/USDC')
            
            price_bp = ticker_bp['last']
            price_hl = ticker_hl['last']
            
            # 2. 计算价差
            diff = price_bp - price_hl
            diff_percent = (diff / price_bp) * 100
            
            # 记录数据用于画图 (只保留最近 50 次)
            spread_history.append(diff)
            if len(spread_history) > 50:
                spread_history.pop(0)

            # 3. 更新界面内容
            with metrics_container.container():
                # 使用 3 列布局
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(label="🎒 Backpack (BTC)", value=f"${price_bp:,.2f}")
                
                with col2:
                    st.metric(label="💧 Hyperliquid (BTC)", value=f"${price_hl:,.2f}")
                
                with col3:
                    # 这里的 delta_color 很有趣：
                    # 如果价差是正的(Backpack贵)，显示绿色；负的显示红色（反之亦然，看您策略）
                    st.metric(
                        label="价差 (Spread)", 
                        value=f"${abs(diff):.2f}", 
                        delta=f"{diff_percent:.4f}%",
                        delta_color="off" # 颜色我们自己控制
                    )
                
                # 状态横幅
                if abs(diff_percent) > 0.05:
                    st.error(f"🔥 发现大额价差！机会来了！方向：{'做空BP/做多HL' if diff > 0 else '做空HL/做多BP'}")
                else:
                    st.success("💤 市场平静，正在监控中...")

            # 4. 更新简单的折线图
            with chart_container.container():
                st.write("### 📊 价差波动走势 (USD)")
                st.line_chart(spread_history)

            # 5. 休息一下
            time.sleep(3)
            
        except Exception as e:
            st.error(f"获取数据出错: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_dashboard()