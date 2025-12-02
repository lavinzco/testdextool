import streamlit as st
import ccxt
import time
import os
import sqlite3
import json
import concurrent.futures
from datetime import datetime
from dotenv import load_dotenv

# === 0. 基础配置与安全加载 ===
load_dotenv()
st.set_page_config(page_title="VibeTrader Pro (Auto)", layout="wide", page_icon="⚡")

# 数据库文件路径
DB_FILE = "bot_state.db"

# 自定义样式
st.markdown("""
<style>
    .big-font {font-size:20px !important; font-weight: bold;}
    .status-ok {color: green;}
    .status-warn {color: orange;}
    .status-danger {color: red;}
</style>
""", unsafe_allow_html=True)

# === 1. 数据库管理 (持久化核心) ===
def init_db():
    """初始化数据库表，用于记录机器人状态，防止刷新丢失"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 创建状态表：记录当前是否持仓、方向、开仓价差、数量
    c.execute('''CREATE TABLE IF NOT EXISTS bot_state
                 (id INTEGER PRIMARY KEY, status TEXT, direction TEXT, 
                  entry_spread REAL, amount REAL, timestamp TEXT)''')
    # 确保有一行初始数据
    c.execute("SELECT count(*) FROM bot_state")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO bot_state VALUES (1, 'EMPTY', 'NONE', 0.0, 0.0, '')")
        conn.commit()
    conn.close()

def get_state():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM bot_state WHERE id=1")
    row = c.fetchone()
    conn.close()
    return {
        "status": row[1],       # 'EMPTY' or 'HOLDING'
        "direction": row[2],    # e.g., 'Long_BP_Short_HL'
        "entry_spread": row[3],
        "amount": row[4],
        "timestamp": row[5]
    }

def update_state(status, direction, entry_spread, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE bot_state SET status=?, direction=?, entry_spread=?, amount=?, timestamp=? WHERE id=1",
              (status, direction, entry_spread, amount, ts))
    conn.commit()
    conn.close()

# 初始化数据库
init_db()

# === 2. 交易所连接 ===
@st.cache_resource
def init_exchanges():
    exchanges = {}
    # Backpack
    bp_key = os.getenv("BP_API_KEY")
    bp_secret = os.getenv("BP_SECRET")
    if bp_key and bp_secret:
        exchanges['bp'] = ccxt.backpack({'apiKey': bp_key, 'secret': bp_secret, 'enableRateLimit': True})
    else:
        exchanges['bp'] = ccxt.backpack({'enableRateLimit': True}) # 仅行情

    # Hyperliquid
    hl_private = os.getenv("HL_PRIVATE_KEY")
    hl_address = os.getenv("HL_WALLET_ADDRESS")
    if hl_private:
        exchanges['hl'] = ccxt.hyperliquid({'walletAddress': hl_address, 'privateKey': hl_private, 'enableRateLimit': True})
    else:
        exchanges['hl'] = ccxt.hyperliquid({'enableRateLimit': True}) # 仅行情
    
    return exchanges

exchanges = init_exchanges()
backpack = exchanges['bp']
hyperliquid = exchanges['hl']

# === 3. 核心交易逻辑 (并发与风控) ===
def place_order_safe(exchange, symbol, side, amount, is_real):
    """单个下单函数的安全封装"""
    if not is_real:
        return {"id": f"sim_{int(time.time()*1000)}", "status": "closed"}
    return exchange.create_order(symbol, 'market', side, amount)

def execute_dual_trade(direction, amount, symbol_bp, symbol_hl, is_real):
    """
    并发执行双边交易，包含‘单边成交’的回滚保护
    direction: 'Long_BP_Short_HL' or 'Short_BP_Long_HL'
    """
    # 1. 解析方向
    if direction == "Long_BP_Short_HL":
        side_bp, side_hl = 'buy', 'sell'
    else:
        side_bp, side_hl = 'sell', 'buy'

    log_msgs = []
    success = False

    # 2. 并发下单
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_bp = executor.submit(place_order_safe, backpack, symbol_bp, side_bp, amount, is_real)
        future_hl = executor.submit(place_order_safe, hyperliquid, symbol_hl, side_hl, amount, is_real)
        
        res_bp, res_hl = None, None
        err_bp, err_hl = None, None

        # 获取 BP 结果
        try:
            res_bp = future_bp.result()
        except Exception as e:
            err_bp = str(e)

        # 获取 HL 结果
        try:
            res_hl = future_hl.result()
        except Exception as e:
            err_hl = str(e)

    # 3. 结果判定与回滚逻辑 (Critical Risk Logic)
    if res_bp and res_hl:
        # --- 完美：双边成功 ---
        success = True
        log_msgs.append(f"✅ 双边成交! BP:{res_bp['id']} | HL:{res_hl['id']}")
    
    elif err_bp and err_hl:
        # --- 安全：双边失败 ---
        success = False
        log_msgs.append(f"❌ 双边失败 (资金安全)。BP Err: {err_bp} | HL Err: {err_hl}")
    
    else:
        # --- 危险：单边成交 (Legging) -> 立即触发回滚 ---
        success = False
        log_msgs.append("🚨 严重警告：发生单边成交！正在执行回滚...")
        
        if res_bp and not res_hl:
            # BP成交，HL失败 -> 平掉 BP
            log_msgs.append(f"原因是: HL下单失败 ({err_hl})")
            try:
                # 反向平仓
                rollback_side = 'sell' if side_bp == 'buy' else 'buy'
                if is_real:
                    backpack.create_order(symbol_bp, 'market', rollback_side, amount)
                log_msgs.append("✅ 回滚成功：Backpack 仓位已平掉。")
            except Exception as e:
                log_msgs.append(f"💀 致命错误：回滚 Backpack 失败！请手动操作！{e}")
                
        elif res_hl and not res_bp:
            # HL成交，BP失败 -> 平掉 HL
            log_msgs.append(f"原因是: BP下单失败 ({err_bp})")
            try:
                rollback_side = 'sell' if side_hl == 'buy' else 'buy'
                if is_real:
                    hyperliquid.create_order(symbol_hl, 'market', rollback_side, amount)
                log_msgs.append("✅ 回滚成功：Hyperliquid 仓位已平掉。")
            except Exception as e:
                log_msgs.append(f"💀 致命错误：回滚 Hyperliquid 失败！请手动操作！{e}")

    return success, log_msgs

# === 4. UI 布局 ===
st.sidebar.header("🛠️ 参数配置")

# 模式选择
mode = st.sidebar.radio("交易模式", ["🛡️ 模拟 (Simulation)", "⚡ 实盘 (Real Money)"])
IS_REAL = "实盘" in mode
if IS_REAL:
    st.sidebar.error("⚠️ 实盘模式已激活")

# 交易对与数量
st.sidebar.subheader("资产设置")
SYMBOL_BP = st.sidebar.text_input("Backpack Symbol", "BTC/USDC")
SYMBOL_HL = st.sidebar.text_input("Hyperliquid Symbol", "BTC/USDC")
TRADE_AMOUNT = st.sidebar.number_input("下单数量", 0.0001, 10.0, 0.001, step=0.0001, format="%.4f")

# 自动化阈值 (精度优化版)
st.sidebar.subheader("🤖 自动化策略")
AUTO_ENABLED = st.sidebar.checkbox("启用自动交易机器人", value=False)

# 修改点：增加了 format="%.4f" 以显示4位小数，step 调整为 0.001 以支持微调
OPEN_THRESHOLD = st.sidebar.number_input(
    "开仓阈值 (Spread %)", 
    min_value=0.001, 
    max_value=5.0, 
    value=0.010,  # 默认设置为 0.01%
    step=0.001,   # 步长改小
    format="%.4f" # 关键：显示4位小数，否则 0.01 可能显示为 0.00
)

CLOSE_THRESHOLD = st.sidebar.number_input(
    "平仓阈值 (Spread %)", 
    min_value=-5.0, 
    max_value=5.0, 
    value=0.005,  # 默认设置为 0.005%
    step=0.001, 
    format="%.4f"
)

st.title("🚀 VibeTrader 自动套利终端")

# 状态显示区
col1, col2, col3, col4 = st.columns(4)
bp_price_box = col1.empty()
hl_price_box = col2.empty()
spread_box = col3.empty()
status_box = col4.empty()

log_expander = st.expander("📜 运行日志", expanded=True)
log_placeholder = log_expander.empty()

# 用于存储本次运行日志的列表
if 'logs' not in st.session_state:
    st.session_state.logs = []

def add_log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.insert(0, f"[{ts}] {msg}")
    # 保持日志长度
    if len(st.session_state.logs) > 50:
        st.session_state.logs.pop()

# === 5. 主循环 (Automated Loop) ===
if st.button("🛑 停止运行"):
    st.stop()

# 自动刷新容器
placeholder = st.empty()

# 获取当前机器人状态
bot_state = get_state()
CURRENT_STATUS = bot_state['status'] # 'EMPTY' or 'HOLDING'
CURRENT_DIR = bot_state['direction']
ENTRY_SPREAD = bot_state['entry_spread']

try:
    # 1. 获取行情
    ticker_bp = backpack.fetch_ticker(SYMBOL_BP)
    ticker_hl = hyperliquid.fetch_ticker(SYMBOL_HL)
    
    p_bp = ticker_bp['last']
    p_hl = ticker_hl['last']
    
    # 2. 计算价差
    diff = p_bp - p_hl
    diff_pct = (diff / p_bp) * 100
    abs_diff_pct = abs(diff_pct)
    
    # 3. UI 更新
    bp_price_box.metric("Backpack", f"${p_bp:,.2f}")
    hl_price_box.metric("Hyperliquid", f"${p_hl:,.2f}")
    
    # 价差颜色
    spread_color = "normal"
    if abs_diff_pct >= OPEN_THRESHOLD: spread_color = "inverse" # 达到开仓机会
    spread_box.metric("Spread %", f"{diff_pct:.4f}%", f"${diff:.2f}", delta_color=spread_color)
    
    # 状态显示
    if CURRENT_STATUS == "EMPTY":
        status_box.markdown(f"### ⚪ 空仓待机\n等待价差 > {OPEN_THRESHOLD}%")
    else:
        status_box.markdown(f"### 🔵 持仓中\n方向: {CURRENT_DIR}\n目标: < {CLOSE_THRESHOLD}%")

    # === 4. 自动化决策逻辑 ===
    if AUTO_ENABLED:
        
        # 场景 A: 空仓 -> 寻找开仓机会
        if CURRENT_STATUS == "EMPTY":
            if abs_diff_pct > OPEN_THRESHOLD:
                # 决定方向
                direction = "Short_BP_Long_HL" if diff_pct > 0 else "Long_BP_Short_HL"
                add_log(f"⚡ 触发自动开仓! 价差 {diff_pct:.2f}%")
                
                # 执行交易
                success, logs = execute_dual_trade(direction, TRADE_AMOUNT, SYMBOL_BP, SYMBOL_HL, IS_REAL)
                for l in logs: add_log(l)
                
                if success:
                    # 更新数据库状态为 HOLDING
                    update_state("HOLDING", direction, diff_pct, TRADE_AMOUNT)
                    st.rerun() # 立即刷新以更新状态
        
        # 场景 B: 持仓 -> 寻找平仓机会
        elif CURRENT_STATUS == "HOLDING":
            # 判断平仓条件
            should_close = False
            
            # 逻辑：价差是否回归
            if "Short_BP" in CURRENT_DIR: 
                # 原本 BP 贵 (diff > 0)，现在希望 diff 变小
                if diff_pct < CLOSE_THRESHOLD: should_close = True
            else:
                # 原本 HL 贵 (diff < 0)，现在希望 diff 变大 (接近0或变正)
                # 即 abs(diff) < CLOSE_THRESHOLD
                if abs_diff_pct < CLOSE_THRESHOLD: should_close = True
            
            if should_close:
                add_log(f"🔄 触发自动平仓! 当前价差 {diff_pct:.2f}% 满足条件")
                
                # 平仓其实就是反向开仓
                close_direction = "Long_BP_Short_HL" if "Short_BP" in CURRENT_DIR else "Short_BP_Long_HL"
                
                success, logs = execute_dual_trade(close_direction, TRADE_AMOUNT, SYMBOL_BP, SYMBOL_HL, IS_REAL)
                for l in logs: add_log(l)
                
                if success:
                    # 更新数据库状态为 EMPTY
                    update_state("EMPTY", "NONE", 0.0, 0.0)
                    st.success("平仓完成，落袋为安！")
                    time.sleep(1)
                    st.rerun()

except Exception as e:
    add_log(f"Error: {str(e)}")

# 渲染日志
log_text = "\n".join(st.session_state.logs)
log_placeholder.text_area("Log Output", log_text, height=200)

# 自动刷新间隔 (模拟循环)
time.sleep(3) 
st.rerun()