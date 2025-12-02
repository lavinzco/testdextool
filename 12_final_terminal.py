import streamlit as st
import ccxt
import time
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# === 0. 加载安全配置 ===
load_dotenv()

# === 1. 页面配置 ===
st.set_page_config(
    page_title="VibeTrader 终极终端", 
    layout="wide", 
    page_icon="🚀",
    initial_sidebar_state="expanded"
)

# 自定义 CSS 让界面更专业
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b;}
    .stButton>button {width: 100%; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# === 2. 交易所连接与初始化 ===
@st.cache_resource
def init_exchanges():
    """
    初始化交易所连接。
    如果 .env 里有私钥，就建立真实连接；否则只建立公共连接用于看行情。
    """
    exchanges = {}
    
    # --- 连接 Backpack ---
    bp_key = os.getenv("BP_API_KEY")
    bp_secret = os.getenv("BP_SECRET")
    if bp_key and bp_secret:
        exchanges['bp'] = ccxt.backpack({
            'apiKey': bp_key, 'secret': bp_secret, 'enableRateLimit': True
        })
        bp_status = "🟢 已连接 (实盘)"
    else:
        exchanges['bp'] = ccxt.backpack({'enableRateLimit': True})
        bp_status = "🟡 仅行情 (未配置Key)"

    # --- 连接 Hyperliquid ---
    hl_address = os.getenv("HL_WALLET_ADDRESS")
    hl_private = os.getenv("HL_PRIVATE_KEY")
    if hl_private:
        exchanges['hl'] = ccxt.hyperliquid({
            'walletAddress': hl_address, 'privateKey': hl_private, 'enableRateLimit': True
        })
        hl_status = "🟢 已连接 (实盘)"
    else:
        exchanges['hl'] = ccxt.hyperliquid({'enableRateLimit': True})
        hl_status = "🟡 仅行情 (未配置Key)"
        
    return exchanges, bp_status, hl_status

# 初始化
exchanges_dict, bp_status_text, hl_status_text = init_exchanges()
backpack = exchanges_dict['bp']
hyperliquid = exchanges_dict['hl']

# === 3. Session State 状态管理 ===
if 'log' not in st.session_state: st.session_state.log = []
if 'balance' not in st.session_state: st.session_state.balance = 10000.0 # 模拟资金
if 'last_trade_time' not in st.session_state: st.session_state.last_trade_time = None

# === 4. 侧边栏：控制中心 ===
with st.sidebar:
    st.header("🎮 控制中心")
    
    # A. 模式选择
    mode = st.radio("交易模式", ["🛡️ 模拟练习 (Simulation)", "⚡ 实盘交易 (Real Money)"])
    is_real_trading = "实盘" in mode
    
    if is_real_trading:
        st.error("⚠️ 警告：当前处于实盘模式！点击交易将消耗真实资金！")
    else:
        st.success("✅ 当前处于模拟模式，资金为虚拟。")

    st.markdown("---")
    
    # B. 交易参数
    st.subheader("⚙️ 策略参数")
    # 这里修正了您的需求：Backpack 使用 BTC/USD
    SYMBOL_BP = st.text_input("Backpack 交易对", "BTC/USDC")
    SYMBOL_HL = st.text_input("Hyperliquid 交易对", "BTC/USDC")
    
    TRADE_AMOUNT = st.number_input("下单数量 (BTC)", min_value=0.0001, value=0.001, step=0.0001, format="%.4f")
    
    st.markdown("---")
    
    # C. 连接状态
    st.subheader("📡 连接状态")
    st.text(f"Backpack: {bp_status_text}")
    st.text(f"Hyperliq: {hl_status_text}")
    
    # D. 余额查询按钮
# D. 余额查询按钮 (增强版)
    if st.button("💰 刷新真实余额"):
        try:
            if is_real_trading:
                # Backpack: 同时查 USD 和 USDC，哪个有钱显示哪个
                bp_bal_data = backpack.fetch_balance()['total']
                bal_bp = bp_bal_data.get('USD', 0) + bp_bal_data.get('USDC', 0)
                
                # Hyperliquid: 通常是 USDC
                hl_bal_data = hyperliquid.fetch_balance()['total']
                bal_hl = hl_bal_data.get('USDC', 0)
                
                st.toast(f"BP余额: ${bal_bp} | HL余额: ${bal_hl}", icon="✅")
                
                # 如果有钱，顺便更新到 Session State 以便交易时判断
                st.session_state.balance_real_bp = bal_bp
            else:
                st.toast("模拟模式下无法查询真实余额", icon="ℹ️")
        except Exception as e:
            st.error(f"查询失败: {e}")

# === 5. 核心交易函数 ===
def execute_trade(direction, price_bp, price_hl):
    """
    执行交易的核心函数。
    direction: "Long_BP_Short_HL" or "Short_BP_Long_HL"
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_msg = ""
    
    # --- 模拟模式逻辑 ---
    if not is_real_trading:
        # 扣除一点虚拟手续费和滑点
        cost = price_bp * TRADE_AMOUNT * 0.001 
        st.session_state.balance -= cost
        log_msg = f"[{timestamp}] 🛡️ 模拟开仓: {direction} | 数量: {TRADE_AMOUNT} BTC | 虚拟花费: ${cost:.2f}"
        st.session_state.log.append(log_msg)
        st.success("模拟订单已提交！")
        return

    # --- 实盘模式逻辑 ---
    try:
        # 这里的逻辑是：并发下单 (简单版：先下A再下B，严格版需要asyncio)
        # 为了安全，这里演示的是“限价单 Ghost Order”逻辑，或者“市价单 Market Order”
        # 真正的套利通常用 Market 单吃单，但有滑点风险。
        
        st.warning("⚡ 正在发送真实交易指令...")
        
        # 定义买卖方向
        side_bp = 'buy' if "Long_BP" in direction else 'sell'
        side_hl = 'buy' if "Long_HL" in direction else 'sell'
        
        # 1. 发送 Backpack 订单
        # 注意：这里为了容易成交，我们用“市价单”(market)。
        # 如果您想保守，可以改成 'limit' 并指定 price
        order_bp = backpack.create_order(SYMBOL_BP, 'market', side_bp, TRADE_AMOUNT)
        st.toast(f"Backpack 订单成功: {order_bp['id']}", icon="🎒")
        
        # 2. 发送 Hyperliquid 订单
        order_hl = hyperliquid.create_order(SYMBOL_HL, 'market', side_hl, TRADE_AMOUNT)
        st.toast(f"Hyperliquid 订单成功: {order_hl['id']}", icon="💧")
        
        log_msg = f"[{timestamp}] ⚡ 实盘成交: {direction} | BP单号: {order_bp['id']} | HL单号: {order_hl['id']}"
        st.session_state.log.append(log_msg)
        st.balloons() # 庆祝一下
        
    except Exception as e:
        err_msg = f"❌ 交易失败: {e}"
        st.error(err_msg)
        st.session_state.log.append(f"[{timestamp}] {err_msg}")

# === 6. 主界面布局 ===
st.title("🚀 VibeTrader 智能交易终端")

# 实时数据占位符
col1, col2, col3 = st.columns(3)
p_bp_metric = col1.empty()
p_hl_metric = col2.empty()
spread_metric = col3.empty()

action_container = st.container()
log_container = st.expander("📝 交易日志", expanded=True)

# === 7. 主循环 (利用 Streamlit 的 rerun 特性) ===
# 只要没点击停止，它就会自动刷新
if st.button("🛑 停止/刷新监控"):
    st.stop()

try:
    # A. 获取行情
    # 注意：分别获取不同的 Symbol
    ticker_bp = backpack.fetch_ticker(SYMBOL_BP) 
    ticker_hl = hyperliquid.fetch_ticker(SYMBOL_HL)
    
    price_bp = ticker_bp['last']
    price_hl = ticker_hl['last']
    
    # B. 计算价差
    diff = price_bp - price_hl
    diff_pct = (diff / price_bp) * 100
    abs_diff_pct = abs(diff_pct)
    
    # C. 更新UI指标
    p_bp_metric.metric("🎒 Backpack (USD)", f"${price_bp:,.2f}")
    p_hl_metric.metric("💧 Hyperliquid (USDC)", f"${price_hl:,.2f}")
    spread_metric.metric("价差 (Spread)", f"${diff:.2f}", f"{diff_pct:.4f}%")
    
    # D. 机会检测与操作区
    with action_container:
        st.markdown("### 🤖 信号检测")
        
        # 判断方向
        if diff > 0:
            suggest_direction = "Short_BP_Long_HL" # BP贵，卖BP买HL
            desc = f"Backpack 贵 {diff_pct:.2f}% -> 卖BP，买HL"
        else:
            suggest_direction = "Long_BP_Short_HL" # HL贵，买BP卖HL
            desc = f"Hyperliquid 贵 {abs(diff_pct):.2f}% -> 买BP，卖HL"
            
        # 显示建议卡片
        col_act1, col_act2 = st.columns([3, 1])
        with col_act1:
            st.info(f"💡 当前建议: {desc}")
        with col_act2:
            # 这是一个半自动按钮：只有点击才会执行
            # 按钮文本会根据模式变化
            btn_label = "⚡ 执行实盘交易" if is_real_trading else "🛡️ 执行模拟交易"
            btn_type = "primary" if is_real_trading else "secondary"
            
            if st.button(btn_label, type=btn_type):
                execute_trade(suggest_direction, price_bp, price_hl)

    # E. 显示日志
    with log_container:
        for line in reversed(st.session_state.log):
            st.text(line)
            
    # 自动刷新机制 (每2秒刷新一次)
    time.sleep(2)
    st.rerun()

except Exception as e:
    st.error(f"获取数据出错: {e}")
    if "Symbol" in str(e):
        st.warning("提示：请检查左侧边栏的‘交易对’名称是否正确？(如 BTC/USD vs BTC/USDC)")
    time.sleep(5)
    st.rerun()